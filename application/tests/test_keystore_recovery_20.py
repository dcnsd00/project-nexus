import base64, json, os, secrets, sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"modules"/"wallet_benchmark"))
from nexus_keystore_recovery import (
    decrypt_keystore, decrypt_and_verify_address, parse_keystore,
    KeystoreFormatError, KeystoreAuthenticationError, KeystoreKeyError
)
from nexus_wallet_manager import _encrypt_secret
from nexus_wallet_benchmark import SECP256K1_N, evm_address

PASSWORD=secrets.token_urlsafe(32)
def fixture():
    k=secrets.randbelow(SECP256K1_N-1)+1
    secret=k.to_bytes(32,"big")
    blob=_encrypt_secret(secret,PASSWORD)
    return k,secret,blob,evm_address(k)
def mutate(blob, **changes):
    obj=json.loads(blob); obj.update(changes); return json.dumps(obj)

def test_01_correct_password_decrypts(): 
    _,secret,blob,_=fixture(); assert decrypt_keystore(blob,PASSWORD)==secret
def test_02_wrong_password_rejected():
    _,_,blob,_=fixture()
    with pytest.raises(KeystoreAuthenticationError): decrypt_keystore(blob,"wrong-password")
def test_03_empty_password_rejected():
    _,_,blob,_=fixture()
    with pytest.raises(KeystoreAuthenticationError): decrypt_keystore(blob,"")
def test_04_address_correspondence_verified():
    _,_,blob,address=fixture(); assert decrypt_and_verify_address(blob,PASSWORD,address)["address_verified"]
def test_05_wrong_expected_address_rejected():
    _,_,blob,_=fixture()
    with pytest.raises(KeystoreKeyError): decrypt_and_verify_address(blob,PASSWORD,"0x"+"0"*40)
def test_06_ciphertext_tampering_rejected():
    _,_,blob,_=fixture(); x=json.loads(blob); b=bytearray(base64.b64decode(x["ciphertext"])); b[0]^=1
    x["ciphertext"]=base64.b64encode(b).decode()
    with pytest.raises(KeystoreAuthenticationError): decrypt_keystore(json.dumps(x),PASSWORD)
def test_07_nonce_tampering_rejected():
    _,_,blob,_=fixture(); x=json.loads(blob); b=bytearray(base64.b64decode(x["nonce"])); b[0]^=1
    x["nonce"]=base64.b64encode(b).decode()
    with pytest.raises(KeystoreAuthenticationError): decrypt_keystore(json.dumps(x),PASSWORD)
def test_08_salt_tampering_rejected():
    _,_,blob,_=fixture(); x=json.loads(blob); b=bytearray(base64.b64decode(x["salt"])); b[0]^=1
    x["salt"]=base64.b64encode(b).decode()
    with pytest.raises(KeystoreAuthenticationError): decrypt_keystore(json.dumps(x),PASSWORD)
def test_09_wrong_aad_rejected():
    _,_,blob,_=fixture()
    # ciphertext created under fixed AAD; any different AAD is not accepted by decryptor
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from nexus_keystore_recovery import AAD
    x=json.loads(blob); salt=base64.b64decode(x["salt"]); nonce=base64.b64decode(x["nonce"])
    from nexus_wallet_manager import _derive_key
    key=_derive_key(PASSWORD,salt)
    ct=AESGCM(key).encrypt(nonce,secrets.token_bytes(32),b"wrong-aad")
    x["ciphertext"]=base64.b64encode(ct).decode()
    with pytest.raises(KeystoreAuthenticationError): decrypt_keystore(json.dumps(x),PASSWORD)
def test_10_invalid_json_rejected():
    with pytest.raises(KeystoreFormatError): decrypt_keystore("{broken",PASSWORD)
def test_11_unknown_version_rejected():
    _,_,blob,_=fixture()
    with pytest.raises(KeystoreFormatError): decrypt_keystore(mutate(blob,v=9),PASSWORD)
def test_12_unknown_kdf_rejected():
    _,_,blob,_=fixture()
    with pytest.raises(KeystoreFormatError): decrypt_keystore(mutate(blob,kdf="pbkdf2"),PASSWORD)
def test_13_missing_salt_rejected():
    _,_,blob,_=fixture(); x=json.loads(blob); del x["salt"]
    with pytest.raises(KeystoreFormatError): decrypt_keystore(json.dumps(x),PASSWORD)
def test_14_invalid_salt_length_rejected():
    _,_,blob,_=fixture()
    with pytest.raises(KeystoreFormatError): decrypt_keystore(mutate(blob,salt=base64.b64encode(b"x").decode()),PASSWORD)
def test_15_invalid_nonce_length_rejected():
    _,_,blob,_=fixture()
    with pytest.raises(KeystoreFormatError): decrypt_keystore(mutate(blob,nonce=base64.b64encode(b"x"*11).decode()),PASSWORD)
def test_16_invalid_base64_rejected():
    _,_,blob,_=fixture()
    with pytest.raises(KeystoreFormatError): decrypt_keystore(mutate(blob,ciphertext="%%%"),PASSWORD)
def test_17_truncated_ciphertext_rejected():
    _,_,blob,_=fixture()
    with pytest.raises(KeystoreFormatError): decrypt_keystore(mutate(blob,ciphertext=base64.b64encode(b"x"*20).decode()),PASSWORD)
def test_18_oversized_blob_rejected():
    with pytest.raises(KeystoreFormatError): decrypt_keystore(" "*70000,PASSWORD)
def test_19_unicode_password_supported():
    pw="Nexus-șțâîă-🔐-Recovery-2026!"
    k=secrets.randbelow(SECP256K1_N-1)+1; secret=k.to_bytes(32,"big")
    blob=_encrypt_secret(secret,pw)
    assert decrypt_keystore(blob,pw)==secret
def test_20_decrypted_scalar_range_checked():
    _,_,blob,_=fixture()
    # Encrypt zero scalar correctly to prove post-decryption scalar validation.
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from nexus_wallet_manager import _derive_key
    x=json.loads(blob); salt=base64.b64decode(x["salt"]); nonce=base64.b64decode(x["nonce"])
    key=_derive_key(PASSWORD,salt)
    x["ciphertext"]=base64.b64encode(AESGCM(key).encrypt(nonce,b"\0"*32,b"NEXUS-LOCAL-KEYSTORE-v1")).decode()
    with pytest.raises(KeystoreKeyError): decrypt_keystore(json.dumps(x),PASSWORD)
