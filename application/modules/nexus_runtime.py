"""NEXUS runtime composition root.

Registers only locally importable, side-effect-bounded services. Starting this
runtime does not launch miners, unlock wallets, contact providers, or collect
blockchain data. Those actions remain explicit API/user operations.
"""
from __future__ import annotations

import importlib
import importlib.util
import sqlite3
import shutil
import sys
from pathlib import Path
from typing import Any, Callable

from modules.lifecycle_manager import LifecycleManager, ServiceSpec


class ModuleAdapter:
    """Thin adapter that validates a module and exposes a read-only health probe."""

    def __init__(self, module_name: str, probe: Callable[[Any], Any], label: str):
        self.module_name = module_name
        self.probe = probe
        self.label = label
        self.module: Any = None
        self.health: dict[str, Any] = {"ok": False, "state": "not_initialized"}

    def initialize(self) -> None:
        self.module = importlib.import_module(self.module_name)

    def start(self) -> None:
        # Intentionally no automatic external activity.
        if self.module is None:
            raise RuntimeError(f"{self.label} module was not imported")

    def health_check(self) -> dict[str, Any]:
        if self.module is None:
            return {"ok": False, "reason": "module_not_initialized"}
        details = self.probe(self.module)
        self.health = {"ok": True, "module": self.module_name,
                       "label": self.label, "details": details,
                       "mode": "local_read_only_no_autostart"}
        return self.health

    def stop(self) -> None:
        pass

    def shutdown(self) -> None:
        self.module = None



class EdgeServiceAdapter:
    """Lifecycle adapter for the in-memory EDGE pilot; no network or device control."""

    def __init__(self):
        self.service: Any = None

    def initialize(self) -> None:
        module = importlib.import_module("nexus_edge.service")
        self.service = module.EdgeService()

    def start(self) -> None:
        if self.service is None:
            raise RuntimeError("EDGE service was not initialized")
        self.service.initialize()
        self.service.start()

    def health_check(self) -> dict[str, Any]:
        if self.service is None:
            return {"ok": False, "reason": "edge_service_not_initialized"}
        return self.service.health_check()

    def stop(self) -> None:
        if self.service is not None:
            self.service.stop()

    def shutdown(self) -> None:
        if self.service is not None:
            self.service.shutdown()
        self.service = None


