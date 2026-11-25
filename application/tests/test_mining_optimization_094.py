import pytest
from modules.mining_optimization import record_trial, list_trials


def test_trial_calculates_measured_delta_and_rejects_not_eligible(tmp_path, monkeypatch):
    import modules.mining_optimization as mo
    monkeypatch.setattr(mo,'TRIALS',tmp_path/'trials.json')
    d=record_trial({'coin':'RVN','algorithm':'KawPoW','miner':'srbminer','device':'GPU',
      'change_description':'intensity 18 vs 20','duration_seconds':60,
      'baseline_hashrate_hs':100,'candidate_hashrate_hs':110,
      'baseline_accepted':10,'baseline_rejected':1,'candidate_accepted':11,'candidate_rejected':0,
      'baseline_power_w':50,'candidate_power_w':52,'math_module':'thread-tuning'})
    assert d['hashrate_delta_percent']==10.0
    assert d['eligible_for_live_mining'] is False
    assert d['candidate_efficiency_h_per_w'] > d['baseline_efficiency_h_per_w']
    assert list_trials()['count']==1


def test_trial_requires_30_second_window(tmp_path, monkeypatch):
    import modules.mining_optimization as mo
    monkeypatch.setattr(mo,'TRIALS',tmp_path/'trials.json')
    with pytest.raises(ValueError,match='30 secunde'):
        record_trial({'coin':'RVN','algorithm':'KawPoW','miner':'srbminer','device':'GPU',
          'change_description':'test','duration_seconds':10,'baseline_hashrate_hs':100,'candidate_hashrate_hs':110})
