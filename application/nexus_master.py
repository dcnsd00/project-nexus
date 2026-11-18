from __future__ import annotations
from uuid import uuid4
from contextlib import asynccontextmanager
import json, os, platform, shutil, subprocess, sys
from pathlib import Path
from fastapi import HTTPException
from fastapi.responses import HTMLResponse
ROOT = Path(__file__).resolve().parent
CORE = ROOT / "core" / "PROJECT-NEXUS-LOCAL"

def _package_version() -> str:
    """Return the authoritative package version from VERSION.json."""
    try:
        metadata = json.loads((ROOT / "VERSION.json").read_text(encoding="utf-8"))
        version = metadata.get("version")
        if isinstance(version, str) and version.strip():
            return version.strip()
    except (OSError, json.JSONDecodeError, AttributeError):
        pass
    return "unknown"
sys.path.insert(0, str(CORE))
sys.path.insert(0, str(ROOT / "modules" / "wallet_benchmark"))
from app.main import app  # noqa: E402
from nexus_wallet_manager import router as wallet_router, initialize_schema as initialize_wallet_schema  # noqa: E402
app.include_router(wallet_router)
# Extend the core FastAPI lifespan with a non-destructive wallet schema migration.
# Existing encrypted rows are preserved; no vault is unlocked or decrypted.
_core_lifespan = app.router.lifespan_context
@asynccontextmanager
async def _nexus_lifespan(application):
    async with _core_lifespan(application):
        from nexus_edge.topology import topology_from_env
        # Validate the declared deployment shape before any network adapter
        # starts. This validates configuration only; it does not provision HA.
        application.state.nexus_topology = topology_from_env(dict(os.environ))
        initialize_wallet_schema()
        # Start the safe, local-only NEXUS service graph. Optional service
        # failures remain visible without taking down independent services.
        import asyncio
        runtime_manager = build_runtime(ROOT)
        await asyncio.to_thread(runtime_manager.start_all)
        application.state.nexus_runtime = runtime_manager
        # Both network adapters must use the exact manager owned by the
        # LifecycleManager service. Independent managers pointed at the same
        # SQLite file would keep divergent in-memory snapshots and overwrite
        # each other's state.
        shared_edge_manager = None
        if _edge_transport.enabled() or _edge_gateway_runtime.enabled():
            try:
                edge_adapter = runtime_manager.get_service_instance("edge_manager")
                shared_edge_manager = edge_adapter.service.manager
            except Exception as exc:
                if _edge_transport.enabled():
                    _edge_transport.set_start_error(type(exc).__name__)
                if _edge_gateway_runtime.enabled():
                    _edge_gateway_runtime.set_start_error(type(exc).__name__)

        if _edge_transport.enabled():
            try:
                if shared_edge_manager is None:
                    raise RuntimeError("shared LifecycleManager EDGE service is unavailable")
                await asyncio.to_thread(_edge_transport.start, shared_edge_manager)
            except Exception as exc:
                _edge_transport.set_start_error(type(exc).__name__)
        if _edge_gateway_runtime.enabled():
            try:
                if shared_edge_manager is None:
                    raise RuntimeError("shared LifecycleManager EDGE service is unavailable")
                await asyncio.to_thread(
                    _edge_gateway_runtime.start, application, shared_edge_manager
                )
            except Exception as exc:
                _edge_gateway_runtime.set_start_error(type(exc).__name__)
        application.state.edge_transport = _edge_transport
        application.state.edge_gateway = _edge_gateway_runtime
        try:
            yield
        finally:
            # A failed optional network adapter must not prevent cleanup of
            # the other adapter or the core LifecycleManager services.
            try:
                await asyncio.to_thread(_edge_gateway_runtime.stop, application)
            except Exception as exc:
                _edge_gateway_runtime.set_start_error(type(exc).__name__)
            try:
                await asyncio.to_thread(_edge_transport.stop)
            except Exception as exc:
                _edge_transport.set_start_error(type(exc).__name__)
            try:
                await asyncio.to_thread(runtime_manager.stop_all)
            finally:
                application.state.nexus_runtime = None
app.router.lifespan_context = _nexus_lifespan
from nexus_wallet_recovery_api import router as wallet_recovery_router  # noqa: E402
app.include_router(wallet_recovery_router)
from modules.earnings_intelligence import router as intel_router  # noqa: E402
app.include_router(intel_router)
from modules.integration_registry import router as integrations_router  # noqa: E402
app.include_router(integrations_router)
from modules.pool_failover_api import router as pool_failover_router  # noqa: E402
app.include_router(pool_failover_router)
from tools_audit_vault import audit as audit_wallet_vault  # noqa: E402

# NEXUS EDGE transport runtime: strictly opt-in; no broker connection by default.
from nexus_edge.runtime import EdgeTransportRuntime  # noqa: E402
from nexus_edge.gateway_runtime import EdgeGatewayRuntime  # noqa: E402
_edge_transport = EdgeTransportRuntime()
_edge_gateway_runtime = EdgeGatewayRuntime()

@app.get("/api/edge/transports")
def edge_transport_status():
    return _edge_transport.status()

@app.get("/api/edge/gateway")
def edge_gateway_status():
    return _edge_gateway_runtime.status()

def _edge_manager_for_status():
    runtime_manager = getattr(app.state, "nexus_runtime", None)
    if runtime_manager is None:
        return None
    try:
        adapter = runtime_manager.get_service_instance("edge_manager")
        return adapter.service.manager
    except Exception:
        return None


@app.get("/api/edge/nodes")
def edge_nodes_status():
    manager = _edge_manager_for_status()
    if manager is None:
        return {"state": "not_started", "nodes": []}
    return {"state": "available", "nodes": manager.list_nodes()}


@app.get("/api/edge/tasks")
def edge_tasks_status():
    manager = _edge_manager_for_status()
    if manager is None:
        return {"state": "not_started", "tasks": []}
    return {"state": "available", "tasks": manager.list_tasks()}


@app.get("/api/edge/telemetry")
def edge_telemetry_status(limit: int = 100):
    manager = _edge_manager_for_status()
    if manager is None:
        return {"state": "not_started", "events": []}
    try:
        return {"state": "available", "events": manager.telemetry(limit=limit)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=type(exc).__name__) from exc


@app.get("/api/edge/topology")
def edge_topology_status():
    topology = getattr(app.state, "nexus_topology", None)
    if topology is None:
        return {"state": "not_started", "configuration_validated": False,
                "operational_failover_verified": False}
    return {
        "state": "configuration_validated",
        "mode": topology.mode.value,
        "server_count": topology.server_count,
        "state_backend": topology.state_backend,
        "shared_state": topology.shared_state,
        "distributed_task_claims": topology.distributed_task_claims,
        "configuration_validated": True,
        "operational_failover_verified": False,
        "note": "Topology declaration is validated; failover and distributed claims are not provisioned or operationally verified.",
    }


def _tool(name: str) -> dict:
    path = shutil.which(name)
    return {"available": bool(path), "path": path}

