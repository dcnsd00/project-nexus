"""NEXUS Earnings Intelligence: local opportunity, device, telemetry and reward ledger.

This module deliberately separates estimates from claimable and realized rewards.
It never stores private keys, signs transactions, claims rewards or starts miners.
"""
from __future__ import annotations
import json, os, sqlite3, time, uuid
from pathlib import Path
from typing import Any, Optional

from modules.data_paths import data_path
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/intel", tags=["NEXUS Earnings Intelligence"])
DB_PATH = Path(os.getenv("NEXUS_INTEL_DB", str(data_path("db", "nexus_intelligence.db")))).expanduser().resolve()


def _db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c


def init_db():
    with _db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS opportunities(
          id TEXT PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL, network TEXT,
          asset TEXT, payout_asset TEXT, algorithm TEXT, device_classes TEXT NOT NULL DEFAULT '[]',
          estimated_tokens_day REAL, price_ron REAL, confidence REAL,
          daily_fee_ron REAL NOT NULL DEFAULT 0, transferable INTEGER, eligibility_verified INTEGER,
          payout_verified INTEGER, liquidity_usd REAL, min_payout REAL, payout_days INTEGER,
          source_url TEXT, source_checked_at TEXT, status TEXT NOT NULL DEFAULT 'candidate',
          notes TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS devices(
          id TEXT PRIMARY KEY, name TEXT NOT NULL, device_type TEXT NOT NULL,
          cpu_threads INTEGER, gpu_model TEXT, gpu_vram_mib INTEGER, ram_mib INTEGER,
          storage_gib REAL, watts_idle REAL, watts_load REAL, tariff_ron_kwh REAL,
          capabilities TEXT NOT NULL DEFAULT '[]', enabled INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS telemetry(
          id TEXT PRIMARY KEY, device_id TEXT NOT NULL, job_id TEXT, observed_at TEXT NOT NULL,
          hashrate REAL, hashrate_unit TEXT, accepted_shares INTEGER, rejected_shares INTEGER,
          watts REAL, temperature_c REAL, uptime_seconds REAL, source TEXT,
          FOREIGN KEY(device_id) REFERENCES devices(id));
        CREATE TABLE IF NOT EXISTS jobs(
          id TEXT PRIMARY KEY, opportunity_id TEXT NOT NULL, device_id TEXT NOT NULL,
          mode TEXT NOT NULL DEFAULT 'shadow', status TEXT NOT NULL DEFAULT 'planned',
          algorithm TEXT, pool TEXT, predicted_net_ron_day REAL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(opportunity_id) REFERENCES opportunities(id),
          FOREIGN KEY(device_id) REFERENCES devices(id));
        CREATE TABLE IF NOT EXISTS reward_events(
          id TEXT PRIMARY KEY, opportunity_id TEXT, device_id TEXT, asset TEXT NOT NULL,
          amount REAL NOT NULL, state TEXT NOT NULL, tx_hash TEXT, source_ref TEXT,
          observed_at TEXT NOT NULL, notes TEXT,
          FOREIGN KEY(opportunity_id) REFERENCES opportunities(id),
          FOREIGN KEY(device_id) REFERENCES devices(id));
        CREATE UNIQUE INDEX IF NOT EXISTS ux_reward_tx ON reward_events(tx_hash) WHERE tx_hash IS NOT NULL;
        CREATE TABLE IF NOT EXISTS cost_events(
          id TEXT PRIMARY KEY, device_id TEXT, job_id TEXT, category TEXT NOT NULL,
          amount_ron REAL NOT NULL, kwh REAL, observed_at TEXT NOT NULL, notes TEXT);
        CREATE TABLE IF NOT EXISTS payouts(
          id TEXT PRIMARY KEY, asset TEXT NOT NULL, amount REAL NOT NULL, chain TEXT,
          tx_hash TEXT NOT NULL UNIQUE, address TEXT, observed_at TEXT NOT NULL,
          verification TEXT NOT NULL DEFAULT 'unverified', source_ref TEXT);
        CREATE TABLE IF NOT EXISTS wallet_watches(
          id TEXT PRIMARY KEY, chain TEXT NOT NULL, address TEXT NOT NULL, label TEXT,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(chain,address));
        CREATE TABLE IF NOT EXISTS source_snapshots(
          id TEXT PRIMARY KEY, provider TEXT NOT NULL, subject TEXT NOT NULL,
          source_url TEXT, captured_at TEXT NOT NULL, payload_json TEXT NOT NULL,
          freshness_seconds INTEGER, status TEXT NOT NULL DEFAULT 'captured');
        CREATE TABLE IF NOT EXISTS audit_events(
          id TEXT PRIMARY KEY, event TEXT NOT NULL, details TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        """)


def _audit(event: str, details: str = ""):
    with _db() as c:
        c.execute("INSERT INTO audit_events(id,event,details) VALUES(?,?,?)", (uuid.uuid4().hex,event,details[:2000]))


def _dicts(rows):
    out=[]
    for r in rows:
        d=dict(r)
        for k in ("device_classes","capabilities"):
            if k in d and isinstance(d[k],str):
                try:d[k]=json.loads(d[k])
                except Exception:d[k]=[]
        for k in ("transferable","eligibility_verified","payout_verified","enabled"):
            if k in d and d[k] is not None:d[k]=bool(d[k])
        out.append(d)
    return out


class OpportunityIn(BaseModel):
    name: str = Field(min_length=2,max_length=160)
    category: str = Field(default="pow",max_length=40)
    network: str | None = Field(default=None,max_length=100)
    asset: str | None = Field(default=None,max_length=24)
    payout_asset: str | None = Field(default=None,max_length=24)
    algorithm: str | None = Field(default=None,max_length=80)
    device_classes: list[str] = Field(default_factory=list,max_length=12)
    estimated_tokens_day: float | None = Field(default=None,ge=0)
    price_ron: float | None = Field(default=None,ge=0)
    confidence: float | None = Field(default=None,ge=0,le=1)
    daily_fee_ron: float = Field(default=0,ge=0)
    transferable: bool | None = None
    eligibility_verified: bool | None = None
    payout_verified: bool | None = None
    liquidity_usd: float | None = Field(default=None,ge=0)
    min_payout: float | None = Field(default=None,ge=0)
    payout_days: int | None = Field(default=None,ge=0,le=3650)
    source_url: str | None = Field(default=None,max_length=1000)
    source_checked_at: str | None = None
    status: str = Field(default="candidate",pattern="^(candidate|verified|active|paused|rejected)$")
    notes: str = Field(default="",max_length=4000)


class DeviceIn(BaseModel):
    name: str = Field(min_length=1,max_length=100)
    device_type: str = Field(pattern="^(CPU|GPU|ASIC|ANDROID|ESP32|MINIPC|STORAGE|BANDWIDTH|OTHER)$")
    cpu_threads: int | None = Field(default=None,ge=1,le=512)
    gpu_model: str | None = Field(default=None,max_length=120)
    gpu_vram_mib: int | None = Field(default=None,ge=0,le=1048576)
    ram_mib: int | None = Field(default=None,ge=0)
    storage_gib: float | None = Field(default=None,ge=0)
    watts_idle: float | None = Field(default=None,ge=0,le=10000)
    watts_load: float | None = Field(default=None,ge=0,le=10000)
    tariff_ron_kwh: float | None = Field(default=None,ge=0,le=100)
    capabilities: list[str] = Field(default_factory=list,max_length=40)
    enabled: bool = True


class TelemetryIn(BaseModel):
    device_id: str
    job_id: str | None = None
    observed_at: str | None = None
    hashrate: float | None = Field(default=None,ge=0)
    hashrate_unit: str | None = "H/s"
    accepted_shares: int | None = Field(default=None,ge=0)
    rejected_shares: int | None = Field(default=None,ge=0)
    watts: float | None = Field(default=None,ge=0)
    temperature_c: float | None = Field(default=None,ge=-50,le=150)
    uptime_seconds: float | None = Field(default=None,ge=0)
    source: str = "manual"


class JobIn(BaseModel):
    opportunity_id: str
    device_id: str
    algorithm: str | None = None
    pool: str | None = None
    predicted_net_ron_day: float | None = None
    mode: str = Field(default="shadow",pattern="^shadow$")


class RewardIn(BaseModel):
    opportunity_id: str | None = None
    device_id: str | None = None
    asset: str = Field(min_length=2,max_length=24)
    amount: float = Field(gt=0)
    state: str = Field(pattern="^(estimated|claimable|claimed|realized)$")
    tx_hash: str | None = Field(default=None,max_length=180)
    source_ref: str | None = Field(default=None,max_length=500)
    observed_at: str | None = None
    notes: str = ""


class CostIn(BaseModel):
    device_id: str | None = None
    job_id: str | None = None
    category: str = Field(min_length=2,max_length=50)
    amount_ron: float = Field(ge=0)
    kwh: float | None = Field(default=None,ge=0)
    observed_at: str | None = None
    notes: str = ""


class PayoutIn(BaseModel):
    asset: str = Field(min_length=2,max_length=24)
    amount: float = Field(gt=0)
    chain: str | None = None
    tx_hash: str = Field(min_length=8,max_length=180)
    address: str | None = None
    observed_at: str | None = None
    verification: str = Field(default="unverified",pattern="^(unverified|explorer_confirmed|provider_confirmed)$")
    source_ref: str | None = None


class WalletWatchIn(BaseModel):
    chain: str = Field(min_length=2,max_length=60)
    address: str = Field(min_length=8,max_length=160)
    label: str | None = Field(default=None,max_length=100)


class SourceSnapshotIn(BaseModel):
    provider: str = Field(min_length=2,max_length=80)
    subject: str = Field(min_length=2,max_length=160)
    source_url: str | None = None
    captured_at: str | None = None
    payload: dict[str,Any]
    freshness_seconds: int | None = Field(default=None,ge=0)
    status: str = Field(default="captured",pattern="^(captured|stale|partial|error)$")


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


@router.get("/status")
def intel_status():
    init_db()
    with _db() as c:
        counts={t:c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("opportunities","devices","telemetry","jobs","reward_events","payouts","wallet_watches","source_snapshots")}
    return {"module":"earnings_intelligence","status":"local_active","mode":"read_only_ingestion_plus_manual_ledger","execution":"shadow_only","counts":counts,"provider_connectors_live":0,"private_keys_accepted":False}


@router.post("/opportunities")
def add_opportunity(x: OpportunityIn):
    init_db(); oid=uuid.uuid4().hex
    data=x.model_dump(); data["device_classes"]=json.dumps(data["device_classes"])
    data["transferable"]=None if data["transferable"] is None else int(data["transferable"])
    for k in ("eligibility_verified","payout_verified"):
        data[k]=None if data[k] is None else int(data[k])
    values = (
        oid, data["name"], data["category"], data["network"], data["asset"],
        data["payout_asset"], data["algorithm"], data["device_classes"],
        data["estimated_tokens_day"], data["price_ron"], data["confidence"],
        data["daily_fee_ron"], data["transferable"], data["eligibility_verified"],
        data["payout_verified"], data["liquidity_usd"], data["min_payout"],
        data["payout_days"], data["source_url"], data["source_checked_at"],
        data["status"], data["notes"],
    )
    with _db() as c:
        c.execute(
            """INSERT INTO opportunities (
                id, name, category, network, asset, payout_asset, algorithm,
                device_classes, estimated_tokens_day, price_ron, confidence,
                daily_fee_ron, transferable, eligibility_verified, payout_verified,
                liquidity_usd, min_payout, payout_days, source_url, source_checked_at,
                status, notes
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            values,
        )
    _audit("opportunity.created",oid); return {"id":oid,"status":"created"}


@router.get("/opportunities")
def list_opportunities(status: str | None = None):
    init_db()
    with _db() as c:
        rows=c.execute("SELECT * FROM opportunities"+(" WHERE status=?" if status else "")+" ORDER BY created_at DESC",(status,) if status else ()).fetchall()
    return _dicts(rows)


@router.post("/devices")
def add_device(x: DeviceIn):
    init_db(); did=uuid.uuid4().hex; d=x.model_dump(); d["capabilities"]=json.dumps(d["capabilities"]); d["enabled"]=int(d["enabled"])
    values = (
        did, d["name"], d["device_type"], d["cpu_threads"], d["gpu_model"],
        d["gpu_vram_mib"], d["ram_mib"], d["storage_gib"], d["watts_idle"],
        d["watts_load"], d["tariff_ron_kwh"], d["capabilities"], d["enabled"],
    )
    with _db() as c:
        c.execute(
            """INSERT INTO devices (
                id, name, device_type, cpu_threads, gpu_model, gpu_vram_mib,
                ram_mib, storage_gib, watts_idle, watts_load, tariff_ron_kwh,
                capabilities, enabled
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            values,
        )
    _audit("device.registered",did); return {"id":did,"status":"registered"}


@router.get("/devices")
def list_devices():
    init_db()
    with _db() as c: rows=c.execute("SELECT * FROM devices ORDER BY created_at DESC").fetchall()
    return _dicts(rows)


@router.post("/jobs")
def create_shadow_job(x: JobIn):
    init_db(); jid=uuid.uuid4().hex
    with _db() as c:
        if not c.execute("SELECT 1 FROM opportunities WHERE id=?",(x.opportunity_id,)).fetchone():raise HTTPException(404,"Opportunity not found")
        if not c.execute("SELECT 1 FROM devices WHERE id=?",(x.device_id,)).fetchone():raise HTTPException(404,"Device not found")
        c.execute("INSERT INTO jobs(id,opportunity_id,device_id,mode,status,algorithm,pool,predicted_net_ron_day) VALUES(?,?,?,'shadow','planned',?,?,?)",(jid,x.opportunity_id,x.device_id,x.algorithm,x.pool,x.predicted_net_ron_day))
    _audit("job.shadow_created",jid)
    return {"id":jid,"mode":"shadow","status":"planned","external_process_started":False}


@router.get("/jobs")
def list_jobs(limit:int=Query(100,ge=1,le=1000)):
    init_db()
    with _db() as c:
        return [dict(r) for r in c.execute("SELECT j.*,o.name opportunity,d.name device FROM jobs j JOIN opportunities o ON o.id=j.opportunity_id JOIN devices d ON d.id=j.device_id ORDER BY j.created_at DESC LIMIT ?",(limit,))]


@router.post("/telemetry")
def add_telemetry(x: TelemetryIn):
    init_db(); d=x.model_dump(); d["observed_at"]=d["observed_at"] or _now(); tid=uuid.uuid4().hex
    with _db() as c:
        if not c.execute("SELECT 1 FROM devices WHERE id=?",(d["device_id"],)).fetchone():raise HTTPException(404,"Device not found")
        c.execute("INSERT INTO telemetry(id,device_id,job_id,observed_at,hashrate,hashrate_unit,accepted_shares,rejected_shares,watts,temperature_c,uptime_seconds,source) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",[tid]+[d[k] for k in ("device_id","job_id","observed_at","hashrate","hashrate_unit","accepted_shares","rejected_shares","watts","temperature_c","uptime_seconds","source")])
    return {"id":tid,"status":"recorded"}


@router.post("/rewards")
def add_reward(x: RewardIn):
    init_db(); d=x.model_dump(); d["observed_at"]=d["observed_at"] or _now(); rid=uuid.uuid4().hex
    try:
        with _db() as c:c.execute("INSERT INTO reward_events(id,opportunity_id,device_id,asset,amount,state,tx_hash,source_ref,observed_at,notes) VALUES(?,?,?,?,?,?,?,?,?,?)",[rid]+[d[k] for k in ("opportunity_id","device_id","asset","amount","state","tx_hash","source_ref","observed_at","notes")])
    except sqlite3.IntegrityError as e: raise HTTPException(409,"Duplicate transaction hash or invalid linked record") from e
    _audit("reward.recorded",f"{d['asset']} {d['amount']} {d['state']}"); return {"id":rid,"status":"recorded"}


@router.post("/costs")
def add_cost(x: CostIn):
    init_db(); d=x.model_dump(); d["observed_at"]=d["observed_at"] or _now(); cid=uuid.uuid4().hex
    with _db() as c:c.execute("INSERT INTO cost_events(id,device_id,job_id,category,amount_ron,kwh,observed_at,notes) VALUES(?,?,?,?,?,?,?,?)",[cid]+[d[k] for k in ("device_id","job_id","category","amount_ron","kwh","observed_at","notes")])
    _audit("cost.recorded",f"{d['category']} {d['amount_ron']} RON"); return {"id":cid,"status":"recorded"}


@router.post("/payouts")
def add_payout(x: PayoutIn):
    init_db(); d=x.model_dump(); d["observed_at"]=d["observed_at"] or _now(); pid=uuid.uuid4().hex
    try:
        with _db() as c:c.execute("INSERT INTO payouts(id,asset,amount,chain,tx_hash,address,observed_at,verification,source_ref) VALUES(?,?,?,?,?,?,?,?,?)",[pid]+[d[k] for k in ("asset","amount","chain","tx_hash","address","observed_at","verification","source_ref")])
    except sqlite3.IntegrityError as e: raise HTTPException(409,"Payout transaction already exists") from e
    _audit("payout.recorded",f"{d['asset']} {d['amount']} {d['verification']}"); return {"id":pid,"status":"recorded"}


@router.get("/ledger")
def ledger():
    init_db()
    with _db() as c:
        rewards=[dict(r) for r in c.execute("SELECT asset,state,SUM(amount) amount,COUNT(*) events FROM reward_events GROUP BY asset,state")]
        payouts=[dict(r) for r in c.execute("SELECT asset,verification,SUM(amount) amount,COUNT(*) events FROM payouts GROUP BY asset,verification")]
        costs=c.execute("SELECT COALESCE(SUM(amount_ron),0) FROM cost_events").fetchone()[0]
        realized=c.execute("SELECT COUNT(*) FROM reward_events WHERE state='realized'").fetchone()[0]
    return {"reward_buckets":rewards,"payout_buckets":payouts,"recorded_costs_ron":round(costs,6),"realized_reward_events":realized,"rule":"estimated != claimable != claimed != realized; payout requires transaction hash"}


@router.post("/wallet-watch")
def add_wallet_watch(x: WalletWatchIn):
    init_db(); wid=uuid.uuid4().hex
    try:
        with _db() as c:c.execute("INSERT INTO wallet_watches(id,chain,address,label) VALUES(?,?,?,?)",(wid,x.chain,x.address,x.label))
    except sqlite3.IntegrityError as e: raise HTTPException(409,"Wallet address already watched") from e
    return {"id":wid,"status":"watch_only","signing":False}


@router.get("/wallet-watch")
def list_wallet_watches():
    init_db()
    with _db() as c:return [dict(r) for r in c.execute("SELECT * FROM wallet_watches ORDER BY created_at DESC")]


@router.post("/sources")
def add_source_snapshot(x: SourceSnapshotIn):
    init_db(); sid=uuid.uuid4().hex; d=x.model_dump(); captured=d.pop("captured_at") or _now(); payload=d.pop("payload")
    with _db() as c:c.execute("INSERT INTO source_snapshots(id,provider,subject,source_url,captured_at,payload_json,freshness_seconds,status) VALUES(?,?,?,?,?,?,?,?)",(sid,d["provider"],d["subject"],d["source_url"],captured,json.dumps(payload,sort_keys=True),d["freshness_seconds"],d["status"]))
    return {"id":sid,"status":"captured","captured_at":captured}


@router.get("/sources")
def list_sources(limit:int=Query(50,ge=1,le=500)):
    init_db()
    with _db() as c:rows=c.execute("SELECT id,provider,subject,source_url,captured_at,freshness_seconds,status FROM source_snapshots ORDER BY captured_at DESC LIMIT ?",(limit,)).fetchall()
    return [dict(r) for r in rows]


def evaluate(op: dict, device: dict, hours: float = 24.0) -> dict:
    """Conservative economics; unknown inputs never become a positive recommendation."""
    missing=[]
    if not op.get("asset"):missing.append("asset_identity")
    if op.get("estimated_tokens_day") is None or op.get("estimated_tokens_day",0)<=0:missing.append("estimated_tokens_day")
    if op.get("price_ron") is None or op.get("price_ron",0)<=0:missing.append("price_ron")
    if op.get("confidence") is None:missing.append("estimate_confidence")
    if op.get("min_payout") is None:missing.append("minimum_payout_unknown")
    if op.get("payout_days") is None:missing.append("payout_timing_unknown")
    watts=device.get("watts_load")
    if watts is None:missing.append("device.watts_load")
    tariff=device.get("tariff_ron_kwh")
    if tariff is None:missing.append("device.tariff_ron_kwh")
    if op.get("transferable") not in (True, 1):missing.append("transferability_not_verified")
    if op.get("eligibility_verified") not in (True, 1):missing.append("eligibility_not_verified")
    if op.get("payout_verified") not in (True, 1):missing.append("payout_not_verified")
    if op.get("liquidity_usd") is None or op.get("liquidity_usd",0)<=0:missing.append("liquidity_unknown")
    if missing:return {"decision":"insufficient_evidence","missing":missing,"gross_ron_day":None,"energy_ron_day":None,"net_ron_day":None}
    gross=op["estimated_tokens_day"]*op["price_ron"]
    energy=(watts*hours/1000.0)*tariff
    fees=float(op.get("daily_fee_ron") or 0)
    net=gross-energy-fees
    confidence=op.get("confidence")
    return {"decision":"positive_estimate" if net>0 else "negative_estimate","missing":[],"gross_ron_day":round(gross,6),"energy_kwh_day":round(watts*hours/1000.0,6),"energy_ron_day":round(energy,6),"fees_ron_day":round(fees,6),"net_ron_day":round(net,6),"confidence":confidence,"note":"Estimate only; not realized income. Hardware wear, pool variance, payout threshold and tax are not included unless separately entered."}


@router.get("/evaluate/{opportunity_id}/{device_id}")
def evaluate_pair(opportunity_id:str,device_id:str,hours:float=Query(24,gt=0,le=24)):
    init_db()
    with _db() as c:
        o=c.execute("SELECT * FROM opportunities WHERE id=?",(opportunity_id,)).fetchone();d=c.execute("SELECT * FROM devices WHERE id=?",(device_id,)).fetchone()
    if not o or not d:raise HTTPException(404,"Opportunity or device not found")
    op=dict(o);dev=dict(d);op["device_classes"]=json.loads(op["device_classes"]);dev["capabilities"]=json.loads(dev["capabilities"])
    if not dev["enabled"]:return {"decision":"blocked","reason":"device_disabled"}
    if op["device_classes"] and dev["device_type"] not in op["device_classes"]:return {"decision":"incompatible","reason":"device_class_mismatch"}
    if op["algorithm"] and op["algorithm"].lower() not in [x.lower() for x in dev["capabilities"]]:
        # Device capabilities can also hold provider/service names; missing capability is a hard block for algorithm jobs.
        if op["category"]=="pow":return {"decision":"incompatible","reason":"algorithm_not_in_device_capabilities"}
    return evaluate(op,dev,hours)


@router.post("/scheduler/shadow")
def scheduler_shadow():
    """Build ranked suggestions only. Never starts/stops external processes."""
    init_db()
    with _db() as c:
        ops=[dict(x) for x in c.execute("SELECT * FROM opportunities WHERE status IN ('candidate','verified','active')")]
        devs=[dict(x) for x in c.execute("SELECT * FROM devices WHERE enabled=1")]
    plans=[]
    for o in ops:
        o["device_classes"]=json.loads(o["device_classes"])
        for d in devs:
            d["capabilities"]=json.loads(d["capabilities"])
            if o["device_classes"] and d["device_type"] not in o["device_classes"]:continue
            if o["category"]=="pow" and o["algorithm"] and o["algorithm"].lower() not in [x.lower() for x in d["capabilities"]]:continue
            ev=evaluate(o,d)
            plans.append({"opportunity_id":o["id"],"opportunity":o["name"],"device_id":d["id"],"device":d["name"],"evaluation":ev,"execution":"not_started"})
    plans.sort(key=lambda x:(x["evaluation"].get("decision")!="positive_estimate",-(x["evaluation"].get("net_ron_day") or -1e99)))
    return {"mode":"shadow_only","jobs_proposed":len(plans),"plans":plans,"live_execution":False}


@router.get("/telemetry")
def list_telemetry(device_id:str|None=None,limit:int=Query(100,ge=1,le=2000)):
    init_db(); q="SELECT * FROM telemetry"; args=[]
    if device_id:q+=" WHERE device_id=?";args.append(device_id)
    q+=" ORDER BY observed_at DESC LIMIT ?";args.append(limit)
    with _db() as c:return [dict(r) for r in c.execute(q,args)]


# Database schema is created lazily by explicit API operations, never at module import.
