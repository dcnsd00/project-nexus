import struct, pytest
from mining.bitcoin_pow_engine import scan_nonce_range, compact_target, difficulty_target, BitcoinPowError
from mining.stratum_session import assemble_bitcoin_header

def test_stratum_job_assembles_valid_header():
    params=['job1','00'*32,'01000000','ffffffff',[],'20000000','207fffff','65a1b2c3',True]
    header=assemble_bitcoin_header(params,'abcd','00000000')
    assert len(header)==80
    assert header[-4:]==bytes(4)

def test_pow_scanner_finds_share_under_easy_test_target():
    header=bytes(80)
    rep=scan_nonce_range(header,0,4,(1<<256)-1)
    assert rep['status']=='share_candidate'
    assert rep['nonce']==0
    assert rep['meets_share_target'] is True

def test_pow_scanner_rejects_invalid_header():
    with pytest.raises(BitcoinPowError): scan_nonce_range(b'bad',0,1,(1<<256)-1)

def test_compact_target_and_difficulty():
    assert compact_target('207fffff') > 0
    assert difficulty_target(2) < difficulty_target(1)