class WalletReadOnlyAdapter:
    """Load wallet route module and inspect its DB without creating or decrypting it."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.module: Any = None
        self.health: dict[str, Any] = {"ok": False, "state": "not_initialized"}

    def initialize(self) -> None:
        wallet_dir = self.project_root / "modules" / "wallet_benchmark"
        module_path = wallet_dir / "nexus_wallet_manager.py"
        if not module_path.is_file():
            raise FileNotFoundError(module_path)
        # Existing app imports this legacy module from its wallet directory.
        # Keep the path change scoped to import and restore sys.path immediately.
        wallet_dir_s = str(wallet_dir)
        inserted = wallet_dir_s not in sys.path
        if inserted:
            sys.path.insert(0, wallet_dir_s)
        try:
            spec = importlib.util.spec_from_file_location("nexus_wallet_manager", module_path)
            if spec is None or spec.loader is None:
                raise ImportError("cannot load wallet manager module")
            module = importlib.util.module_from_spec(spec)
            sys.modules.setdefault("nexus_wallet_manager", module)
            spec.loader.exec_module(module)
            self.module = module
        finally:
            if inserted:
                try:
                    sys.path.remove(wallet_dir_s)
                except ValueError:
                    pass

    def start(self) -> None:
        if self.module is None:
            raise RuntimeError("wallet module was not imported")
        # Deliberately do not call initialize_schema(): that creates DB tables.

    def health_check(self) -> dict[str, Any]:
        if self.module is None:
            return {"ok": False, "reason": "wallet_module_not_initialized"}
        db_path = Path(self.module.DB).expanduser().resolve()
        if not db_path.is_file():
            details = {"database_present": False, "schema_checked": False,
                       "vaults_or_keys_opened": False, "database_path": str(db_path)}
        else:
            uri = db_path.as_uri() + "?mode=ro"
            with sqlite3.connect(uri, uri=True, timeout=2) as conn:
                tables = {row[0] for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'")}
            details = {"database_present": True, "schema_checked": True,
                       "wallet_tables_present": sorted(tables.intersection(
                           {"vaults", "bitcoin_vaults", "watch_addresses"})),
                       "vaults_or_keys_opened": False, "database_path": str(db_path)}
        self.health = {"ok": True, "module": "modules.wallet_benchmark.nexus_wallet_manager",
                       "label": "Wallet Engine", "details": details,
                       "mode": "local_read_only_no_unlock_no_schema_mutation"}
        return self.health

    def stop(self) -> None:
        pass

    def shutdown(self) -> None:
        self.module = None


class RCSCReadOnlyAdapter:
    """Inspect RCSC persistence without creating its database or contacting providers."""

    def __init__(self):
        self.module: Any = None

    def initialize(self) -> None:
        self.module = importlib.import_module("modules.rcsc_service")

    def start(self) -> None:
        if self.module is None:
            raise RuntimeError("RCSC module was not imported")
        # Do not call status(): its current implementation initializes SQLite tables.

    def health_check(self) -> dict[str, Any]:
        if self.module is None:
            return {"ok": False, "reason": "rcsc_module_not_initialized"}
        db_path = Path(self.module.DB_PATH).expanduser().resolve()
        if not db_path.is_file():
            details = {"database_present": False, "schema_checked": False,
                       "stored_blocks": None, "stored_runs": None,
                       "database_path": str(db_path)}
        else:
            uri = db_path.as_uri() + "?mode=ro"
            with sqlite3.connect(uri, uri=True, timeout=2) as conn:
                tables = {row[0] for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'")}
                blocks = (conn.execute("SELECT COUNT(*) FROM blocks").fetchone()[0]
                          if "blocks" in tables else None)
                runs = (conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
                        if "runs" in tables else None)
            details = {"database_present": True, "schema_checked": True,
                       "tables_present": sorted(tables.intersection({"blocks", "runs"})),
                       "stored_blocks": blocks, "stored_runs": runs,
                       "database_path": str(db_path)}
        return {"ok": True, "module": "modules.rcsc_service", "label": "RCSC Research",
                "details": details,
                "mode": "local_read_only_no_schema_mutation_no_provider_access"}

    def stop(self) -> None:
        pass

    def shutdown(self) -> None:
        self.module = None


class MiningSupervisorAdapter:
    """Expose supervisor status only; never start a mining mode or worker."""

    def __init__(self):
        self.supervisor: Any = None

    def initialize(self) -> None:
        module = importlib.import_module("mining.hybrid_supervisor")
        self.supervisor = module.HybridSupervisor()

    def start(self) -> None:
        if self.supervisor is None:
            raise RuntimeError("mining supervisor was not initialized")

    def health_check(self) -> dict[str, Any]:
        if self.supervisor is None:
            return {"ok": False, "reason": "supervisor_not_initialized"}
        status = self.supervisor.status(read_only=True)
        states = {name: item.get("state") for name, item in status.get("engines", {}).items()}
        return {"ok": True, "module": "mining.hybrid_supervisor",
                "label": "Mining Supervisor",
                "details": {"mode": status.get("mode"), "mode_state": status.get("mode_state"),
                            "engine_states": states, "workers_started_by_runtime": False},
                "mode": "status_only_no_mining_autostart"}

    def stop(self) -> None:
        # Runtime shutdown must not stop workers started explicitly elsewhere.
        pass

    def shutdown(self) -> None:
        self.supervisor = None


def _data_paths_probe(module: Any) -> dict[str, Any]:
    layout = module.data_layout()
    return {"data_root": layout["root"], "directories": {
        key: value for key, value in layout.items() if key != "root"},
        "filesystem_created_by_probe": False}


def _crypto_probe(module: Any) -> dict[str, Any]:
    engine = module.CryptoEngine()
    algorithms = engine.algorithms()
    if not algorithms:
        raise RuntimeError("no hashing algorithms available")
    import hashlib
    sha256_ok = engine.digest("sha256", b"NEXUS") == hashlib.sha256(b"NEXUS").digest()
    sha256d_ok = engine.digest("sha256d", b"NEXUS") == hashlib.sha256(
        hashlib.sha256(b"NEXUS").digest()).digest()
    if not sha256_ok or not sha256d_ok:
        raise RuntimeError("cryptographic primitive self-test failed")
    names = sorted(row["name"] for row in algorithms)
    return {"algorithms_available": len(algorithms), "algorithm_names": names,
            "sha256_self_test": sha256_ok, "sha256d_self_test": sha256d_ok,
            "pow_algorithms_not_implemented_here": ["RandomX", "KawPow", "Scrypt", "Ethash"],
            "note": "Hash API primitives are not equivalent to coin-specific PoW miners."}


def _math_probe(module: Any) -> dict[str, Any]:
    catalog = module.research_catalog()
    return {"research_catalog_entries": len(catalog.get("shortcuts", [])),
            "auto_apply": False}


def _integrations_probe(module: Any) -> dict[str, Any]:
    rows = module.connector_status(env={})
    return {"providers_catalogued": len(rows), "live_connections_verified": 0,
            "writes_enabled": False}


def _fieldstation_probe(module: Any) -> dict[str, Any]:
    return {"host": module.HOST, "port": module.PORT,
            "data_directory": str(module.DATA_DIR),
            "data_loaded": False, "server_started": False,
            "miner_autostart_enabled": False, "wallet_signing_enabled": False,
            "transaction_broadcast_enabled": False,
            "network_calls_by_probe": False,
            "startup_requires_explicit_standalone_command": True}


def _mining_optimizer_probe(module: Any) -> dict[str, Any]:
    history = module.list_trials(limit=1)
    return {"recorded_trials": history.get("count", 0),
            "policy": history.get("policy"),
            "automatic_parameter_application": False,
            "automatic_coin_switching": False}


def _coin_catalog_probe(module: Any) -> dict[str, Any]:
    return {"provider": "CoinPaprika", "endpoint": module.URL,
            "cache_present": module.CACHE.is_file(),
            "bundled_catalog_present": module.BUNDLED.is_file(),
            "network_calls_by_probe": False,
            "cache_ttl_seconds": module.CACHE_TTL_SECONDS,
            "freshness_checked": False}


def _earnings_intelligence_probe(module: Any) -> dict[str, Any]:
    db_path = Path(module.DB_PATH).expanduser().resolve()
    if not db_path.is_file():
        return {"database_present": False, "schema_checked": False,
                "database_path": str(db_path), "provider_connectors_live": 0,
                "execution_mode": "shadow_only"}
    uri = db_path.as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True, timeout=2) as conn:
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    expected = {"opportunities", "devices", "telemetry", "jobs", "reward_events",
                "payouts", "source_snapshots", "audit_events"}
    return {"database_present": True, "schema_checked": True,
            "tables_present": sorted(tables.intersection(expected)),
            "tables_missing": sorted(expected - tables),
            "database_path": str(db_path), "provider_connectors_live": 0,
            "execution_mode": "shadow_only"}


def _blockchain_regtest_probe(module: Any) -> dict[str, Any]:
    compose_file = Path(module.__file__).with_name("docker-compose.yml")
    return {"bitcoin_rpc": module.BTC_URL, "evm_nodes": sorted(module.EVM_NODES),
            "all_endpoints_loopback": all(
                str(value).startswith(("http://127.0.0.1:", "http://localhost:"))
                for value in [module.BTC_URL, *[entry[1] for entry in module.EVM_NODES.values()]]),
            "compose_file_present": compose_file.is_file(),
            "docker_available": bool(shutil.which("docker")),
            "network_calls_by_probe": False, "nodes_started_by_runtime": False,
            "execution_requires_explicit_local_benchmark": True}


def _mining_switch_probe(module: Any) -> dict[str, Any]:
    policy = dict(module.DEFAULT_POLICY)
    return {"policy": policy, "automatic_switch_enabled": policy["auto_switch_enabled"],
            "requires_verified_source": True, "minimum_measurement_windows": policy["minimum_windows"],
            "cooldown_seconds": policy["cooldown_seconds"],
            "daily_switch_limit": policy["maximum_switches_per_24h"],
            "worker_execution": "only through transactional MiningSupervisor.switch_engine",
            "source_adapter": module.source_adapter_status()}


def _research_hub_probe(module: Any) -> dict[str, Any]:
    catalog = module.catalog()
    history = module.history(limit=1)
    return {"shortcuts_registered": len(catalog.get("shortcuts", [])),
            "saved_experiments": history.get("count", 0),
            "privacy": catalog.get("privacy"),
            "external_uploads": catalog.get("external_uploads", True),
            "auto_apply": False}


def _sha2_probe(module: Any) -> dict[str, Any]:
    status = module.status()
    return {"package": status.get("package"),
            "package_present": status.get("present", False),
            "network_access": False, "miner_auto_apply": False}


def build_runtime(root: str | Path | None = None) -> LifecycleManager:
    """Build the NEXUS runtime graph; no service starts until start_all()."""
    base = Path(root or Path(__file__).resolve().parents[1]).resolve()
    manager = LifecycleManager()

    # Canonical mutable-data location is a foundational runtime service.
    manager.register(ServiceSpec(
        name="data_paths",
        factory=lambda: ModuleAdapter("modules.data_paths", _data_paths_probe, "Central Data Layer"),
        critical=True,
    ))

    # Critical local cryptographic primitive layer.
    manager.register(ServiceSpec(
        name="crypto_engine",
        factory=lambda: ModuleAdapter("modules.crypto_engine.engine", _crypto_probe, "Crypto Engine"),
        critical=True,
    ))
    manager.register(ServiceSpec(
        name="math_intelligence",
        factory=lambda: ModuleAdapter("modules.math_intelligence", _math_probe, "Math Intelligence"),
        dependencies=("crypto_engine", "data_paths"), critical=False,
    ))
    manager.register(ServiceSpec(
        name="provider_registry",
        factory=lambda: ModuleAdapter("modules.integration_registry", _integrations_probe, "Provider Registry"),
        dependencies=("crypto_engine",), critical=False,
    ))
    if (base / "adapters" / "fieldstation" / "crypto_fieldstation" / "app.py").is_file():
        manager.register(ServiceSpec(
            name="depin_fieldstation",
            factory=lambda: ModuleAdapter("adapters.fieldstation.crypto_fieldstation.app", _fieldstation_probe, "DePIN Crypto Fieldstation"),
            dependencies=("crypto_engine", "data_paths"), critical=False,
        ))
    if (base / "modules" / "mining_optimization.py").is_file():
        manager.register(ServiceSpec(
            name="mining_optimizer",
            factory=lambda: ModuleAdapter("modules.mining_optimization", _mining_optimizer_probe, "Mining Optimization Ledger"),
            dependencies=("crypto_engine", "data_paths", "mining_supervisor"), critical=False,
        ))
    if (base / "modules" / "coin_catalog.py").is_file():
        manager.register(ServiceSpec(
            name="coin_catalog",
            factory=lambda: ModuleAdapter("modules.coin_catalog", _coin_catalog_probe, "Crypto Coin Catalog"),
            dependencies=("data_paths",), critical=False,
        ))
    if (base / "modules" / "earnings_intelligence.py").is_file():
        manager.register(ServiceSpec(
            name="earnings_intelligence",
            factory=lambda: ModuleAdapter("modules.earnings_intelligence", _earnings_intelligence_probe, "Earnings Intelligence"),
            dependencies=("crypto_engine", "data_paths"), critical=False,
        ))
    if (base / "nexus_edge" / "service.py").is_file():
        manager.register(ServiceSpec(
            name="edge_manager",
            factory=EdgeServiceAdapter,
            dependencies=("crypto_engine", "data_paths"), critical=False,
        ))
    if (base / "modules" / "blockchain_regtest" / "nexus_v05_integration.py").is_file():
        manager.register(ServiceSpec(
            name="blockchain_regtest",
            factory=lambda: ModuleAdapter("modules.blockchain_regtest.nexus_v05_integration", _blockchain_regtest_probe, "Local Blockchain Regtest"),
            dependencies=("crypto_engine", "data_paths"), critical=False,
        ))
    if (base / "modules" / "mining_switch_controller.py").is_file():
        manager.register(ServiceSpec(
            name="mining_switch_controller",
            factory=lambda: ModuleAdapter("modules.mining_switch_controller", _mining_switch_probe, "Mining Switch Controller"),
            dependencies=("crypto_engine", "data_paths", "mining_supervisor"), critical=False,
        ))
    if (base / "modules" / "research_hub.py").is_file():
        manager.register(ServiceSpec(
            name="research_hub",
            factory=lambda: ModuleAdapter("modules.research_hub", _research_hub_probe, "Research Hub"),
            dependencies=("crypto_engine", "data_paths"), critical=False,
        ))
    if (base / "modules" / "rcsc_service.py").is_file():
        manager.register(ServiceSpec(
            name="rcsc_research",
            factory=RCSCReadOnlyAdapter,
            dependencies=("crypto_engine", "data_paths"), critical=False,
        ))
    if (base / "modules" / "sha2_research_service.py").is_file():
        manager.register(ServiceSpec(
            name="sha2_research",
            factory=lambda: ModuleAdapter("modules.sha2_research_service", _sha2_probe, "SHA-2 Research"),
            dependencies=("crypto_engine", "data_paths"), critical=False,
        ))
    if (base / "modules" / "wallet_benchmark" / "nexus_wallet_manager.py").is_file():
        manager.register(ServiceSpec(
            name="wallet_engine",
            factory=lambda: WalletReadOnlyAdapter(base),
            dependencies=("crypto_engine", "data_paths"), critical=False,
        ))
    if (base / "mining" / "hybrid_supervisor.py").is_file():
        manager.register(ServiceSpec(
            name="mining_supervisor",
            factory=MiningSupervisorAdapter,
            dependencies=("crypto_engine", "data_paths"), critical=False,
        ))
    return manager


def runtime_status(manager: LifecycleManager) -> dict[str, Any]:
    """Return lifecycle state without starting or modifying any service."""
    return manager.snapshot()
