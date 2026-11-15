from __future__ import annotations
import json, time, urllib.request
from typing import Any

BASE = "https://api.unmineable.dev/v1"
UA = "NEXUS-MASTER/0.10.9 (+local public metadata client)"

ATOM_ROUTES = [
    {"payout_asset":"ATOM","payout_network":"Cosmos","payout_status":"paused","min_payout":"0.2 ATOM",
     "source":"https://unmineable.com/es/coins/ATOM",
     "routes":[
       {"mined_asset":"PRL","algorithm":"PearlPow","host":"pearlpow.unmineable.com","ports":{"tcp":[3333,13333,80],"tls":[4444,443]},"device_classes":["GPU"]},
       {"mined_asset":"XEL","algorithm":"XelisHash","host":"xelishash.unmineable.com","ports":{"tcp":[3333,13333,80],"tls":[4444,443]},"device_classes":["GPU"]}
     ],
     "warning":"ATOM is a Proof-of-Stake payout asset, not a PoW algorithm. The official unMineable ATOM page currently says payouts are paused. NEXUS must block start until provider metadata/page confirms reactivation."}
]

def _request_json(path: str, timeout: float = 8.0) -> Any:
    if not path.startswith("/v1/meta/coin"):
        raise ValueError("Only public unMineable coin metadata endpoints are allowed here.")
    req = urllib.request.Request(BASE + path, headers={"Accept":"application/json","User-Agent":UA}, method="GET")
    with urllib.request.urlopen(req, timeout=max(2.0,min(float(timeout),10.0))) as response:
        if response.status != 200:
            raise RuntimeError(f"unMineable metadata HTTP {response.status}")
        raw=response.read(2_000_000)
        return json.loads(raw.decode("utf-8"))

def _extract_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload,list):
        return [x for x in payload if isinstance(x,dict)]
    if isinstance(payload,dict):
        for key in ("coins","assets","data","items","results"):
            value=payload.get(key)
            if isinstance(value,list): return [x for x in value if isinstance(x,dict)]
            if isinstance(value,dict):
                rows=[]
                for k,v in value.items():
                    if isinstance(v,dict): rows.append({"symbol":k,**v})
                if rows:return rows
        # Some responses are grouped by category. Flatten only object leaves with ticker-like fields.
        rows=[]
        for value in payload.values():
            if isinstance(value,list): rows.extend(x for x in value if isinstance(x,dict))
        return rows
    return []

def public_asset_catalog(timeout: float = 8.0) -> dict[str, Any]:
    payload=_request_json("/v1/meta/coin?compact=true",timeout)
    items=_extract_items(payload)
    return {"provider":"unMineable","source":BASE+"/meta/coin?compact=true","status":"live_public_metadata",
            "read_only":True,"auth_required":False,"retrieved_at":time.time(),"count":len(items),
            "assets":items,"raw_shape":"list" if isinstance(payload,list) else "object"}

def public_asset_detail(symbol: str, timeout: float = 8.0) -> dict[str, Any]:
    s=(symbol or "").strip().upper()
    if not s.isalnum() or not 2 <= len(s) <= 12: raise ValueError("Ticker invalid.")
    payload=_request_json("/v1/meta/coin/"+s,timeout)
    return {"provider":"unMineable","symbol":s,"status":"live_public_metadata","read_only":True,"auth_required":False,"data":payload}

def payout_routes(symbol: str | None = None) -> dict[str, Any]:
    rows=ATOM_ROUTES
    if symbol: rows=[x for x in rows if x["payout_asset"].upper()==symbol.upper()]
    return {"provider":"unMineable","routes":rows,"source":"https://unmineable.com/api and provider coin pages",
            "note":"Payout assets are not the same as mined PoW assets. Live metadata endpoint should be refreshed before configuring a job."}