def _nvidia() -> dict:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return {"available": False, "reason": "nvidia-smi not found in this runtime"}
    try:
        p = subprocess.run(
            [exe, "--query-gpu=name,memory.total,driver_version,temperature.gpu,power.draw",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5, check=True
        )
        rows = []
        for line in p.stdout.splitlines():
            vals = [x.strip() for x in line.split(",")]
            if len(vals) >= 5:
                rows.append({"name": vals[0], "memory_mib": vals[1], "driver": vals[2],
                             "temperature_c": vals[3], "power_w": vals[4]})
        return {"available": bool(rows), "gpus": rows}
    except Exception as exc:
        return {"available": False, "reason": type(exc).__name__}

@app.get("/api/nexus/master")
def nexus_master_manifest():
    return {
        "product": "NEXUS",
        "version": _package_version(),
        "architecture": "single control plane with separately versioned adapters",
        "modules": {
            "core": {"present": True, "runtime": "FastAPI + SQLite", "source": "core/PROJECT-NEXUS-LOCAL"},
            "wallet_lab": {"present": (ROOT/"modules"/"wallet_benchmark"/"nexus_recovery_lab.py").is_file(),
                           "runtime": "local cryptographic derivation and wallet format benchmark"},
            "blockchain_regtest": {"present": (ROOT/"modules"/"blockchain_regtest"/"nexus_v05_integration.py").is_file(),
                                   "runtime": "Bitcoin Core Regtest + Anvil local nodes; execution requires external daemons"},
            "multiminer_x": {"present": (ROOT/"adapters"/"multiminer_x"/"MULTIMINER_X_v1.0"/"app"/"miner_controller.py").is_file(),
                             "runtime": "XMRig CPU / SRBMiner GPU process controller"},
            "fieldstation": {"present": (ROOT/"adapters"/"fieldstation"/"crypto_fieldstation"/"app.py").is_file(),
                             "runtime": "Android/Termux edge client source"},
            "crypto_engine": {"present": (ROOT/"modules"/"crypto_engine"/"engine.py").is_file(),
                              "runtime": "hashlib SHA-2/SHA-3/BLAKE2/SHAKE + HMAC + experimental composite"},
            "coin_catalog": {"present": True, "runtime": "CoinPaprika full coin registry with local cache"},
            "pool_catalog": {"present": (ROOT/"mining"/"pools.json").is_file(), "runtime": "operator-documented coin/pool catalog, TCP/TLS/Stratum diagnostics, live Stratum V1 CPU worker with optional native C SHA-256d scanner and Python fallback, mining.submit, read-only payout connectors, solo pool profiles and guarded Bitcoin Core regtest"},
            "hybrid_mining_orchestrator": {"present": (ROOT/"mining"/"hybrid_orchestrator.py").is_file(), "runtime": "exclusive Standard/Development modes with isolated CPU/GPU workers, per-lane lifecycle, local PoW research and preflight planner"},
            "hybrid_supervisor": {"present": (ROOT/"mining"/"hybrid_supervisor.py").is_file(), "runtime": "separate OS worker processes; global exclusive mode; independent CPU/GPU stop; heartbeat and bounded shutdown"},
            "development_pow": {"present": (ROOT/"mining"/"development_pow.py").is_file(), "runtime": "local Regtest/Testnet SHA-256d research; no public-pool submission"},
            "hybrid_efficiency_optimizer": {"present": (ROOT/"modules"/"mining_efficiency_optimizer.py").is_file(), "runtime": "robust repeated-window scoring; manual review only; no auto-apply"},
            "desktop_shell": {"present": (ROOT/"START_NEXUS_DESKTOP.pyw").is_file(), "runtime": "pywebview + Edge WebView2 over the same local FastAPI control plane"},
            "mining_optimization_ledger": {"present": (ROOT/"modules"/"mining_optimization.py").is_file(), "runtime": "measured A/B hashrate, shares, power and temperature; no automatic tuning"},
            "sha256_research_lab": {"present": (ROOT/"modules"/"sha256_research"/"lab.py").is_file(), "runtime": "reduced-round differential, carry, multi-bit holdout hill-climb and SAT/CNF experiments; isolated from consensus mining"},
            "private_research_hub": {"present": (ROOT/"modules"/"research_hub.py").is_file(), "runtime": "local-only research shortcuts, bounded toy brute-force, truncated-hash collision lab, scheduler and executive summaries"},
            "earnings_intelligence": {"present": (ROOT/"modules"/"earnings_intelligence.py").is_file(), "runtime": "opportunity diligence, device inventory, telemetry, reward ledger, payout evidence, wallet watch and shadow scheduler"},
            "math_intelligence": {"present": (ROOT/"modules"/"math_intelligence.py").is_file(), "runtime": "SHA-2/SHA-3 exact benchmarks, modular congruence solver and measured candidate triage; manual review only"},
            "integrations": {"present": (ROOT/"modules"/"integration_registry.py").is_file(), "runtime": "12-provider read-only configuration registry; live API adapters pending provider-specific validation"},
            "sha2_research_package": {"present": (ROOT/"research"/"sha2_independent"/"nexus_sha"/"sha256_advanced.py").is_file(), "runtime": "independent SHA-256/SHA-512 research, differential/message-modification experiments, SAT/CNF, statistical analysis and exact benchmark; research-only, no miner auto-application"},
            "rcsc": {"present": (ROOT/"research"/"rcsc"/"nexus_rcsc"/"nexus_rcsc"/"collector.py").is_file(), "runtime": "read-only Bitcoin block collection, header SHA256d/PoW verification, full TXID Merkle reconstruction, fee extraction, SQLite persistence and chronological holdout research"},
            "edge_manager": {"present": (ROOT/"nexus_edge"/"gateway.py").is_file(), "runtime": "HMAC-authenticated node control plane, encrypted SQLite state, persistent anti-replay, opt-in HTTPS gateway and MQTTS uplink adapter; single-host pilot, physical-node and external network-server validation pending"}
        },
        "wallet_manager": {"present": True, "encrypted_local_evm_vault": True, "watch_only": True,
                           "local_wallet_search": True, "format_detection": True,
                           "bitcoin_encrypted_vault": True, "bip38_secure_import": True,
                           "recovery_formats_api": "/api/wallet/recovery/formats",
                           "recovery_search_api": "/api/wallet/recovery/search",
                           "web3_v3_import": True, "bip38_non_ec": True,
                           "bip39_checksum_and_one_missing": True,
                           "bitcoin_core_loopback_rpc": True,
                           "public_chain_broadcast": False},
        "provider_connectors_live": 0,
        "provider_connectors_configured": "see /api/integrations/status",
        "earnings_intelligence": {"execution": "shadow_only", "private_keys_accepted": False},
        "notes": ["Presence means source included, not that external accounts or services are connected.",
                  "Raw private keys are not returned by recovery endpoints; owner-supplied keys are kept in encrypted vaults.",
                  "NEXUS does not search public chains for dormant third-party wallets or attempt to obtain their keys."]
    }

@app.get("/api/nexus/readiness")
def nexus_readiness():
    tools = {x: _tool(x) for x in ("docker", "bitcoind", "bitcoin-cli", "anvil", "nvidia-smi")}
    return {
        "python": platform.python_version(),
        "os": platform.platform(),
        "logical_cpus": os.cpu_count(),
        "tools": tools,
        "ready_for_local_chain_benchmark": tools["docker"]["available"] and tools["bitcoind"]["available"] and tools["anvil"]["available"],
        "gpu_telemetry": _nvidia(),
        "public_chain_writes_enabled": False
    }

@app.get("/api/mining/profiles")
def mining_profiles():
    return json.loads((ROOT/"mining"/"profiles.json").read_text(encoding="utf-8"))

@app.get("/api/mining/hardware")
def mining_hardware():
    return {
        "cpu": {"logical_threads": os.cpu_count(), "model": platform.processor() or None},
        "gpu": _nvidia(),
        "miner_binaries": {
            "xmrig": _tool("xmrig"),
            "srbminer": _tool("SRBMiner-MULTI"),
        },
        "warning": "No miner is started by this endpoint. Hardware benchmark must be run locally."
    }

@app.get("/api/mining/native-engine")
def mining_native_engine_status():
    """Read-only status of the optional native SHA-256d C backend."""
    from mining.native_sha256d import native_status
    return native_status()

@app.get("/api/nexus/modules")
def nexus_modules():
    return {"wallet_lab":"source bundled; local tests required",
            "blockchain_regtest":"source bundled; daemons not assumed installed",
            "multiminer_x":"source bundled; external miners not bundled",
            "fieldstation":"source bundled; Android runtime not available in this process",
            "crypto_radar":"local opportunity registry and source snapshots; provider-specific ingestion adapters pending",
            "earnings_intelligence":"local opportunity/device/reward ledger and shadow scheduler; provider connectors not live",
            "integrations":"provider registry, configuration readiness and read-only capability declarations; live provider validation pending",
            "sha2_research":"independent SHA-256/SHA-512 reference, reduced-round research, SAT/CNF, statistics, benchmark and independent verification; research-only",
            "native_sha256d":"optional C SHA-256d scanner with exact nonce partitioning, AVX2/AVX-512 runtime dispatch and Python fallback; connected to internal Stratum worker"}

@app.get("/api/wallet/audit")
def wallet_vault_audit():
    """Read-only structural audit; never decrypts or modifies vault material."""
    wallet_db = Path(os.getenv("NEXUS_WALLET_DB", "./data/nexus_wallets.db"))
    return audit_wallet_vault(wallet_db)


@app.get("/wallet", response_class=HTMLResponse)
def wallet_page():
    return (ROOT / "wallet.html").read_text(encoding="utf-8")

# NEXUS 0.7.0 cryptographic primitives API
from pydantic import BaseModel, Field, ValidationError
from modules.crypto_engine import CryptoEngine, CryptoInputError, AlgorithmUnavailable
import base64

_crypto = CryptoEngine()

class CryptoHashRequest(BaseModel):
    algorithm: str = Field(min_length=1, max_length=64)
    data: str = Field(max_length=11_184_812)
    encoding: str = Field(default="utf-8", pattern="^(utf-8|hex|base64)$")
    output_bytes: int | None = Field(default=None, ge=1, le=4096)

class CryptoBenchmarkRequest(BaseModel):
    algorithm: str = Field(min_length=1, max_length=64)
    payload_bytes: int = Field(default=1024, ge=0, le=8*1024*1024)
    iterations: int = Field(default=1000, ge=1, le=1_000_000)
    output_bytes: int | None = Field(default=None, ge=1, le=4096)

@app.get("/api/crypto/algorithms")
def crypto_algorithms():
    return {"algorithms": _crypto.algorithms(), "consensus_warning": "Experimental composites are not compatible with existing blockchain consensus rules."}

@app.post("/api/crypto/hash")
def crypto_hash(req: CryptoHashRequest):
    try:
        if req.encoding == "hex":
            try: payload = bytes.fromhex(req.data)
            except ValueError as exc: raise CryptoInputError("invalid hex input") from exc
        elif req.encoding == "base64":
            try: payload = base64.b64decode(req.data, validate=True)
            except Exception as exc: raise CryptoInputError("invalid base64 input") from exc
        else:
            payload = req.data.encode("utf-8")
        result = _crypto.digest(req.algorithm, payload, req.output_bytes)
        return {"algorithm": req.algorithm.lower(), "digest_hex": result.hex(), "digest_bytes": len(result), "input_bytes": len(payload)}
    except CryptoInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except AlgorithmUnavailable as exc:
        raise HTTPException(status_code=501, detail=str(exc))

@app.post("/api/crypto/benchmark")
def crypto_benchmark(req: CryptoBenchmarkRequest):
    try:
        return _crypto.benchmark(req.algorithm, req.payload_bytes, req.iterations, req.output_bytes)
    except CryptoInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except AlgorithmUnavailable as exc:
        raise HTTPException(status_code=501, detail=str(exc))

# NEXUS 0.8.0: coin catalogue, pool selector and desktop dashboard
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from modules.coin_catalog import get_coins

@app.get("/api/mining/pools")
def mining_pools():
    return json.loads((ROOT/"mining"/"pools.json").read_text(encoding="utf-8"))

class PoolConfigRequest(BaseModel):
    pool_id: str = Field(min_length=1, max_length=80)
    wallet: str = Field(min_length=3, max_length=256)
    worker: str = Field(default="nexus-worker", min_length=1, max_length=64)
    password: str = Field(default="x", max_length=128)
    use_ssl: bool = False
    mining_mode: str = Field(default="POOL", pattern="^(POOL|SOLO_POOL)$")
    custom_host: str | None = Field(default=None, max_length=255)
    custom_port: int | None = Field(default=None, ge=1, le=65535)
    custom_algorithm: str | None = Field(default=None, max_length=80)
    miner_id: str | None = Field(default=None, max_length=32)
    device: str = Field(default="GPU", pattern="^(CPU|GPU|BOTH|ESP32|ASIC)$")

@app.post("/api/mining/config")
def mining_config(req: PoolConfigRequest):
    catalog=json.loads((ROOT/"mining"/"pools.json").read_text(encoding="utf-8"))
    pool=next((x for x in catalog["pools"] if x["id"]==req.pool_id),None)
    if not pool: raise HTTPException(status_code=404, detail="Pool not found")
    if str(pool.get('payout_status','')).lower() in ('paused','suspended','disabled'):
        raise HTTPException(status_code=409, detail=f"Payout-ul {pool.get('payout_asset',pool.get('coin'))} este suspendat de operator; job-ul nu poate fi pornit.")
    if pool.get('selectable') is False: raise HTTPException(status_code=409, detail="Profilul este informativ și nu poate fi folosit pentru pornire.")
    if req.mining_mode == "SOLO_POOL" and "SOLO" not in str(pool.get("mode", "")).upper():
        raise HTTPException(status_code=400, detail="Pool-ul selectat nu declară suport SOLO în catalog.")
    custom = pool.get("id") == "custom"
    host,port=(req.custom_host,req.custom_port) if custom else pool_endpoint(pool,req.use_ssl)
    algo=(req.custom_algorithm if custom else pool.get("algorithm"))
    if custom and not algo: raise HTTPException(status_code=400, detail="Pentru pool Custom trebuie completat algoritmul.")
    if not host or not port: raise HTTPException(status_code=400, detail="Pool host/port must be configured")
    if req.use_ssl and not (req.custom_port or pool.get("ssl_port")):
        raise HTTPException(status_code=400,detail="Nu există port TLS confirmat pentru acest pool.")
    if not custom and algo != pool.get("algorithm"):
        raise HTTPException(status_code=400,detail=f"Algoritmul nu poate fi suprascris: pool-ul cere {pool.get('algorithm')}.")
    compatibility=None
    if req.miner_id:
        compatibility=_compatibility(pool,req.miner_id,req.device)
        if not compatibility["compatible"]:
            raise HTTPException(status_code=400,detail="Incompatibilitate: " + " ".join(compatibility["reasons"]))
    # Config generation only; no mining process is started by this API.
    protocol = pool.get("tls_scheme", "ssl") if req.use_ssl else "tcp"
    url = f"stratum+{protocol}://{host}:{int(port)}"
    solo_profile = None
    if req.mining_mode == "SOLO_POOL":
        from mining.solo_profiles import build_solo_pool_profile
        try: solo_profile = build_solo_pool_profile(pool, req.wallet, req.worker, req.password, req.use_ssl)
        except ValueError as exc: raise HTTPException(status_code=400, detail=str(exc))
    worker_format = pool.get("worker_format", "WALLET.worker")
    pool_login = pool_username(pool,req.wallet,req.worker)
    external_cfg = None
    if req.miner_id in ("nerdminer", "asic"):
        external_cfg = {"device": "NerdMiner ESP32" if req.miner_id == "nerdminer" else "ASIC extern",
                        "stratum_host": host, "stratum_port": int(port),
                        "username": (solo_profile or {}).get("username", pool_login),
                        "password": req.password, "tls": req.use_ssl,
                        "solo": req.mining_mode == "SOLO_POOL", "worker_format": worker_format,
                        "instructions": "Aplică manual aceste setări în firmware/interfața dispozitivului. NEXUS nu pornește hardware extern."}
    return {"pool":pool["name"],"pool_id":pool["id"],"coin":pool["coin"],"mined_asset":pool.get("mined_asset",pool["coin"]),
            "payout_asset":pool.get("payout_asset",pool["coin"]),"payout_status":pool.get('payout_status','active'),"algorithm":algo,"url":url,"host":host,"port":int(port),
            "ssl_port":pool.get("ssl_port"),"tls":req.use_ssl,"wallet":req.wallet,"worker":req.worker,
            "wallet_worker":(solo_profile or {}).get("username",pool_login),"worker_format":worker_format,
            "password":req.password,"miner":req.miner_id,"device":req.device,"mining_mode":req.mining_mode,
            "pool_mode":("SOLO" if req.mining_mode == "SOLO_POOL" else pool.get("mode")),"compatibility":compatibility,
            "execution":"not_started","pool_account_api_available":pool.get("account_connector") in ("2miners_public_api","unmineable_signed_read_api","kryptex_public_api","braiins_read_api"),
            "solo_settings":solo_profile,"external_device_config":external_cfg,
            "backup_ports":pool.get("backup_ports",[]),"backup_hosts":pool.get("backup_hosts",[]),
            "fee_note":pool.get("solo_fee_note") if solo_profile else pool.get("fee_note"),
            "command_preview":(["--algorithm",algo,"--pool",url,"--wallet",pool_login,"--password",req.password,"--disable-cpu"] if req.miner_id=="srbminer" and req.device=="GPU" else None),
            "warning":"Configurația a fost generată din catalogul selectat; nu pornește minerul. Host/port/algoritm nu pot fi suprascrise pentru pool-urile catalogate."}

@app.get("/api/coins/catalog")
def coin_catalog(refresh: bool=False, q: str="", limit: int=100):
    try:
        data=get_coins(force=refresh)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Coin catalog unavailable: {type(exc).__name__}")
    coins=data["coins"]
    if q:
        needle=q.casefold()
        coins=[c for c in coins if needle in str(c.get("name","")).casefold() or needle in str(c.get("symbol","")).casefold() or needle in str(c.get("id","")).casefold()]
    return {"source":data["source"],"cached":data["cached"],"stale":data.get("stale",False),
            "fallback":data.get("fallback",False),"age_seconds":data.get("age_seconds"),
            "warning":data.get("warning"),"upstream_error":data.get("upstream_error"),
            "total_returned":len(coins),"coins":coins[:max(1,min(limit,500))],"limit":max(1,min(limit,500))}

# NEXUS live host telemetry: local measurements, bounded history, no synthetic values.
from modules.runtime_telemetry import RuntimeTelemetry  # noqa: E402
from modules.blockchain_node_telemetry import bitcoin_node_snapshot  # noqa: E402
from modules.evm_node_telemetry import evm_node_snapshot  # noqa: E402
_runtime_telemetry = RuntimeTelemetry()

@app.get("/api/nexus/telemetry")
def nexus_runtime_telemetry(history: int = 120, sample: bool = True):
    try:
        return _runtime_telemetry.snapshot_with_history(history, sample=sample)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Telemetry unavailable: {type(exc).__name__}")

@app.get("/api/blockchain/nodes/bitcoin")
def bitcoin_node_telemetry():
    """Read-only, loopback-only Bitcoin Core node telemetry."""
    return bitcoin_node_snapshot()


@app.get("/api/blockchain/nodes/evm")
def evm_node_telemetry():
    """Read-only EVM JSON-RPC telemetry; endpoint must be explicitly configured."""
    return evm_node_snapshot()


@app.get("/api/nexus/dashboard", response_class=HTMLResponse)
def nexus_dashboard():
    return (ROOT/"dashboard.html").read_text(encoding="utf-8")

# NEXUS 0.9.1: supervised mining process control and live diagnostics
from modules import __path__ as _modules_path  # noqa: E402
from mining import controller as mining_controller  # noqa: E402
from mining import installer as mining_installer  # noqa: E402
from mining.hybrid_orchestrator import build_hybrid_plan  # noqa: E402
from mining.hybrid_supervisor import HybridSupervisor  # noqa: E402
from modules.mining_switch_controller import (evaluate_candidate, switch_if_approved, DEFAULT_POLICY as MINING_SWITCH_DEFAULT_POLICY, load_switch_state, record_active_configuration, record_successful_switch, source_adapter_status)  # noqa: E402
from mining.development_pow import define_experiment  # noqa: E402
from mining.randomx_benchmark import run_thread_sweep as run_randomx_thread_sweep, run_native_reference_benchmark, run_synthetic_blocks_benchmark as run_randomx_synthetic_blocks_benchmark  # noqa: E402
from modules.mining_efficiency_optimizer import rank_candidates as rank_mining_candidates  # noqa: E402
from mining.hybrid_safety import validate_engine_resources  # noqa: E402
hybrid_supervisor = HybridSupervisor()
from mining.solo_bitcoin_rpc import BitcoinRPC, SoloRPCError, benchmark_sha256d, mine_regtest_block  # noqa: E402

class MinerStartRequest(BaseModel):
    miner_id: str = Field(min_length=2, max_length=32)
    pool_id: str = Field(min_length=1, max_length=80)
    wallet: str = Field(min_length=3, max_length=256)
    worker: str = Field(default="nexus-worker", min_length=1, max_length=64)
    password: str = Field(default="x", max_length=128)
    algorithm: str | None = Field(default=None, max_length=80)
    device: str = Field(default="GPU", pattern="^(CPU|GPU|BOTH|ESP32|ASIC)$")
    use_ssl: bool = False
    custom_host: str | None = Field(default=None, max_length=253)
    custom_port: int | None = Field(default=None, ge=1, le=65535)
    binary_path: str | None = Field(default=None, max_length=1024)
    mining_mode: str = Field(default="POOL", pattern="^(POOL|SOLO_POOL)$")

@app.get("/api/mining/miners")
def mining_miners():
    return mining_controller.inventory()

@app.post("/api/mining/start")
def mining_start(req: MinerStartRequest):
    try:
        catalog=json.loads((ROOT/"mining"/"pools.json").read_text(encoding="utf-8"))
        pool=next((x for x in catalog["pools"] if x["id"]==req.pool_id),None)
        if not pool:
            raise HTTPException(status_code=404, detail="Pool-ul nu există în catalog.")
        if req.mining_mode == "SOLO_POOL" and "SOLO" not in str(pool.get("mode", "")).upper():
            raise HTTPException(status_code=400, detail="Pool-ul nu are mod SOLO confirmat în catalog.")
        if pool.get('id') == 'custom':
            effective_host=req.custom_host; effective_port=req.custom_port
        else:
            effective_host,effective_port=pool_endpoint(pool,req.use_ssl)
        if not effective_host or not effective_port:
            raise HTTPException(status_code=400,detail="Host/port pool lipsă.")
        gate=_compatibility(pool,req.miner_id,req.device)
        if not gate.get("compatible"):
            raise HTTPException(status_code=400,detail="START blocat de verificarea de compatibilitate: "+" ".join(gate.get("reasons",[])))
        return mining_controller.start(req.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@app.post("/api/mining/stop")
def mining_stop():
    try:
        return mining_controller.stop()
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.get("/api/mining/solo-readiness")
def mining_solo_readiness(pool_id: str | None = None):
    catalog=json.loads((ROOT/"mining"/"pools.json").read_text(encoding="utf-8"))
    eligible=[{"id":p["id"],"pool":p["pool"],"coin":p["coin"],"algorithm":p["algorithm"],"host":p.get("host"),"port":p.get("port"),"ssl_port":p.get("ssl_port"),"backup_ports":p.get("backup_ports",[]),"share_difficulty_default":p.get("share_difficulty_default"),"mode":p.get("mode"),"worker_format":p.get("worker_format"),"device_class":p.get("device_class",[]),"source":p.get("source")} for p in catalog["pools"] if "SOLO" in str(p.get("mode", "")).upper()]
    selected=next((p for p in eligible if p["id"]==pool_id),None) if pool_id else None
    from shutil import which
    bitcoind = which("bitcoind")
    return {"solo_pool_available":bool(eligible),"eligible_pools":eligible,"selected":selected,
            "local_node_solo":{"ready":False,"daemon_detected":bool(bitcoind),"bitcoind_path":bitcoind,
                               "adapter":"Bitcoin Core JSON-RPC regtest CPU solo",
                               "network_policy":"loopback RPC; regtest only for NEXUS internal CPU miner",
                               "limitations":"Nu este disponibil până când daemonul și RPC-ul local nu sunt configurate. Template-urile cu mempool necesită un assembler complet; adaptorul actual e limitat la template gol.",
                               "asic_path":"ASIC -> local CKPool/Stratum bridge -> Bitcoin Core getblocktemplate/submitblock; instalare și testare separată."},
            "warning":"SOLO pool nu crește viteza hash-ului; schimbă varianța recompensei. Solo pe nod propriu este diferit de solo pool."}

class SoloRPCRequest(BaseModel):
    rpc_url: str = Field(default="http://127.0.0.1:18443", max_length=300)
    rpc_user: str | None = Field(default=None, max_length=128)
    rpc_password: str | None = Field(default=None, max_length=256)
    cookie_file: str | None = Field(default=None, max_length=1024)
    payout_script_hex: str = Field(min_length=2, max_length=20000)
    max_nonce_attempts: int = Field(default=5000000, ge=1, le=20000000)

@app.get("/api/mining/solo-rpc/benchmark")
def mining_solo_rpc_benchmark(iterations: int = 200000):
    return benchmark_sha256d(iterations)

@app.post("/api/mining/solo-rpc/mine-regtest")
def mining_solo_rpc_mine(req: SoloRPCRequest):
    try:
        rpc=BitcoinRPC(req.rpc_url, req.rpc_user, req.rpc_password, req.cookie_file)
        return mine_regtest_block(rpc, req.payout_script_hex, req.max_nonce_attempts)
    except SoloRPCError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@app.get("/api/mining/status")
def mining_status():
    return mining_controller.status()

@app.get("/api/mining/processes")
def mining_processes():
    return {"processes":mining_controller.active_processes(),"managed":mining_controller.status().get("pid")}

@app.get("/api/mining/diagnostics")
def mining_diagnostics():
    return mining_controller.diagnose()

@app.get("/api/mining/installers")
def mining_installers():
    return {"installers": mining_installer.list_sources(), "policy": "official_upstream_only; archive_path_safety; SHA-256; no automatic execution"}

@app.get("/api/mining/installers/{miner_id}/latest")
def mining_installer_latest(miner_id: str):
    try:
        return mining_installer.latest_release(miner_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Nu am putut verifica release-ul: {type(exc).__name__}: {exc}")

@app.post("/api/mining/installers/{miner_id}/install")
def mining_installer_install(miner_id: str):
    try:
        return mining_installer.install(miner_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Instalarea minerului a eșuat: {type(exc).__name__}: {exc}")


# NEXUS 0.9.3: SHA-256 differential and compression carry research
from datetime import datetime, timezone
from modules.sha256_research.lab import run_differential, run_round_sweep, run_multi_delta_sweep, run_compression_carry_differential, research_info

SHA_RESEARCH_RESULTS = ROOT / "modules" / "sha256_research" / "results"
SHA_RESEARCH_RESULTS.mkdir(parents=True, exist_ok=True)

class SHA256DifferentialRequest(BaseModel):
    rounds: int = Field(default=20, ge=1, le=64)
    samples: int = Field(default=2000, ge=100, le=20000)
    word: int = Field(default=14, ge=0, le=15)
    input_bit: int = Field(default=0, ge=0, le=31)
    seed: int | None = Field(default=None, ge=0, le=(2**64 - 1))

class SHA256SweepRequest(BaseModel):
    rounds: list[int] = Field(default_factory=lambda: list(range(4, 33)), min_length=1, max_length=29)
    samples: int = Field(default=2000, ge=100, le=20000)
    word: int = Field(default=14, ge=0, le=15)
    input_bit: int = Field(default=0, ge=0, le=31)
    seed: int | None = Field(default=None, ge=0, le=(2**64 - 1))

def _save_sha_research_result(result: dict, kind: str) -> dict:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "_" + uuid4().hex[:12]
    payload = {"run_id": run_id, "created_utc": datetime.now(timezone.utc).isoformat(), "kind": kind, "result": result}
    target = SHA_RESEARCH_RESULTS / f"{run_id}.json"
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"run_id": run_id, "saved_to": str(target.relative_to(ROOT)), "result": result}

@app.get("/api/research/sha256/info")
def sha256_research_info():
    return research_info()

@app.post("/api/research/sha256/differential")
def sha256_research_differential(req: SHA256DifferentialRequest):
    try:
        result = run_differential(req.rounds, req.samples, req.word, req.input_bit, req.seed)
        return _save_sha_research_result(result, "differential")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@app.post("/api/research/sha256/sweep")
def sha256_research_sweep(req: SHA256SweepRequest):
    try:
        result = run_round_sweep(req.rounds, req.samples, req.word, req.input_bit, req.seed)
        return _save_sha_research_result(result, "round_sweep")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

class SHA256MultiDeltaRequest(BaseModel):
    rounds: int = Field(default=20, ge=1, le=64)
    samples: int = Field(default=2000, ge=100, le=20000)
    seed: int | None = Field(default=None, ge=0, le=(2**64 - 1))

@app.post("/api/research/sha256/multi-delta")
def sha256_research_multi_delta(req: SHA256MultiDeltaRequest):
    try:
        result = run_multi_delta_sweep(req.rounds, req.samples, req.seed)
        return _save_sha_research_result(result, "multi_delta_sweep")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@app.get("/api/research/sha256/results")
def sha256_research_results(limit: int = 20):
    safe_limit = max(1, min(limit, 100))
    files = sorted(SHA_RESEARCH_RESULTS.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:safe_limit]
    rows = []
    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            rows.append({"run_id": data.get("run_id"), "created_utc": data.get("created_utc"), "kind": data.get("kind"), "file": path.name})
        except (OSError, json.JSONDecodeError):
            continue
    return {"count": len(rows), "results": rows}


class SHA256CarryRequest(BaseModel):
    rounds: int = Field(default=20, ge=1, le=64)
    samples: int = Field(default=2000, ge=100, le=20000)
    word: int = Field(default=14, ge=0, le=15)
    input_bit: int = Field(default=0, ge=0, le=31)
    seed: int | None = Field(default=None, ge=0, le=(2**64 - 1))

@app.post("/api/research/sha256/compression-carries")
def sha256_research_compression_carries(req: SHA256CarryRequest):
    try:
        result = run_compression_carry_differential(req.rounds, req.samples, req.word, req.input_bit, req.seed)
        return _save_sha_research_result(result, "compression_carry_differential")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

# NEXUS 0.10.1: bounded multi-bit differential search and SAT research
from modules.sha256_research.advanced import (
    advanced_research_info, search_differential, track_differential,
    sat_selfcheck, solve_reduced_collision, export_dimacs,
)

class SHAAdvancedSearchRequest(BaseModel):
    rounds: int = Field(default=20, ge=1, le=64)
    steps: int = Field(default=60, ge=1, le=120)
    samples: int = Field(default=16, ge=8, le=96)
    restarts: int = Field(default=2, ge=1, le=3)
    validation_samples: int = Field(default=64, ge=16, le=1024)
    seed: int = Field(default=20261109, ge=0, le=(2**64 - 1))
    allowed_words: list[int] = Field(default_factory=lambda: [14, 15], min_length=1, max_length=16)

class SHAAdvancedTrackRequest(BaseModel):
    rounds: int = Field(default=20, ge=1, le=64)
    samples: int = Field(default=256, ge=16, le=4096)
    delta_words: list[int] = Field(min_length=16, max_length=16)
    seed: int = Field(default=20261109, ge=0, le=(2**64 - 1))

class SHASATSelfcheckRequest(BaseModel):
    rounds: int = Field(default=12, ge=1, le=24)
    seed: int = Field(default=1234, ge=0, le=(2**64 - 1))

class SHASATSolveRequest(BaseModel):
    rounds: int = Field(default=12, ge=1, le=24)
    bits: int = Field(default=32, ge=1, le=256)
    timeout_seconds: int = Field(default=10, ge=1, le=30)
    delta_words: list[int] | None = Field(default=None, min_length=16, max_length=16)

class SHASATDimacsRequest(BaseModel):
    rounds: int = Field(default=12, ge=1, le=24)
    bits: int = Field(default=32, ge=1, le=256)
    delta_words: list[int] | None = Field(default=None, min_length=16, max_length=16)

@app.get("/api/research/sha256/advanced/info")
def sha256_research_advanced_info():
    return advanced_research_info()

@app.post("/api/research/sha256/advanced/search")
def sha256_research_advanced_search(req: SHAAdvancedSearchRequest):
    try:
        result = search_differential(req.rounds, req.steps, req.samples, req.restarts, req.validation_samples, req.seed, req.allowed_words)
        return _save_sha_research_result(result, "advanced_multi_bit_hill_climb")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@app.post("/api/research/sha256/advanced/track")
def sha256_research_advanced_track(req: SHAAdvancedTrackRequest):
    try:
        result = track_differential(req.delta_words, req.rounds, req.samples, req.seed)
        return _save_sha_research_result(result, "advanced_multi_bit_track")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@app.post("/api/research/sha256/sat/selfcheck")
def sha256_research_sat_selfcheck(req: SHASATSelfcheckRequest):
    try:
        result = sat_selfcheck(req.rounds, req.seed)
        return _save_sha_research_result(result, "sat_cnf_selfcheck")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@app.post("/api/research/sha256/sat/solve")
def sha256_research_sat_solve(req: SHASATSolveRequest):
    try:
        result = solve_reduced_collision(req.rounds, req.bits, req.timeout_seconds, req.delta_words)
        return _save_sha_research_result(result, "sat_reduced_round_collision")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=501, detail=str(exc))

@app.post("/api/research/sha256/sat/dimacs")
def sha256_research_sat_dimacs(req: SHASATDimacsRequest):
    try:
        result = export_dimacs(req.rounds, req.bits, SHA_RESEARCH_RESULTS, req.delta_words)
        return _save_sha_research_result(result, "sat_dimacs_export")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

# NEXUS 0.9.4: compatibility gate, consolidated dashboard and measurable A/B ledger
from modules.mining_optimization import record_trial as record_mining_trial, list_trials as list_mining_trials

def _compatibility(pool: dict, miner_id: str, device: str) -> dict:
    spec=mining_controller.MINERS.get(miner_id)
    if not spec:
        return {"compatible":False,"reasons":["Miner necunoscut."]}
    reasons=[]
    algo=pool.get("algorithm")
    if algo not in spec.get("algorithms",[]): reasons.append(f"Algoritmul {algo} nu este în lista suportată de {spec['name']}.")
    if device not in spec.get("device",[]): reasons.append(f"Dispozitivul {device} nu este suportat de {spec['name']}.")
    if algo=='RandomX' and device not in ('CPU','BOTH'): reasons.append('RandomX este limitat la CPU; GPU nu este permis.')
    if algo=='SHA-256d' and device in ('GPU','BOTH'): reasons.append('Bitcoin SHA-256d nu este configurat pentru GPU consumer; folosește ASIC sau NerdMiner extern.')
    alias={"xmrig":"xmrig","srbminer":"srbminer","trex":"t-rex","lolminer":"lolminer","gminer":"gminer","rigel":"rigel","teamredminer":"teamredminer","bzminer":"bzminer"}.get(miner_id,miner_id)
    if miner_id!='nexus-btc-cpu' and pool.get("id") != "custom" and not spec.get('external_device') and alias not in str(pool.get("miner","")).casefold(): reasons.append("Minerul nu este listat de catalogul acestui pool.")
    if spec.get('external_device') and device not in (pool.get('device_class') or []): reasons.append(f"Pool-ul nu declară compatibilitatea cu dispozitivul extern {device}.")
    binary=mining_controller._resolve_binary(miner_id)
    if not binary and not spec.get('external_device') and not spec.get('internal'): reasons.append("Executabilul minerului nu este instalat/detectat.")
    if miner_id=="nexus-btc-cpu":
        if pool.get('coin')!='BTC' or algo!='SHA-256d' or device!='CPU' or str(pool.get('stratum_protocol','')).upper()!='V1':
            reasons.append('Motorul intern NEXUS necesită BTC / SHA-256d / CPU / Stratum V1.')
    if miner_id=="xmrig" and (algo!="RandomX" or device!="CPU"): reasons.append("XMRig în NEXUS este limitat la RandomX pe CPU.")
    gpu_info=None; dag_info=None
    if device in ("GPU","BOTH"):
        hw=_nvidia()
        if not hw.get("available"):
            reasons.append("Nu a fost detectat un GPU NVIDIA pentru modul GPU.")
        else:
            gpu_info=(hw.get("gpus") or [{}])[0]
            dag_file=ROOT/"mining"/"dag_requirements.json"
            try: dag_catalog=json.loads(dag_file.read_text(encoding="utf-8"))
            except Exception: dag_catalog={"requirements_mib":{}}
            dag_info=dag_catalog.get("requirements_mib",{}).get(algo)
            if dag_info:
                try: vram=int(float(gpu_info.get("memory_mib")))
                except (TypeError,ValueError): vram=0
                required=int(dag_info["dag_mib"])
                # 256 MiB runtime margin beyond DAG itself.
                if vram < required+256:
                    reasons.append(f"VRAM insuficient: {gpu_info.get('name','GPU')} are {vram} MiB, dar {dag_info['coin']} {algo} cere aproximativ {required} MiB DAG + 256 MiB rezervă. Mining GPU blocat pentru a evita eșecul DAG.")
    return {"compatible":not reasons,"miner_id":miner_id,"miner":spec["name"],"coin":pool.get("coin"),"algorithm":algo,"device":device,"binary":binary,"gpu":gpu_info,"dag_requirement":dag_info,"reasons":reasons,
            "math_policy":"Doar optimizări cu ieșire identică și acceptare de pool pot fi candidate live; SHA-256 redus-round rămâne research-only."}

class CompatibilityRequest(BaseModel):
    pool_id: str = Field(min_length=1,max_length=80)
    miner_id: str = Field(min_length=2,max_length=32)
    device: str = Field(default="GPU",pattern="^(CPU|GPU|BOTH|ESP32|ASIC)$")

@app.post("/api/mining/compatibility")
def mining_compatibility(req: CompatibilityRequest):
    catalog=json.loads((ROOT/"mining"/"pools.json").read_text(encoding="utf-8"))
    pool=next((x for x in catalog["pools"] if x["id"]==req.pool_id),None)
    if not pool: raise HTTPException(status_code=404,detail="Pool-ul nu există.")
    return _compatibility(pool,req.miner_id,req.device)

class HybridPlanRequest(BaseModel):
    cpu_pool_id: str = Field(min_length=1, max_length=80)
    gpu_pool_id: str = Field(min_length=1, max_length=80)

@app.post("/api/mining/hybrid/plan")
def mining_hybrid_plan(req: HybridPlanRequest):
    """Preflight CPU RandomX + GPU algorithm plan; does not launch miners."""
    catalog=json.loads((ROOT/"mining"/"pools.json").read_text(encoding="utf-8"))
    try:
        return build_hybrid_plan(pools=catalog["pools"], inventory=mining_controller.inventory(),
                                 cpu_pool_id=req.cpu_pool_id, gpu_pool_id=req.gpu_pool_id,
                                 compatibility=_compatibility, hardware=mining_hardware())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

class HybridEngineLaunchRequest(BaseModel):
    binary_path: str = Field(min_length=1, max_length=1024)
    args: list[str] = Field(default_factory=list, max_length=80)
    miner_id: str = Field(min_length=2, max_length=32)
    pool_id: str = Field(min_length=1, max_length=80)
    algorithm: str = Field(min_length=2, max_length=80)


def _safe_float(value):
    try: return float(value)
    except (TypeError, ValueError): return None


def _hybrid_safe_request(data: dict, engine: str) -> dict:
    try:
        req = HybridEngineLaunchRequest(**data)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors())
    inventory = mining_controller.inventory().get("miners", [])
    allowed = {str(x.get("path")): x for x in inventory if x.get("available") and x.get("path")}
    binary = str(Path(req.binary_path).resolve())
    item = next((v for k, v in allowed.items() if str(Path(k).resolve()) == binary and v.get("id") == req.miner_id), None)
    if item is None:
        raise HTTPException(status_code=409, detail="backend_unavailable_or_not_in_inventory")
    catalog = json.loads((ROOT / "mining" / "pools.json").read_text(encoding="utf-8"))
    pool = next((x for x in catalog.get("pools", []) if x.get("id") == req.pool_id), None)
    if not pool:
        raise HTTPException(status_code=404, detail="pool_not_found")
    if pool.get("algorithm") != req.algorithm:
        raise HTTPException(status_code=400, detail="algorithm_pool_mismatch")
    gate = _compatibility(pool, req.miner_id, engine.upper())
    if not gate.get("compatible"):
        raise HTTPException(status_code=409, detail={"error": "miner_pool_incompatible", "reasons": gate.get("reasons", [])})
    if engine == "gpu":
        gpu_info = mining_hardware().get("gpu", {})
        first = (gpu_info.get("gpus") or [{}])[0]
        try:
            total_vram = float(first.get("memory_mib"))
        except (TypeError, ValueError):
            total_vram = None
        check = validate_engine_resources("gpu", {"available": gpu_info.get("available", False),
            "memory_total_mb": total_vram, "temperature_c": _safe_float(first.get("temperature_c"))},
            {"required_vram_mb": 0, "vram_margin_mb": 256, "max_temperature_c": 85})
        if not check["allowed"]:
            raise HTTPException(status_code=409, detail={"error": "gpu_resource_guard", "reasons": check["reasons"]})
    if len(req.args) > 80 or any(not isinstance(x, str) or len(x) > 512 for x in req.args):
        raise HTTPException(status_code=400, detail="invalid_miner_arguments")
    return {"command": [binary, *req.args], "miner_id": req.miner_id, "algorithm": req.algorithm, "coin": pool.get("coin"), "pool_id": pool.get("id")}


@app.post("/api/mining/mode/{mode}/start")
def hybrid_mode_start(mode: str):
    try:
        result = hybrid_supervisor.start_mode(mode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not result.get("started"):
        raise HTTPException(status_code=409, detail=result)
    return result


@app.post("/api/mining/mode/{mode}/stop")
def hybrid_mode_stop(mode: str):
    if mode not in {"standard", "development"}:
        raise HTTPException(status_code=400, detail="mode must be standard or development")
    result = hybrid_supervisor.stop_mode(mode)
    if not result.get("stopped"):
        raise HTTPException(status_code=409, detail=result)
    return result


@app.get("/api/mining/mode/status")
def hybrid_mode_status():
    return hybrid_supervisor.status()


@app.post("/api/mining/hybrid/start")
def hybrid_start(payload: dict):
    mode = str(payload.get("mode", "standard")).lower()
    plan = {}
    for engine in ("cpu", "gpu"):
        if engine in payload:
            if not isinstance(payload[engine], dict):
                raise HTTPException(status_code=422, detail=f"{engine} request must be an object")
            if mode == "development":
                if engine == "gpu":
                    raise HTTPException(status_code=409, detail="development_gpu_backend_unavailable")
                try:
                    exp = define_experiment(payload[engine].get("network", "regtest"), payload[engine].get("algorithm", "sha256d"))
                except ValueError as exc:
                    raise HTTPException(status_code=400, detail=str(exc))
                attempts = payload[engine].get("attempts", 100000)
                if not isinstance(attempts, int) or not 1 <= attempts <= 1000000:
                    raise HTTPException(status_code=400, detail="attempts must be an integer from 1 to 1000000")
                plan[engine] = {"executor": "development_pow", "network": exp["network"],
                                "algorithm": exp["algorithm"], "attempts": attempts}
            else:
                plan[engine] = _hybrid_safe_request(payload[engine], engine)
    try:
        result = hybrid_supervisor.start(plan, mode=mode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result.get("error") == "mode_conflict":
        raise HTTPException(status_code=409, detail=result)
    if result.get("started") and mode == "standard":
        for engine in result.get("started_engines", []):
            request = plan.get(engine, {})
            record_active_configuration(engine, request.get("coin"), request.get("algorithm"))
    return result


@app.post("/api/mining/hybrid/stop")
def hybrid_stop():
    result = hybrid_supervisor.stop()
    if not result.get("stopped"):
        raise HTTPException(status_code=409, detail=result)
    return result


@app.post("/api/mining/hybrid/engine/{engine}/start")
def hybrid_engine_start(engine: str, payload: dict):
    if engine not in {"cpu", "gpu"}:
        raise HTTPException(status_code=400, detail="engine must be cpu or gpu")
    mode = hybrid_supervisor.active_mode()
    if mode is None:
        raise HTTPException(status_code=409, detail="select a mining mode first")
    if mode == "development":
        if engine == "gpu":
            raise HTTPException(status_code=409, detail="development_gpu_backend_unavailable")
        try:
            exp = define_experiment(payload.get("network", "regtest"), payload.get("algorithm", "sha256d"))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        attempts = payload.get("attempts", 100000)
        if not isinstance(attempts, int) or not 1 <= attempts <= 1000000:
            raise HTTPException(status_code=400, detail="attempts must be an integer from 1 to 1000000")
        request = {"executor": "development_pow", "network": exp["network"],
                   "algorithm": exp["algorithm"], "attempts": attempts}
    else:
        request = _hybrid_safe_request(payload, engine)
    result = hybrid_supervisor.start({engine: request}, mode=mode)
    if not result.get("started"):
        raise HTTPException(status_code=409, detail=result)
    if mode == "standard":
        record_active_configuration(engine, request.get("coin"), request.get("algorithm"))
    return result


@app.post("/api/mining/hybrid/engine/{engine}/stop")
def hybrid_engine_stop(engine: str):
    if engine not in {"cpu", "gpu"}:
        raise HTTPException(status_code=400, detail="engine must be cpu or gpu")
    return hybrid_supervisor.stop(engine)


@app.post("/api/mining/hybrid/gpu/switch")
def hybrid_gpu_switch(payload: dict):
    if hybrid_supervisor.active_mode() == "development":
        raise HTTPException(status_code=409, detail="development_gpu_backend_unavailable")
    request = _hybrid_safe_request(payload, "gpu")
    result = hybrid_supervisor.switch_gpu(request)
    if not result.get("switched"):
        raise HTTPException(status_code=409, detail=result)
    return result



class MiningSwitchEvaluationRequest(BaseModel):
    current: dict
    candidate: dict
    state: dict = Field(default_factory=dict)
    policy: dict = Field(default_factory=dict)


@app.post("/api/mining/hybrid/engine/{engine}/switch/evaluate")
def hybrid_switch_evaluate(engine: str, payload: MiningSwitchEvaluationRequest):
    """Evaluate a source-backed candidate; this endpoint never changes a running worker."""
    if engine not in {"cpu", "gpu"}:
        raise HTTPException(status_code=400, detail="engine must be cpu or gpu")
    policy = {**MINING_SWITCH_DEFAULT_POLICY, **payload.policy}
    # Runtime configuration may disable automatic switching globally; request data
    # cannot enable it when the process-level setting is off.
    import os
    policy["auto_switch_enabled"] = (
        os.getenv("NEXUS_AUTO_SWITCH_ENABLED", "0").strip().lower() in {"1", "true", "yes"}
        and bool(payload.policy.get("auto_switch_enabled", False))
    )
    state = load_switch_state(engine)
    decision = evaluate_candidate(payload.current, payload.candidate, state, policy)
    return {"engine": engine, "decision": decision, "worker_changed": False,
            "execution": "evaluation_only", "requires_live_source_adapters": True}


@app.post("/api/mining/hybrid/engine/{engine}/switch/apply")
def hybrid_switch_apply(engine: str, payload: MiningSwitchEvaluationRequest):
    """Explicitly approved switch; disabled until live evidence adapters are validated."""
    if engine not in {"cpu", "gpu"}:
        raise HTTPException(status_code=400, detail="engine must be cpu or gpu")
    import os
    if os.getenv("NEXUS_AUTO_SWITCH_ENABLED", "0").strip().lower() not in {"1", "true", "yes"}:
        raise HTTPException(status_code=409, detail="mining_switch_globally_disabled")
    if payload.candidate.get("evidence_status") != "verified":
        raise HTTPException(status_code=409, detail="candidate_evidence_not_verified")
    source_status = source_adapter_status()
    if not source_status.get("verified"):
        raise HTTPException(status_code=409, detail={"error": "live_source_adapter_not_verified", "source_status": source_status})
    worker_config = payload.candidate.get("worker_config")
    if not isinstance(worker_config, dict):
        raise HTTPException(status_code=422, detail="worker_config_required")
    request = _hybrid_safe_request(worker_config, engine)
    candidate = {**payload.candidate, "worker_request": request}
    policy = {**MINING_SWITCH_DEFAULT_POLICY, **payload.policy, "auto_switch_enabled": True}
    result = switch_if_approved(hybrid_supervisor, engine, payload.current, candidate,
                                payload.state, policy)
    if not result["executed"]:
        raise HTTPException(status_code=409, detail=result)
    return result


@app.get("/api/mining/hybrid/status")
def hybrid_status():
    return hybrid_supervisor.status()


@app.post("/api/mining/randomx/20block-benchmark")
def randomx_twenty_block_benchmark(payload: dict):
    threads = payload.get("threads", 4)
    hashes_per_block = payload.get("hashes_per_block", 1000)
    if isinstance(threads, bool) or not isinstance(threads, int) or not 1 <= threads <= 64:
        raise HTTPException(status_code=400, detail="threads must be an integer from 1 to 64")
    if isinstance(hashes_per_block, bool) or not isinstance(hashes_per_block, int) or not 100 <= hashes_per_block <= 50000:
        raise HTTPException(status_code=400, detail="hashes_per_block must be an integer from 100 to 50000")
    return run_randomx_synthetic_blocks_benchmark(threads, hashes_per_block)


@app.post("/api/mining/randomx/reference-benchmark")
def randomx_reference_benchmark(payload: dict):
    threads = payload.get("threads", 4)
    mode = payload.get("mode", "fast")
    seed = payload.get("seed", 1)
    nonces = payload.get("nonces", 1000)
    if isinstance(threads, bool) or not isinstance(threads, int) or not 1 <= threads <= 256:
        raise HTTPException(status_code=400, detail="threads must be an integer from 1 to 256")
    if mode not in {"fast", "light"}:
        raise HTTPException(status_code=400, detail="mode must be fast or light")
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 2**32 - 1:
        raise HTTPException(status_code=400, detail="seed must be an unsigned 32-bit integer")
    if isinstance(nonces, bool) or not isinstance(nonces, int) or not 1 <= nonces <= 10000000:
        raise HTTPException(status_code=400, detail="nonces must be from 1 to 10000000")
    return run_native_reference_benchmark(threads, mode, seed, nonces)


@app.post("/api/mining/randomx/benchmark")
def randomx_benchmark(payload: dict):
    threads = payload.get("threads", [1, 2, 4])
    dataset = payload.get("dataset", "1M")
    if not isinstance(threads, list) or any(isinstance(x, bool) or not isinstance(x, int) or not 1 <= x <= 256 for x in threads):
        raise HTTPException(status_code=400, detail="threads must be an array of integers from 1 to 256")
    if not 1 <= len(threads) <= 8 or len(set(threads)) != len(threads):
        raise HTTPException(status_code=400, detail="threads must contain 1 to 8 unique values")
    if dataset not in {"1M", "10M"}:
        raise HTTPException(status_code=400, detail="dataset must be 1M or 10M")
    try:
        return run_randomx_thread_sweep(threads, dataset)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/mining/hybrid/optimize/plan")
def hybrid_optimize_plan(payload: dict):
    if not isinstance(payload.get("baseline", {}), dict) or not isinstance(payload.get("candidates", []), list) or not isinstance(payload.get("policy", {}), dict):
        raise HTTPException(status_code=422, detail="baseline and policy must be objects; candidates must be an array")
    result = rank_mining_candidates(payload.get("baseline", {}), payload.get("candidates", []), payload.get("policy", {}))
    return {**result, "mode": hybrid_supervisor.active_mode(), "execution": "recommendation_only"}


class PoolTestRequest(BaseModel):
    pool_id: str = Field(min_length=1,max_length=80)
    use_ssl: bool = False
    custom_host: str | None = Field(default=None,max_length=253)
    custom_port: int | None = Field(default=None,ge=1,le=65535)

@app.post("/api/mining/pool-test")
def mining_pool_test(req: PoolTestRequest):
    import socket, time
    catalog=json.loads((ROOT/"mining"/"pools.json").read_text(encoding="utf-8"))
    pool=next((x for x in catalog["pools"] if x["id"]==req.pool_id),None)
    if not pool: raise HTTPException(status_code=404,detail="Pool-ul nu există.")
    if pool.get('id') == 'custom':
        host=req.custom_host; port=req.custom_port
    else:
        host,port=pool_endpoint(pool,req.use_ssl)
    if not host or not port: raise HTTPException(status_code=400,detail="Host/port lipsă.")
    started=__import__('time').perf_counter()
    try:
        raw=socket.create_connection((host,int(port)),timeout=4)
        if req.use_ssl:
            import ssl
            with ssl.create_default_context().wrap_socket(raw,server_hostname=host): pass
        else:
            raw.close()
        return {"ok":True,"host":host,"port":int(port),"tls_requested":req.use_ssl,"tcp_reachable":True,"tls_handshake":bool(req.use_ssl),"latency_ms":round((__import__('time').perf_counter()-started)*1000,2),"scope":"TCP/TLS handshake only; does not authenticate Stratum or prove mining shares."}
    except Exception as exc:
        return {"ok":False,"host":host,"port":int(port),"tls_requested":req.use_ssl,"tcp_reachable":False,"error":type(exc).__name__,"detail":str(exc)[:240],"scope":"TCP/TLS handshake only; no miner was started."}

@app.get("/api/nexus/dashboard-data")
def nexus_dashboard_data():
    st=mining_controller.status(); inv=mining_controller.inventory(); hw=mining_hardware()
    active=inv.get("processes",[])
    managed={k:st.get(k) for k in ("status","pid","miner_id","miner_name","coin","algorithm","pool","started_at","last_error","last_exit_code")}
    metrics=st.get("metrics",{})
    return {"version":_package_version(),"hybrid":hybrid_supervisor.status(),"managed_miner":managed,"active_processes":active,"metrics":metrics,
            "hardware":hw,"pool_reported_coin_mined":metrics.get("pool_reported_coin_mined"),
            "pool_reported_payout":metrics.get("pool_reported_payout"),
            "earnings_status":"not_connected" if not metrics.get("pool_reported_coin_mined") else "pool_reported",
            "trials":list_mining_trials(10)}

class MiningTrialRequest(BaseModel):
    coin: str = Field(min_length=2,max_length=16)
    algorithm: str = Field(min_length=2,max_length=80)
    miner: str = Field(min_length=2,max_length=40)
    device: str = Field(pattern="^(CPU|GPU|BOTH|ESP32|ASIC)$")
    change_description: str = Field(min_length=3,max_length=300)
    duration_seconds: int = Field(ge=30,le=86400)
    baseline_hashrate_hs: float = Field(gt=0)
    candidate_hashrate_hs: float = Field(ge=0)
    baseline_accepted: int = Field(default=0,ge=0)
    baseline_rejected: int = Field(default=0,ge=0)
    candidate_accepted: int = Field(default=0,ge=0)
    candidate_rejected: int = Field(default=0,ge=0)
    baseline_gpu_temp_c: float | None = Field(default=None,ge=0,le=120)
    candidate_gpu_temp_c: float | None = Field(default=None,ge=0,le=120)
    baseline_power_w: float | None = Field(default=None,gt=0,le=2000)
    candidate_power_w: float | None = Field(default=None,gt=0,le=2000)
    math_module: str = Field(default="none",max_length=80)

@app.post("/api/mining/optimization-trials")
def mining_optimization_trial(req: MiningTrialRequest):
    try: return record_mining_trial(req.model_dump())
    except ValueError as exc: raise HTTPException(status_code=400,detail=str(exc))

@app.get("/api/mining/optimization-trials")
def mining_optimization_trials():
    return list_mining_trials()

@app.get("/api/mining/pool-account")
def mining_pool_account(pool_id: str, wallet: str):
    """Read-only 2Miners account snapshot; never requests wallet signing or secrets."""
    import urllib.parse, urllib.request
    catalog=json.loads((ROOT/"mining"/"pools.json").read_text(encoding="utf-8"))
    pool=next((x for x in catalog["pools"] if x["id"]==pool_id),None)
    if not pool: raise HTTPException(status_code=404,detail="Pool-ul nu există.")
    if pool.get("pool")!="2Miners": raise HTTPException(status_code=400,detail="Interogarea contului este activă doar pentru pool-urile 2Miners în acest milestone.")
    wallet=wallet.strip()
    if not wallet or len(wallet)>256 or any(ch.isspace() for ch in wallet): raise HTTPException(status_code=400,detail="Adresa publică de payout nu este validă.")
    coin=str(pool.get("coin","")).lower()
    decimals={"rvn":8,"kas":8,"etc":18}.get(coin)
    if decimals is None: raise HTTPException(status_code=400,detail="Conversia unităților acestui coin nu este configurată.")
    url=f"https://{coin}.2miners.com/api/accounts/{urllib.parse.quote(wallet,safe='')}"
    try:
        request=urllib.request.Request(url,headers={"User-Agent":"NEXUS-Control-Center/0.9.4","Accept":"application/json"})
        with urllib.request.urlopen(request,timeout=8) as response: data=json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=502,detail=f"API-ul pool-ului nu a putut fi citit: {type(exc).__name__}")
    stats=data.get("stats") or {}
    def amount(v):
        if not isinstance(v,(int,float)): return None
        return {"raw":v,"coin":v/(10**decimals),"unit":"smallest-unit converted using configured decimals"}
    return {"source":"2Miners account API","url":url,"pool":pool["name"],"coin":pool["coin"],"wallet":wallet,
            "current_hashrate_hs":data.get("currentHashrate"),"average_hashrate_hs":data.get("hashrate"),
            "balance":amount(stats.get("balance")),"immature":amount(stats.get("immature")),"paid":amount(stats.get("paid")),
            "reward_24h":amount(data.get("24hreward")),"workers_online":data.get("workersOnline"),"workers_total":data.get("workersTotal"),
            "payments_total":data.get("paymentsTotal"),"last_share_unix":stats.get("lastShare"),"raw_units_note":"Conversia folosește 8 zecimale pentru RVN/KAS și 18 pentru ETC; păstrăm și valoarea brută pentru audit.",
            "read_only":True}


# NEXUS 0.9.6: private research hub and actionable dashboard shortcuts
from modules import research_hub
from pydantic import BaseModel, Field

@app.get("/api/research/hub")
def research_hub_catalog():
    return research_hub.catalog()

@app.get("/api/research/hub/summary")
def research_hub_summary():
    return research_hub.executive_summary()

@app.get("/api/research/hub/history")
def research_hub_history(limit: int = 30):
    return research_hub.history(limit)

class ToyPowRequest(BaseModel):
    bits: int = Field(default=12, ge=8, le=20)
    max_attempts: int = Field(default=500000, ge=1, le=2000000)
    prefix: str = Field(default="NEXUS-LOCAL-LAB", min_length=1, max_length=64)

@app.post("/api/research/hub/toy-pow")
def research_hub_toy_pow(req: ToyPowRequest):
    try: return research_hub.run_toy_pow(req.bits, req.max_attempts, req.prefix)
    except ValueError as exc: raise HTTPException(status_code=400, detail=str(exc))

class ToyCollisionRequest(BaseModel):
    bits: int = Field(default=16, ge=8, le=20)
    max_attempts: int = Field(default=100000, ge=1, le=500000)

@app.post("/api/research/hub/toy-collision")
def research_hub_toy_collision(req: ToyCollisionRequest):
    try: return research_hub.run_toy_collision(req.bits, req.max_attempts)
    except ValueError as exc: raise HTTPException(status_code=400, detail=str(exc))

@app.post("/api/research/hub/run-suite")
def research_hub_run_suite():
    # Bounded, offline-only starter suite. Does not access wallets, pools or public chains.
    pow_result = research_hub.run_toy_pow(bits=12, max_attempts=250000)
    collision_result = research_hub.run_toy_collision(bits=12, max_attempts=50000)
    summary = research_hub.executive_summary()
    return {"suite":"NEXUS private starter research suite", "offline_only":True,
            "runs":[pow_result, collision_result], "summary":summary,
            "next_step":"Compare CPU/GPU implementations and add measured A/B only after correctness checks."}


# NEXUS 0.9.6: actionable Math Intelligence, SHA-512/SHA-3 exact benchmarks, modular solver and candidate triage
from modules import math_intelligence
from pydantic import BaseModel, Field

@app.get("/api/math-intelligence/catalog")
def math_intelligence_catalog():
    return math_intelligence.research_catalog()

class HashBenchRequest(BaseModel):
    algorithms: list[str] = Field(default_factory=lambda: ["sha256", "sha512", "sha3_256", "blake2b_256"])
    payload_bytes: int = Field(default=1024, ge=0, le=1048576)
    iterations: int = Field(default=2000, ge=10, le=200000)

@app.post("/api/math-intelligence/hash-benchmark")
def math_hash_benchmark(req: HashBenchRequest):
    try: return math_intelligence.hash_benchmark(req.algorithms, req.payload_bytes, req.iterations)
    except ValueError as exc: raise HTTPException(status_code=400, detail=str(exc))

class ModularSolveRequest(BaseModel):
    a: int; b: int; modulus: int = Field(ge=2, le=10**18)

@app.post("/api/math-intelligence/modular-solve")
def math_modular_solve(req: ModularSolveRequest):
    try: return math_intelligence.solve_modular_congruence(req.a, req.b, req.modulus)
    except ValueError as exc: raise HTTPException(status_code=400, detail=str(exc))

class CandidateTriageRequest(BaseModel):
    baseline_hashrate: float = Field(gt=0); candidate_hashrate: float = Field(ge=0)
    duration_seconds: int = Field(ge=0, le=86400)
    accepted_shares: int = Field(default=0, ge=0); rejected_shares: int = Field(default=0, ge=0)
    exact_equivalence_verified: bool = False; independent_runs: int = Field(default=0, ge=0, le=1000)

@app.post("/api/math-intelligence/triage")
def math_candidate_triage(req: CandidateTriageRequest):
    try: return math_intelligence.triage_candidate(req.model_dump())
    except ValueError as exc: raise HTTPException(status_code=400, detail=str(exc))


# NEXUS 0.10.2: full-standard hash avalanche diagnostics
from modules.sha_avalanche import avalanche_experiment, avalanche_catalog

class HashAvalancheRequest(BaseModel):
    algorithm: str = Field(default="sha512", min_length=1, max_length=32)
    samples: int = Field(default=256, ge=16, le=4096)
    payload_bytes: int = Field(default=64, ge=1, le=4096)
    seed: int = Field(default=20261109, ge=0, le=(2**64 - 1))

@app.get("/api/math-intelligence/avalanche/catalog")
def hash_avalanche_catalog():
    return avalanche_catalog()

@app.post("/api/math-intelligence/avalanche/run")
def hash_avalanche_run(req: HashAvalancheRequest):
    try:
        result = avalanche_experiment(req.algorithm, req.samples, req.payload_bytes, req.seed)
        return _save_sha_research_result(result, "full_standard_hash_avalanche")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# NEXUS 0.10.20 — independent SHA-256/SHA-512 research package integration.
from modules import sha2_research_service as sha2_service

@app.get("/api/research/sha2/status")
def sha2_research_status():
    return sha2_service.status()

@app.post("/api/research/sha2/selftest")
def sha2_research_selftest():
    return sha2_service.run_selftest()

class SHA2ResearchBenchmarkRequest(BaseModel):
    nonces: int = Field(default=2000, ge=100, le=10000)
    seed: int = Field(default=42, ge=0, le=(2**32 - 1))

@app.post("/api/research/sha2/benchmark")
def sha2_research_benchmark(req: SHA2ResearchBenchmarkRequest):
    try:
        return sha2_service.run_benchmark(req.nonces, req.seed)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

class SHA2ResearchAvalancheRequest(BaseModel):
    samples: int = Field(default=32, ge=1, le=128)
    seed: int = Field(default=42, ge=0, le=(2**32 - 1))

@app.post("/api/research/sha2/avalanche")
def sha2_research_avalanche(req: SHA2ResearchAvalancheRequest):
    try:
        return sha2_service.run_avalanche(req.seed, req.samples)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

class SHA2ResearchStatisticsRequest(BaseModel):
    samples: int = Field(default=2000, ge=100, le=10000)
    seed: int = Field(default=42, ge=0, le=(2**32 - 1))

@app.post("/api/research/sha2/statistics")
def sha2_research_statistics(req: SHA2ResearchStatisticsRequest):
    try:
        return sha2_service.run_statistics(req.seed, req.samples)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

class SHA2ResearchDifferentialRequest(BaseModel):
    rounds: list[int] = Field(default_factory=lambda: [3, 4], min_length=1, max_length=4)
    seed: int = Field(default=42, ge=0, le=(2**32 - 1))
    search_samples: int = Field(default=300, ge=50, le=1000)
    validation_samples: int = Field(default=2000, ge=100, le=5000)
    time_budget_seconds: float = Field(default=8.0, ge=0.5, le=20)

@app.post("/api/research/sha2/differential")
def sha2_research_differential(req: SHA2ResearchDifferentialRequest):
    try:
        return sha2_service.run_differential(req.rounds, req.seed, req.search_samples,
                                             req.validation_samples, req.time_budget_seconds)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

class SHA2ResearchMessageModificationRequest(BaseModel):
    samples: int = Field(default=1000, ge=100, le=10000)
    k_bits: int = Field(default=8, ge=1, le=16)
    seed: int = Field(default=42, ge=0, le=(2**32 - 1))

@app.post("/api/research/sha2/message-modification")
def sha2_research_message_modification(req: SHA2ResearchMessageModificationRequest):
    try:
        return sha2_service.run_message_modification(req.seed, req.samples, req.k_bits)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

class SHA2ResearchMessageModificationE2Request(BaseModel):
    rounds: int = Field(default=2, ge=2, le=3)
    n_learn: int = Field(default=500, ge=100, le=1000)
    n_test: int = Field(default=500, ge=100, le=1000)
    k_cond: int = Field(default=4, ge=1, le=8)
    seed: int = Field(default=42, ge=0, le=(2**32 - 1))

@app.post("/api/research/sha2/message-modification/e2")
def sha2_research_message_modification_e2(req: SHA2ResearchMessageModificationE2Request):
    try:
        return sha2_service.run_message_modification_e2(req.rounds, req.seed,
                                                        req.n_learn, req.n_test, req.k_cond)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

class SHA2ResearchSATRequest(BaseModel):
    rounds: int = Field(default=6, ge=2, le=16)
    seed: int = Field(default=42, ge=0, le=(2**32 - 1))

@app.post("/api/research/sha2/sat/solve")
def sha2_research_sat_solve(req: SHA2ResearchSATRequest):
    try:
        return sha2_service.run_sat_solve(req.rounds, req.seed)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except sha2_service.ResearchDependencyError as exc:
        raise HTTPException(status_code=501, detail=str(exc))

@app.post("/api/research/sha2/verify")
def sha2_research_verify():
    return sha2_service.run_verification()


# NEXUS 0.10.3 — Hybrid Solver Router, full coin/pool catalog, Stratum V1 probe and solo profiles.
from modules import hybrid_solver as hybrid_math
from mining.solo_profiles import build_solo_pool_profile, build_local_node_profile, SoloProfileError
from mining.stratum_probe import probe_stratum, StratumProbeError
from mining.stratum_session import probe_job as probe_stratum_job
from modules.pool_connectors import unmineable_account_stats, kryptex_account_stats, braiins_account_stats, connector_catalog
from modules import unmineable_catalog
from mining.pool_config import pool_endpoint, pool_username, pool_identity_label

@app.get("/api/mining/coins")
def mining_coins():
    path = ROOT / "mining" / "coins.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return {**data, "total": len(data.get("coins", [])),
            "mineable_count": sum(1 for c in data.get("coins", []) if c.get("pow_mineable"))}

@app.get("/api/staking/assets")
def staking_assets():
    data=json.loads((ROOT / "mining" / "asset_classes.json").read_text(encoding="utf-8"))
    return {"schema_version":data.get("schema_version"),"assets":data.get("staking_assets",[]),"read_only":True}

@app.get("/api/mining/merged-rewards")
def mining_merged_rewards():
    data=json.loads((ROOT / "mining" / "asset_classes.json").read_text(encoding="utf-8"))
    return {"schema_version":data.get("schema_version"),"assets":data.get("merged_mining_rewards",[])}

@app.get("/api/mining/unmineable/routes")
def unmineable_routes(asset: str | None = None):
    return unmineable_catalog.payout_routes(asset)

@app.get("/api/mining/unmineable/assets")
def unmineable_assets(refresh: bool = False):
    """Fetch public unMineable payout-asset metadata; no account key or secret required."""
    if not refresh:
        return {"provider":"unMineable","status":"cached_metadata_not_loaded","auth_required":False,
                "routes":unmineable_catalog.payout_routes().get("routes",[]),
                "refresh_endpoint":"/api/mining/unmineable/assets?refresh=true",
                "note":"Setează refresh=true pentru a interoga endpoint-ul oficial public /v1/meta/coin."}
    try:
        data=unmineable_catalog.public_asset_catalog(timeout=8.0)
        data["known_payout_routes"]=unmineable_catalog.payout_routes().get("routes",[])
        return data
    except Exception as exc:
        return {"provider":"unMineable","status":"live_metadata_unavailable","auth_required":False,
                "error":f"{type(exc).__name__}: {str(exc)[:180]}",
                "known_payout_routes":unmineable_catalog.payout_routes().get("routes",[]),
                "warning":"Nu s-a înlocuit catalogul cu o listă goală. Activele necitite rămân UNKNOWN, nu inactive."}

@app.get("/api/mining/pool-connectors")
def mining_pool_connectors():
    return {"connectors": connector_catalog(), "private_keys_required": False,
            "read_only": True, "provider_auth_is_request_scoped": True}

@app.get("/api/mining/catalog-audit")
def mining_catalog_audit():
    data = json.loads((ROOT / "mining" / "pools.json").read_text(encoding="utf-8"))
    pools = data.get("pools", [])
    ids = [p.get("id") for p in pools]
    duplicates = sorted({v for v in ids if ids.count(v) > 1})
    missing = [p.get("id") for p in pools if p.get("id") != "custom" and (not p.get("host") or not p.get("port") or not p.get("algorithm") or not p.get("source"))]
    solo = [p.get("id") for p in pools if "SOLO" in str(p.get("mode", "")).upper()]
    unsupported_solo_metadata = [p.get("id") for p in pools if p.get("id") in solo and not p.get("worker_format")]
    return {"schema_version": data.get("schema_version"), "pool_count": len(pools),
            "coin_count": len({p.get("coin") for p in pools}), "duplicate_ids": duplicates,
            "missing_required_fields": missing, "solo_pool_count": len(solo),
            "solo_pool_ids": solo, "solo_missing_worker_format": unsupported_solo_metadata,
            "catalog_source_note": data.get("note"), "live_reachability_checked": False,
            "interpretation": "Audit structural only. Run TCP/TLS/Stratum probe per endpoint; endpoint listing is not proof of live service or accepted shares."}

@app.get("/api/mining/solo-profiles")
def mining_solo_profiles():
    data = json.loads((ROOT / "mining" / "pools.json").read_text(encoding="utf-8"))
    pools = []
    for p in data.get("pools", []):
        if "SOLO" in str(p.get("mode", "")).upper():
            pools.append({"id":p["id"],"operator":p["pool"],"coin":p["coin"],"algorithm":p["algorithm"],
                          "host":p.get("host"),"port":p.get("port"),"ssl_host":p.get("ssl_host"),"ssl_port":p.get("ssl_port"),
                          "backup_hosts":p.get("backup_hosts",[]),"backup_ports":p.get("backup_ports",[]),
                          "backup_ssl_ports":p.get("backup_ssl_ports",[]),"worker_format":p.get("worker_format"),
                          "solo_requires_account_mode":bool(p.get("solo_requires_account_mode",False)),"solo_mode_note":p.get("solo_mode_note"),
                          "auth_type":p.get("auth_type","wallet"),"share_difficulty_default":p.get("share_difficulty_default"),
                          "share_difficulty_high":p.get("share_difficulty_high"),"min_payout":p.get("min_payout"),
                          "fee_note":p.get("solo_fee_note") or p.get("fee_note"),"payout_rule":p.get("solo_payout"),
                          "device_class":p.get("device_class", []),"source":p.get("source")})
    from shutil import which
    return {"modes":["SOLO_POOL","LOCAL_REGTEST","LOCAL_NODE_STRATUM_PROXY"],
            "solo_pools":pools,"local_regtest":{"adapter":"Bitcoin Core RPC CPU SHA-256d","daemon_detected":bool(which("bitcoind")),"default_rpc":"http://127.0.0.1:18443","network":"regtest only"},
            "local_node_proxy":{"adapter":"CKPool Stratum bridge profile","generated_config_only":True,"not_installed_or_started":True,
                                 "requirements":["Bitcoin Core node", "CKPool built from verified source", "RPC cookie/config permissions", "ASIC or Stratum V1 miner"]},
            "explanation":"A pool SOLO endpoint, local regtest CPU mining, and a self-hosted node plus Stratum bridge are three different execution modes."}

class SoloProfileRequest(BaseModel):
    mode: str = Field(pattern="^(SOLO_POOL|LOCAL_REGTEST|LOCAL_NODE_STRATUM_PROXY)$")
    pool_id: str | None = Field(default=None, max_length=80)
    wallet: str | None = Field(default=None, max_length=256)
    worker: str = Field(default="nexus-solo", min_length=1, max_length=64)
    password: str = Field(default="x", max_length=128)
    use_tls: bool = False
    rpc_url: str = Field(default="http://127.0.0.1:18443", max_length=300)
    network: str = Field(default="regtest", pattern="^(main|test|signet|regtest)$")
    payout_script_hex: str | None = Field(default=None, max_length=20000)
    stratum_proxy: str = Field(default="ckpool", max_length=32)
    stratum_port: int = Field(default=3333, ge=1, le=65535)
    rpc_cookie_path: str | None = Field(default=None, max_length=1024)

@app.post("/api/mining/solo/config")
def mining_solo_config(req: SoloProfileRequest):
    try:
        if req.mode == "SOLO_POOL":
            catalog = json.loads((ROOT / "mining" / "pools.json").read_text(encoding="utf-8"))
            pool = next((p for p in catalog.get("pools", []) if p.get("id") == req.pool_id), None)
            if not pool: raise SoloProfileError("Pool SOLO inexistent în catalog.")
            return build_solo_pool_profile(pool, req.wallet or "", req.worker, req.password, req.use_tls)
        if req.mode == "LOCAL_REGTEST":
            return build_local_node_profile(req.mode, req.rpc_url, req.network, req.payout_script_hex,
                                            req.stratum_proxy, req.stratum_port, req.rpc_cookie_path)
        return build_local_node_profile(req.mode, req.rpc_url, req.network, req.payout_script_hex,
                                        req.stratum_proxy, req.stratum_port, req.rpc_cookie_path)
    except SoloProfileError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

class StratumProbeRequest(BaseModel):
    pool_id: str = Field(min_length=1, max_length=80)
    wallet: str = Field(min_length=3, max_length=256)
    worker: str = Field(default="nexus-probe", min_length=1, max_length=64)
    password: str = Field(default="x", max_length=128)
    use_tls: bool = False
    custom_host: str | None = Field(default=None, max_length=253)
    custom_port: int | None = Field(default=None, ge=1, le=65535)
    timeout_seconds: float = Field(default=5, ge=1, le=8)

@app.post("/api/mining/stratum-probe")
def mining_stratum_probe(req: StratumProbeRequest):
    catalog = json.loads((ROOT / "mining" / "pools.json").read_text(encoding="utf-8"))
    pool = next((p for p in catalog.get("pools", []) if p.get("id") == req.pool_id), None)
    if not pool: raise HTTPException(status_code=404, detail="Pool inexistent.")
    if pool.get("id") == "custom":
        host, port = req.custom_host, req.custom_port
    else:
        # Use canonical per-operator TLS host/port when published; never reuse stale UI fields.
        host, port = pool_endpoint(pool, req.use_tls)
    if not host or not port: raise HTTPException(status_code=400, detail="Host/port lipsă; nu există endpoint documentat pentru transportul ales.")
    username = pool_username(pool,req.wallet.strip(),req.worker)
    result = probe_stratum(host, int(port), username, req.password, req.use_tls, req.timeout_seconds)
    result.update({"pool_id":pool["id"],"pool":pool["name"],"coin":pool["coin"],"algorithm":pool["algorithm"],
                   "no_miner_started":True,"no_share_submitted":True,"username_redacted":True})
    return result

@app.post("/api/mining/stratum-job-probe")
def mining_stratum_job_probe(req: StratumProbeRequest):
    catalog = json.loads((ROOT / "mining" / "pools.json").read_text(encoding="utf-8"))
    pool = next((p for p in catalog.get("pools", []) if p.get("id") == req.pool_id), None)
    if not pool: raise HTTPException(status_code=404, detail="Pool inexistent.")
    if pool.get("selectable") is False: raise HTTPException(status_code=400, detail="Profil informativ; nu poate fi testat.")
    if pool.get("id") == "custom": host, port = req.custom_host, req.custom_port
    else: host, port = pool_endpoint(pool, req.use_tls)
    if not host or not port: raise HTTPException(status_code=400, detail="Host/port lipsă pentru transportul ales.")
    username = pool_username(pool, req.wallet.strip(), req.worker)
    result = probe_stratum_job(host, int(port), username, req.password, req.use_tls, req.timeout_seconds)
    result.update({"pool_id":pool["id"],"pool":pool["name"],"coin":pool["coin"],"algorithm":pool["algorithm"],
                   "no_miner_started":True,"no_share_submitted":True,"username_redacted":True})
    return result

class RewardsCheckRequest(BaseModel):
    provider: str = Field(pattern="^(2Miners|unMineable|Kryptex|Braiins)$")
    pool_id: str | None = Field(default=None, max_length=80)
    wallet: str | None = Field(default=None, max_length=256)
    coin: str | None = Field(default=None, max_length=12)
    api_key: str | None = Field(default=None, max_length=512)
    api_secret: str | None = Field(default=None, max_length=512)

@app.post("/api/mining/rewards-check")
def mining_rewards_check(req: RewardsCheckRequest):
    try:
        if req.provider == "2Miners":
            if not req.pool_id or not req.wallet: raise HTTPException(status_code=400, detail="Selectează pool-ul 2Miners și adresa publică.")
            return mining_pool_account(req.pool_id, req.wallet)
        if req.provider == "unMineable":
            if not req.coin or not req.api_key or not req.api_secret:
                raise HTTPException(status_code=400, detail="unMineable necesită ticker, API key și API secret cu scope read. Datele sunt folosite numai în această cerere.")
            return unmineable_account_stats(req.coin, req.api_key, req.api_secret)
        if req.provider == "Kryptex":
            if not req.coin or not req.wallet: raise HTTPException(status_code=400, detail="Kryptex necesită moneda și adresa/username folosită la mining.")
            return kryptex_account_stats(req.coin, req.wallet)
        if req.provider == "Braiins":
            if not req.wallet or not req.api_key: raise HTTPException(status_code=400, detail="Braiins necesită username și token API cu acces web API read-only.")
            return braiins_account_stats(req.wallet, req.api_key)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"{req.provider} API error: {type(exc).__name__}: {str(exc)[:220]}")
    raise HTTPException(status_code=400,detail="Provider invalid.")

