from __future__ import annotations
import json, math, time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TRIALS = ROOT / 'results' / 'mining_optimization_trials.json'
TRIALS.parent.mkdir(parents=True, exist_ok=True)


def _load() -> list[dict[str, Any]]:
    try:
        data=json.loads(TRIALS.read_text(encoding='utf-8'))
        return data if isinstance(data,list) else []
    except (OSError, ValueError):
        return []


def record_trial(data: dict[str, Any]) -> dict[str, Any]:
    baseline=float(data['baseline_hashrate_hs']); candidate=float(data['candidate_hashrate_hs'])
    if baseline <= 0 or candidate < 0:
        raise ValueError('Hashrate-ul de bază trebuie să fie > 0, iar candidatul >= 0.')
    duration=int(data['duration_seconds'])
    if duration < 30:
        raise ValueError('Fiecare fereastră de măsurare trebuie să aibă cel puțin 30 secunde.')
    ba=int(data.get('baseline_accepted',0)); br=int(data.get('baseline_rejected',0))
    ca=int(data.get('candidate_accepted',0)); cr=int(data.get('candidate_rejected',0))
    def reject(a,r): return (r/(a+r)*100) if a+r else None
    result={
      'trial_id':f"turbo-{int(time.time())}-{len(_load())+1}", 'created_unix':time.time(),
      'coin':data['coin'].upper(), 'algorithm':data['algorithm'], 'miner':data['miner'],
      'device':data['device'], 'change_description':data['change_description'],
      'duration_seconds':duration, 'baseline_hashrate_hs':baseline, 'candidate_hashrate_hs':candidate,
      'hashrate_delta_percent':round((candidate/baseline-1)*100,4),
      'baseline_accepted':ba,'baseline_rejected':br,'candidate_accepted':ca,'candidate_rejected':cr,
      'baseline_reject_percent':reject(ba,br),'candidate_reject_percent':reject(ca,cr),
      'baseline_gpu_temp_c':data.get('baseline_gpu_temp_c'),'candidate_gpu_temp_c':data.get('candidate_gpu_temp_c'),
      'baseline_power_w':data.get('baseline_power_w'),'candidate_power_w':data.get('candidate_power_w'),
      'baseline_efficiency_h_per_w':round(baseline/float(data['baseline_power_w']),4) if data.get('baseline_power_w') and float(data['baseline_power_w'])>0 else None,
      'candidate_efficiency_h_per_w':round(candidate/float(data['candidate_power_w']),4) if data.get('candidate_power_w') and float(data['candidate_power_w'])>0 else None,
      'math_module':data.get('math_module','none'),
      'exact_consensus_equivalence_proven':False,
      'eligible_for_live_mining':False,
      'classification':'measurement_only',
      'note':'A/B măsurat local. Nu este dovadă de profit sau validitate de consens; rezultatul nu se aplică automat minerului.'
    }
    rows=_load(); rows.append(result); TRIALS.write_text(json.dumps(rows[-500:],indent=2,ensure_ascii=False),encoding='utf-8')
    return result


def list_trials(limit: int=50) -> dict:
    rows=_load()
    return {'count':len(rows),'trials':rows[-max(1,min(limit,200)):], 'policy':'measurement_only; no automatic mining parameter changes'}


def analyze_measured_windows(baseline: dict, candidates: list[dict], policy: dict | None = None) -> dict:
    """Delegate robust, multi-window analysis to the 0.10.23 evidence gate."""
    from modules.mining_efficiency_optimizer import rank_candidates
    return rank_candidates(baseline, candidates, policy or {})
