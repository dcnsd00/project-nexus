from __future__ import annotations
import argparse, getpass, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/"modules"/"wallet_benchmark"))
from nexus_wallet_formats import (
    decrypt_web3_v3, decrypt_bip38_non_ec, load_bip39_wordlist,
    bip39_validate, bip39_recover_one_missing_by_address,
    WalletFormatError
)
from nexus_wallet_benchmark import bip39_seed
from nexus_wallet_manager import _encrypt_secret
from nexus_wallet_benchmark import derive_path, make_path, bitcoin_address, evm_address, FORMATS

def require_auth(args, parser):
    if not args.owner_authorized:
        parser.error("Use only with a wallet you own or are explicitly authorized to recover; pass --owner-authorized")

def main():
    p=argparse.ArgumentParser(description="NEXUS local wallet recovery for owner-authorized files")
    sub=p.add_subparsers(dest="cmd",required=True)
    e=sub.add_parser("web3-v3"); e.add_argument("file"); e.add_argument("--owner-authorized",action="store_true")
    b=sub.add_parser("bip38"); b.add_argument("encrypted_key"); b.add_argument("--owner-authorized",action="store_true")
    c=sub.add_parser("bip39-check"); c.add_argument("--format",choices=sorted(FORMATS),required=True)
    c.add_argument("--address",required=True); c.add_argument("--language",default="english")
    c.add_argument("--index",type=int,default=0); c.add_argument("--owner-authorized",action="store_true")
    m=sub.add_parser("bip39-one-missing"); m.add_argument("--format",choices=sorted(FORMATS),required=True)
    m.add_argument("--address",required=True); m.add_argument("--language",default="english")
    m.add_argument("--index",type=int,default=0); m.add_argument("--owner-authorized",action="store_true")
    for sp in (e,b):
        sp.add_argument("--save-keystore",help="save a NEXUS-encrypted local keyfile (never outputs the raw key)")
    args=p.parse_args()
    require_auth(args,p)
    if args.cmd in ("web3-v3","bip38"):
        password=getpass.getpass("Current wallet password/passphrase: ")
        new_password=None
        if args.save_keystore:
            new_password=getpass.getpass("New NEXUS keystore password (min 12 chars): ")
            if len(new_password)<12: p.error("New NEXUS password must contain at least 12 characters")
        if args.cmd=="web3-v3":
            obj=json.loads(Path(args.file).read_text(encoding="utf-8"))
            result=decrypt_web3_v3(obj,password,owner_authorized=True)
        else:
            result=decrypt_bip38_non_ec(args.encrypted_key,password,owner_authorized=True)
        secret=result.pop("private_key")
        result.pop("wif",None)
        if args.save_keystore:
            blob=_encrypt_secret(secret,new_password)
            output={"format":"NEXUS-LOCAL-KEYSTORE-v1","source_format":result["format"],
                    "address":result["address"],"keystore":json.loads(blob)}
            Path(args.save_keystore).write_text(json.dumps(output,indent=2),encoding="utf-8")
            result["saved_encrypted_keystore"]=args.save_keystore
        result["private_key_exported"]=False
        print(json.dumps(result,indent=2)); return

    wordlist=load_bip39_wordlist(args.language)
    phrase=getpass.getpass("Enter owner mnemonic/partial mnemonic (? for one missing word): ")
    passphrase=getpass.getpass("BIP39 passphrase (leave empty if none): ")
    if args.cmd=="bip39-check":
        valid=bip39_validate(phrase,wordlist)
        if not valid["valid"]: p.error(f"Invalid mnemonic: {valid['reason']}")
        seed=bip39_seed(phrase,passphrase)
        path=make_path(args.format,args.index)
        key=derive_path(seed,path)
        address=evm_address(key) if args.format=="EVM_ETHEREUM" else bitcoin_address(args.format,key)
        print(json.dumps({"mnemonic_checksum_valid":True,"address_match":address.lower()==args.address.lower(),
                          "derived_address":address,"expected_address":args.address,"path":path,
                          "seed_exported":False,"private_key_exported":False},indent=2))
    else:
        matches=bip39_recover_one_missing_by_address(phrase,wordlist,args.address,args.format,
                  passphrase,args.index,owner_authorized=True)
        print(json.dumps({"matches":matches,"count":len(matches),
                          "note":"Only candidates matching the supplied owner address are returned; no seed/private key exported."},indent=2))

if __name__=="__main__":
    try: main()
    except Exception as exc:
        print(f"Recovery failed: {type(exc).__name__}: {exc}",file=sys.stderr); sys.exit(2)
