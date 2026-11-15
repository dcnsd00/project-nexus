"""NEXUS runtime composition root.

Registers only locally importable, side-effect-bounded services. Starting this
runtime does not launch miners, unlock wallets, contact providers, or collect
blockchain data. Those actions remain explicit API/user operations.
"""
from __future__ import annotations

import importlib
import importlib.util
import sqlite3
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
        status = self.supervisor.status()
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


def _crypto_probe(module: Any) -> dict[str, Any]:
    engine = module.CryptoEngine()
    algorithms = engine.algorithms()
    if not algorithms:
        raise RuntimeError("no hashing algorithms available")
    return {"algorithms_available": len(algorithms),
            "sha256_self_test": engine.digest_hex("sha256", b"NEXUS") ==
            "".join(__import__("hashlib").sha256(b"NEXUS").hexdigest())}


def _math_probe(module: Any) -> dict[str, Any]:
    catalog = module.research_catalog()
    return {"research_catalog_entries": len(catalog.get("shortcuts", [])),
            "auto_apply": False}


def _integrations_probe(module: Any) -> dict[str, Any]:
    rows = module.connector_status(env={})
    return {"providers_catalogued": len(rows), "live_connections_verified": 0,
            "writes_enabled": False}


def _sha2_probe(module: Any) -> dict[str, Any]:
    status = module.status()
    return {"package": status.get("package"),
            "package_present": status.get("present", False),
            "network_access": False, "miner_auto_apply": False}


def build_runtime(root: str | Path | None = None) -> LifecycleManager:
    """Build the NEXUS runtime graph; no service starts until start_all()."""
    base = Path(root or Path(__file__).resolve().parents[1]).resolve()
    manager = LifecycleManager()

    # Critical local cryptographic primitive layer.
    manager.register(ServiceSpec(
        name="crypto_engine",
        factory=lambda: ModuleAdapter("modules.crypto_engine.engine", _crypto_probe, "Crypto Engine"),
        critical=True,
    ))
    manager.register(ServiceSpec(
        name="math_intelligence",
        factory=lambda: ModuleAdapter("modules.math_intelligence", _math_probe, "Math Intelligence"),
        dependencies=("crypto_engine",), critical=False,
    ))
    manager.register(ServiceSpec(
        name="provider_registry",
        factory=lambda: ModuleAdapter("modules.integration_registry", _integrations_probe, "Provider Registry"),
        dependencies=("crypto_engine",), critical=False,
    ))
    if (base / "modules" / "sha2_research_service.py").is_file():
        manager.register(ServiceSpec(
            name="sha2_research",
            factory=lambda: ModuleAdapter("modules.sha2_research_service", _sha2_probe, "SHA-2 Research"),
            dependencies=("crypto_engine",), critical=False,
        ))
    if (base / "modules" / "wallet_benchmark" / "nexus_wallet_manager.py").is_file():
        manager.register(ServiceSpec(
            name="wallet_engine",
            factory=lambda: WalletReadOnlyAdapter(base),
            dependencies=("crypto_engine",), critical=False,
        ))
    if (base / "mining" / "hybrid_supervisor.py").is_file():
        manager.register(ServiceSpec(
            name="mining_supervisor",
            factory=MiningSupervisorAdapter,
            dependencies=("crypto_engine",), critical=False,
        ))
    return manager


def runtime_status(manager: LifecycleManager) -> dict[str, Any]:
    """Return lifecycle state without starting or modifying any service."""
    return manager.snapshot()
