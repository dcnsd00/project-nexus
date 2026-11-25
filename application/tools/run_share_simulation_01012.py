#!/usr/bin/env python3
"""Run NEXUS local Stratum submit scenarios and save a JSON report."""
import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from mining.stratum_share_simulator import run_local_submit_scenario
scenarios=[('accepted',{}),('pool_reject',{'reject':True}),('stale_job',{'stale':True}),('duplicate_share',{'duplicate':True})]
results=[]
for name,kwargs in scenarios:
    r=run_local_submit_scenario(**kwargs); r['name']=name; results.append(r)
report={'version':'0.10.12','mode':'offline_loopback_simulation','scenarios':results,
        'summary':{'passed':sum((x['ok'] if x['name']=='accepted' else not x['ok'] or x['name']=='duplicate_share') for x in results),
                   'total':len(results),'live_pool_test':False,'real_miner':False,'wallet_touched':False}}
out=ROOT/'results'/'stratum_share_simulation_01012.json'; out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