@app.get("/api/math/hybrid/capabilities")
def math_hybrid_capabilities():
    return hybrid_math.capabilities()

class HybridSolveRequest(BaseModel):
    kind: str = Field(pattern="^(modular_congruence|linear_system|bitvector_xor)$")
    a: int | None = None
    b: int | None = None
    modulus: int | None = None
    matrix: list[list[int | float | str]] | None = None
    rhs: list[int | float | str] | None = None
    variables: list[str] | None = None
    target: int | None = None
    width: int = Field(default=32, ge=1, le=64)

@app.post("/api/math/hybrid/solve")
def math_hybrid_solve(req: HybridSolveRequest):
    try:
        return hybrid_math.solve(req.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=501, detail=str(exc))

# NEXUS cumulative RCSC integration: Bitcoin block collection and SHA256 structure research.
from modules import rcsc_service as rcsc
from pydantic import BaseModel as _RCSCBaseModel, Field as _RCSCField

@app.get("/api/research/rcsc/status")
def rcsc_status():
    return rcsc.status()

class RCSCCollectRequest(_RCSCBaseModel):
    count: int = _RCSCField(default=10, ge=1, le=200)
    start_height: int | None = _RCSCField(default=None, ge=0)

@app.post("/api/research/rcsc/collect")
def rcsc_collect(req: RCSCCollectRequest):
    try:
        return rcsc.collect(req.count, req.start_height)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=502, detail=str(exc))

