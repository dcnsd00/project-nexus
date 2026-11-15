import struct, hashlib, pytest
from modules.sha2_research_bridge import ExactBitcoinMidstate, double_sha256_reference, research_status

@pytest.mark.parametrize('nonce',[0,1,2,0x12345678,0xffffffff])
def test_midstate_matches_bitcoin_nonce_serialization(nonce):
    header=bytearray(80)
    header[0:4]=bytes.fromhex('20000000')
    header[76:80]=struct.pack('<I',nonce)
    expected=hashlib.sha256(hashlib.sha256(bytes(header)).digest()).digest()
    got=ExactBitcoinMidstate(bytes(header)).hash_nonce(nonce)
    assert got==expected

def test_invalid_header_rejected():
    with pytest.raises(ValueError): ExactBitcoinMidstate(b'bad')

def test_invalid_nonce_rejected():
    with pytest.raises(ValueError): ExactBitcoinMidstate(bytes(80)).hash_nonce(-1)

def test_research_boundary_is_explicit():
    status=research_status()
    assert status['package_present']
    assert status['reduced_round_results_enable_consensus_mining'] is False
