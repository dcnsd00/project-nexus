from __future__ import annotations
import argparse, base64, getpass
from crypto_lab import digest_hex, verify_candidate, derive_key_pbkdf2, decrypt_aes_gcm

def main():
    p=argparse.ArgumentParser(description='MULTIMINER X offline crypto lab (no wallet access)')
    sub=p.add_subparsers(dest='cmd',required=True)
    h=sub.add_parser('hash'); h.add_argument('--algorithm',choices=['SHA-256','SHA-512','SHA3-256','BLAKE2b-512'],default='SHA-256'); h.add_argument('--text',required=True)
    v=sub.add_parser('verify'); v.add_argument('--algorithm',choices=['SHA-256','SHA-512','SHA3-256','BLAKE2b-512'],default='SHA-256'); v.add_argument('--candidate',required=True); v.add_argument('--digest',required=True)
    d=sub.add_parser('derive-key'); d.add_argument('--salt-hex',required=True); d.add_argument('--iterations',type=int,default=600000); d.add_argument('--bytes',type=int,choices=[16,24,32],default=32)
    a=sub.add_parser('decrypt-aes-gcm'); a.add_argument('--key-hex',required=True); a.add_argument('--nonce-hex',required=True); a.add_argument('--ciphertext-b64',required=True); a.add_argument('--aad-b64',default='')
    x=p.parse_args()
    if x.cmd=='hash': print(digest_hex(x.algorithm,x.text.encode()))
    elif x.cmd=='verify': print('MATCH' if verify_candidate(x.algorithm,x.candidate.encode(),x.digest) else 'NO_MATCH')
    elif x.cmd=='derive-key':
        pw=getpass.getpass('Parola (nu se salvează): '); print(derive_key_pbkdf2(pw,x.salt_hex,x.iterations,x.bytes))
    elif x.cmd=='decrypt-aes-gcm':
        pt=decrypt_aes_gcm(x.ciphertext_b64,x.key_hex,x.nonce_hex,x.aad_b64)
        print('PLAINTEXT_UTF8='+pt.decode('utf-8','replace'))
        print('PLAINTEXT_HEX='+pt.hex())
if __name__=='__main__': main()