class RCSCAnalyzeRequest(_RCSCBaseModel):
    limit: int = _RCSCField(default=1000, ge=1, le=5000)

@app.post("/api/research/rcsc/analyze")
def rcsc_analyze(req: RCSCAnalyzeRequest):
    try:
        return rcsc.run_analysis(req.limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

class RCSCHeaderVerifyRequest(_RCSCBaseModel):
    header_hex: str = _RCSCField(min_length=160, max_length=160, pattern=r"^[0-9a-fA-F]{160}$")

@app.post("/api/research/rcsc/verify-header")
def rcsc_verify_header(req: RCSCHeaderVerifyRequest):
    try:
        return rcsc.verify_header(req.header_hex)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@app.get("/api/research/rcsc/runs/{run_id}")
def rcsc_run_detail(run_id: str):
    result = rcsc.get_run(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="RCSC run not found")
    return result

# NEXUS unified module registry and live lifecycle status.
from modules.module_registry import build_module_registry  # noqa: E402
from modules.nexus_runtime import build_runtime  # noqa: E402

def _active_runtime_services():
    manager = getattr(app.state, "nexus_runtime", None)
    if manager is None:
        return set()
    return {
        row["name"] for row in manager.snapshot()["services"]
        if row["state"] == "running"
    }

@app.get("/api/nexus/runtime")
def nexus_runtime_status():
    manager = getattr(app.state, "nexus_runtime", None)
    if manager is None:
        return {"state": "not_started", "running": 0, "total": 0,
                "system_ready": False, "services": []}
    return manager.health_check_all()

@app.get("/api/nexus/module-registry")
def nexus_module_registry():
    return build_module_registry(ROOT, app, runtime_services=_active_runtime_services())

@app.get("/api/nexus/module-registry/health")
def nexus_module_registry_health():
    runtime_services = _active_runtime_services()
    registry = build_module_registry(ROOT, app, runtime_services=runtime_services)
    critical = [m for m in registry["modules"] if m["critical"]]
    return {
        "critical_modules": len(critical),
        "critical_source_missing": [m["id"] for m in critical if not m["source_present"]],
        "critical_routes_unregistered": [m["id"] for m in critical
                                         if m["source_present"] and m["route_registration_required"]
                                         and not m["registered_routes"]],
        "operational_verified": False,
        "note": "This is a structural integration check, not a live functional health test.",
    }


# Shared algorithm-specific capability layer (evaluation only; never launches miners).
from modules.mining_capability_registry import (
    ALGORITHM_PROFILES as NEXUS_ALGORITHM_PROFILES,
    algorithm_profile as nexus_algorithm_profile,
    catalog_coverage as nexus_catalog_coverage,
    compatibility_matrix as nexus_compatibility_matrix,
    evaluate_capability as nexus_evaluate_capability,
)

@app.get("/api/mining/capabilities/algorithms")
def mining_algorithm_capabilities():
    return {
        "algorithms": [nexus_algorithm_profile(name) for name in NEXUS_ALGORITHM_PROFILES],
        "common_nexus_services": [
            "crypto_engine", "math_intelligence", "research_hub",
            "earnings_intelligence", "mining_optimization",
            "mining_switch_controller", "provider_registry", "telemetry",
            "audit_log", "hardware_inventory", "pool_registry", "wallet_read_only",
        ],
        "policy": "Algorithm profiles describe capability boundaries; live backend, pool authorization and accepted shares require separate validation.",
    }

@app.get("/api/mining/capabilities/pool-coverage")
def mining_capability_pool_coverage():
    return nexus_catalog_coverage(ROOT / "mining" / "pools.json")

class MiningCapabilityRequest(BaseModel):
    algorithm: str = Field(min_length=1, max_length=64)
    device: str = Field(min_length=2, max_length=16)
    miner_id: str = Field(min_length=1, max_length=64)
    pool_id: str | None = Field(default=None, max_length=80)

@app.post("/api/mining/capabilities/evaluate")
def mining_capability_evaluate(req: MiningCapabilityRequest):
    pool = None
    if req.pool_id:
        catalog = json.loads((ROOT / "mining" / "pools.json").read_text(encoding="utf-8"))
        pool = next((item for item in catalog.get("pools", []) if item.get("id") == req.pool_id), None)
        if pool is None:
            raise HTTPException(status_code=404, detail="Pool profile not found")
    try:
        return nexus_evaluate_capability(req.algorithm, req.device, req.miner_id, pool)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# Algorithm-specific backend adapters (read-only discovery/evaluation only).
from mining.backend_adapters import (
    backend_catalog as nexus_backend_catalog,
    discover_backends as nexus_discover_backends,
    evaluate_backend as nexus_evaluate_backend,
)

@app.get("/api/mining/backends")
def mining_backend_catalog():
    return {
        "backends": nexus_backend_catalog(),
        "execution_enabled": False,
        "note": "Backend profiles are candidates; executable discovery and pool/share validation are separate stages.",
    }

@app.get("/api/mining/backends/discovery")
def mining_backend_discovery():
    return {
        "backends": nexus_discover_backends(),
        "execution_enabled": False,
        "note": "Executable presence does not prove algorithm compatibility, pool authorization, accepted shares or profitability.",
    }

class MiningBackendEvaluationRequest(BaseModel):
    backend_id: str = Field(min_length=1, max_length=64)
    algorithm: str = Field(min_length=1, max_length=64)
    device_class: str = Field(min_length=2, max_length=16)

@app.post("/api/mining/backends/evaluate")
def mining_backend_evaluate(req: MiningBackendEvaluationRequest):
    return nexus_evaluate_backend(req.backend_id, req.algorithm, req.device_class)


@app.get("/api/mining/capabilities/compatibility-matrix")
def mining_compatibility_matrix():
    return nexus_compatibility_matrix(
        ROOT / "mining" / "pools.json", nexus_backend_catalog()
    )


# NEXUS unified operator snapshot: read-only aggregation of measured subsystem state.
@app.get("/api/nexus/operator")
def nexus_operator_snapshot():
    """Return one read-only operational snapshot with explicit evidence boundaries."""
    from datetime import datetime, timezone

    def capture(fn):
        try:
            return {"status": "available", "data": fn()}
        except Exception as exc:
            return {"status": "unavailable", "error": type(exc).__name__}

    runtime = capture(nexus_runtime_status)
    modules = capture(nexus_module_registry)
    module_health = capture(nexus_module_registry_health)
    # Dashboard polling is the sampling owner; aggregate reports reuse the
    # latest measured snapshot to avoid duplicate process/GPU probes.
    telemetry = capture(lambda: nexus_runtime_telemetry(history=30, sample=False))
    mining = capture(mining_status)
    mining_processes_report = capture(mining_processes)
    mining_diagnostics_report = capture(mining_diagnostics)
    readiness = capture(nexus_readiness)
    blockchain_node = capture(bitcoin_node_telemetry)
    evm_node = capture(evm_node_telemetry)
    transports = capture(edge_transport_status)
    gateway = capture(edge_gateway_status)
    topology = capture(edge_topology_status)
    edge_nodes = capture(edge_nodes_status)
    edge_tasks = capture(edge_tasks_status)
    edge_telemetry = capture(edge_telemetry_status)

    runtime_data = runtime.get("data") or {}
    telemetry_data = telemetry.get("data") or {}
    mining_data = mining.get("data") or {}
    module_data = modules.get("data") or {}
    service_rows = runtime_data.get("services") or []
    shared_pid = os.getpid()

    # Services execute inside MASTER today. Do not invent isolated service PIDs.
    services = [{
        **row,
        "execution_model": "in_process",
        "shared_master_pid": shared_pid,
        "service_pid": None,
        "per_service_resource_usage": "not_instrumented",
        "lifecycle_timing": "measured_by_lifecycle_manager",
    } for row in service_rows]

    sections = {
        "runtime": runtime,
        "modules": modules,
        "module_health": module_health,
        "host_telemetry": telemetry,
        "mining": mining,
        "mining_processes": mining_processes_report,
        "mining_diagnostics": mining_diagnostics_report,
        "blockchain_readiness": readiness,
        "blockchain_node": blockchain_node,
        "evm_node": evm_node,
        "edge_transports": transports,
        "edge_gateway": gateway,
        "edge_topology": topology,
        "edge_nodes": edge_nodes,
        "edge_tasks": edge_tasks,
        "edge_telemetry": edge_telemetry,
    }
    unavailable_sections = [name for name, item in sections.items()
                            if item.get("status") != "available"]
    runtime_ready = runtime_data.get("system_ready") is True
    overall = "local_runtime_ready_modules_unverified" if runtime_ready and not unavailable_sections else "degraded_or_incomplete"
    return {
        "product": "NEXUS",
        "report_version": "1.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "overall_state": overall,
        "summary": {
            "runtime_ready": runtime_ready,
            "services_running": runtime_data.get("running", 0),
            "services_total": runtime_data.get("total", 0),
            "modules_total": module_data.get("total", 0),
            "modules_operational_verified": module_data.get("system_operational_verified", False),
            "module_state_counts": module_data.get("counts", {}),
            "mining_status": mining_data.get("status", "unavailable"),
            "unavailable_sections": unavailable_sections,
        },
        "execution_model": {
            "master_pid": shared_pid,
            "services_share_master_process": True,
            "individual_service_pids": "not_applicable_in_current_in_process_runtime",
            "per_service_cpu_ram": "not_instrumented",
        },
        "services": services,
        "sections": sections,
        "evidence_policy": {
            "host_cpu_ram_disk_network_gpu": "measured_local_when_available",
            "mining_processes": "detected_from_local_process_table; miner_api_metrics_are_separate",
            "blockchain": "node_metrics_require_successful_loopback_bitcoin_core_rpc; tool_presence_is_not_connectivity",
            "provider_connectivity": "not_inferred_from_source_or_configuration",
            "external_hardware": "not_verified_without_agent_or_hardware_telemetry",
            "missing_values": "reported_as_unavailable_or_null; never estimated",
        },
        "safety": {
            "read_only": True,
            "starts_or_stops_miners": False,
            "wallet_unlock_or_transactions": False,
            "public_chain_writes_enabled": False,
        },
    }
