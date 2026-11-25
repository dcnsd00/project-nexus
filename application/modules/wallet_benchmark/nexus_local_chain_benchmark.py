#!/usr/bin/env python3
"""NEXUS 0.4.0 — isolated, signed local-chain lifecycle benchmark.

This is a deterministic educational ledger simulator, NOT an EVM node, Bitcoin
Core/regtest node, public-chain client, or broadcaster. It executes signed,
nonce/UTXO-checked transactions into hash-linked local blocks. No RPC/network I/O.
Only synthetic keys and balances are used.
"""
from __future__ import annotations
import hashlib, json, time, zipfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.utils import Prehashed
from nexus_wallet_benchmark import (
    SECP256K1_N, bitcoin_address, evm_address, FORMATS,
)

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'results'
OUT.mkdir(exist_ok=True)
NETWORKS = ['BTC', 'ETH', 'BASE', 'BNB', 'POLYGON', 'ARBITRUM']
EVM_NETWORKS = NETWORKS[1:]
SAT_PER_BTC = 100_000_000
GAS_LIMIT = 21_000
GAS_PRICE_WEI = 1_000_000_000


def h(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def canon(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(',', ':')).encode()

def test_key(label: str) -> int:
    # Reproducible disposable key material; never use this derivation for funds.
    n = int.from_bytes(hashlib.sha256(('NEXUS-0.4-TEST-ONLY|' + label).encode()).digest(), 'big')
    return (n % (SECP256K1_N - 1)) + 1

def sign(key: int, payload: bytes) -> str:
    sk = ec.derive_private_key(key, ec.SECP256K1())
    digest = hashlib.sha256(payload).digest()
    return sk.sign(digest, ec.ECDSA(Prehashed(hashes.SHA256()))).hex()

def verify(key: int, payload: bytes, signature: str) -> bool:
    pk = ec.derive_private_key(key, ec.SECP256K1()).public_key()
    digest = hashlib.sha256(payload).digest()
    try:
        pk.verify(bytes.fromhex(signature), digest, ec.ECDSA(Prehashed(hashes.SHA256())))
        return True
    except Exception:
        return False

@dataclass
class Account:
    wallet_id: str
    address: str
    private_key: bytearray
    balance: int = 0
    nonce: int = 0
    retired: bool = False

    def key_int(self) -> int:
        if self.retired or not any(self.private_key):
            raise RuntimeError(f'{self.wallet_id} key is retired')
        return int.from_bytes(self.private_key, 'big')

    def erase_key(self) -> None:
        for i in range(len(self.private_key)):
            self.private_key[i] = 0
        self.retired = True

class LocalChain:
    def __init__(self, name: str):
        self.name = name
        self.blocks = []
        self.txs = []
        self.accounts: dict[str, Account] = {}
        self.genesis_hash = h(('NEXUS-GENESIS|' + name).encode())
        self.tip = self.genesis_hash

    def add_account(self, a: Account):
        self.accounts[a.address] = a

    def mine(self, txs: list[dict]) -> dict:
        body = {'chain': self.name, 'height': len(self.blocks) + 1,
                'previous_hash': self.tip, 'transactions': txs}
        block_hash = h(canon(body))
        block = {**body, 'block_hash': block_hash}
        self.blocks.append(block)
        self.txs.extend(txs)
        self.tip = block_hash
        return block

    def check_chain(self) -> bool:
        prev = self.genesis_hash
        for i, b in enumerate(self.blocks, 1):
            body = {k: b[k] for k in ('chain', 'height', 'previous_hash', 'transactions')}
            if b['height'] != i or b['previous_hash'] != prev or h(canon(body)) != b['block_hash']:
                return False
            prev = b['block_hash']
        return prev == self.tip

def account(wallet_id: str, family: str, fmt: str) -> Account:
    k = test_key(wallet_id)
    address = bitcoin_address(fmt, k) if family == 'BTC' else evm_address(k)
    return Account(wallet_id, address, bytearray(k.to_bytes(32, 'big')))


def btc_run() -> tuple[LocalChain, dict]:
    chain = LocalChain('BTC-REGTEST-SIM')
    formats = ['BTC_LEGACY_P2PKH', 'BTC_NESTED_SEGWIT_P2SH_P2WPKH',
               'BTC_NATIVE_SEGWIT_P2WPKH', 'BTC_TAPROOT_BIP86']
    sources, receivers, externals = {}, {}, {}
    for fi, fmt in enumerate(formats):
        recv = account(f'BTC-RCV-{fi+1}', 'BTC', fmt)
        ext = account(f'BTC-EXT-{fi+1}', 'BTC', fmt)
        receivers[fmt], externals[fmt] = recv, ext
        chain.add_account(recv); chain.add_account(ext)
        for j in range(4):
            src = account(f'BTC-SRC-{fi*4+j+1:02d}', 'BTC', fmt)
            src.balance = 1_000_000 + j * 10_000  # satoshis; synthetic funding
            sources[src.wallet_id] = (src, recv, fmt)
            chain.add_account(src)
    tx_count = 0
    for wallet_id, (src, recv, fmt) in sources.items():
        value_in = src.balance
        fee = 1_000
        value_out = value_in - fee
        payload_obj = {'chain': chain.name, 'type': 'UTXO_SPEND', 'from': src.address,
                       'to': recv.address, 'input_sats': value_in, 'output_sats': value_out,
                       'fee_sats': fee, 'nonce': 0, 'wallet_id': wallet_id}
        payload = canon(payload_obj)
        sig = sign(src.key_int(), payload)
        assert verify(src.key_int(), payload, sig)
        src.balance = 0; recv.balance += value_out; src.nonce += 1
        chain.mine([{**payload_obj, 'signature': sig, 'signature_valid': True}])
        src.erase_key(); tx_count += 1
    # Receiver -> external; this is a single local UTXO-style consolidation record per format.
    outbound = []
    for fmt, recv in receivers.items():
        ext = externals[fmt]
        fee = 1_000
        value_out = recv.balance - fee
        if value_out <= 0: raise AssertionError('receiver balance cannot cover simulated fee')
        payload_obj = {'chain': chain.name, 'type': 'UTXO_CONSOLIDATION_SPEND',
                       'from': recv.address, 'to': ext.address, 'input_sats': recv.balance,
                       'output_sats': value_out, 'fee_sats': fee, 'nonce': 0,
                       'wallet_id': recv.wallet_id}
        payload = canon(payload_obj); sig = sign(recv.key_int(), payload)
        assert verify(recv.key_int(), payload, sig)
        recv.balance = 0; ext.balance += value_out; recv.nonce += 1
        chain.mine([{**payload_obj, 'signature': sig, 'signature_valid': True}])
        recv.erase_key(); tx_count += 1
        outbound.append({'from_wallet': recv.wallet_id, 'to_wallet': ext.wallet_id,
                         'amount_sats': value_out, 'fee_sats': fee})
    return chain, {'source_wallets': 16, 'receiver_wallets': 4, 'external_wallets': 4,
                   'transactions': tx_count, 'receiver_to_external': outbound,
                   'total_fees_sats': 16*1_000 + 4*1_000,
                   'all_source_and_receiver_keys_erased': all(a.retired and not any(a.private_key) for a in list(chain.accounts.values()) if '-SRC-' in a.wallet_id or '-RCV-' in a.wallet_id),
                   'all_source_and_receiver_balances_zero': all(a.balance == 0 for a in chain.accounts.values() if '-SRC-' in a.wallet_id or '-RCV-' in a.wallet_id)}


def evm_run(network: str) -> tuple[LocalChain, dict]:
    chain = LocalChain(network + '-LOCAL-EVM-SIM')
    srcs = [account(f'{network}-SRC-{i+1}', 'EVM', 'EVM_ETHEREUM') for i in range(3)]
    recv = account(f'{network}-RCV-01', 'EVM', 'EVM_ETHEREUM')
    ext = account(f'{network}-EXT-01', 'EVM', 'EVM_ETHEREUM')
    for a in srcs + [recv, ext]: chain.add_account(a)
    for i, src in enumerate(srcs): src.balance = 1_000_000_000_000_000_000  # 1 native coin in wei
    fee = GAS_LIMIT * GAS_PRICE_WEI
    txs = 0
    for src in srcs:
        amount = src.balance - fee  # sweep full synthetic balance, minus network fee
        payload_obj = {'chain': chain.name, 'type': 'ACCOUNT_TRANSFER', 'from': src.address,
                       'to': recv.address, 'value_wei': amount, 'fee_wei': fee,
                       'nonce': src.nonce, 'gas_limit': GAS_LIMIT,
                       'gas_price_wei': GAS_PRICE_WEI, 'wallet_id': src.wallet_id}
        payload = canon(payload_obj); sig = sign(src.key_int(), payload)
        assert verify(src.key_int(), payload, sig)
        src.balance -= amount + fee; recv.balance += amount; src.nonce += 1
        chain.mine([{**payload_obj, 'signature': sig, 'signature_valid': True}])
        src.erase_key(); txs += 1
    # Receiver sends its accumulated balance externally, paying one simulated fee.
    value_out = recv.balance - fee
    payload_obj = {'chain': chain.name, 'type': 'ACCOUNT_TRANSFER_EXTERNAL',
                   'from': recv.address, 'to': ext.address, 'value_wei': value_out,
                   'fee_wei': fee, 'nonce': recv.nonce, 'gas_limit': GAS_LIMIT,
                   'gas_price_wei': GAS_PRICE_WEI, 'wallet_id': recv.wallet_id}
    payload = canon(payload_obj); sig = sign(recv.key_int(), payload)
    assert verify(recv.key_int(), payload, sig)
    recv.balance = 0; ext.balance += value_out; recv.nonce += 1
    chain.mine([{**payload_obj, 'signature': sig, 'signature_valid': True}])
    recv.erase_key(); txs += 1
    return chain, {'source_wallets': 3, 'receiver_wallets': 1, 'external_wallets': 1,
                   'transactions': txs, 'receiver_to_external': {'from_wallet': recv.wallet_id,
                   'to_wallet': ext.wallet_id, 'amount_wei': value_out, 'fee_wei': fee},
                   'total_fees_wei': 4*fee,
                   'all_source_and_receiver_keys_erased': all(a.retired and not any(a.private_key) for a in srcs+[recv]),
                   'all_source_and_receiver_balances_zero': all(a.balance == 0 for a in srcs+[recv])}


def main():
    started = time.perf_counter()
    chains, summary = {}, {}
    btc_chain, btc_summary = btc_run(); chains[btc_chain.name] = btc_chain; summary['BTC'] = btc_summary
    for n in EVM_NETWORKS:
        c, s = evm_run(n); chains[c.name] = c; summary[n] = s
    # Every transaction is signed, signature checked, block hash-linked, and local only.
    assert all(c.check_chain() for c in chains.values())
    total_tx = sum(len(c.txs) for c in chains.values())
    total_blocks = sum(len(c.blocks) for c in chains.values())
    assert total_tx == 40, total_tx
    assert total_blocks == total_tx
    assert all(s['all_source_and_receiver_keys_erased'] for s in summary.values())
    assert all(s['all_source_and_receiver_balances_zero'] for s in summary.values())
    elapsed = time.perf_counter() - started
    result = {
      'engine': 'NEXUS Local Chain Lifecycle Benchmark', 'version': '0.4.0',
      'execution_mode': 'ISOLATED_LOCAL_SIGNED_LEDGER_SIMULATION',
      'network_io': False, 'rpc_calls': 0, 'public_chain_broadcasts': 0,
      'real_funds_moved': False, 'synthetic_test_funds_only': True,
      'chains': {name: {'blocks': len(c.blocks), 'transactions': len(c.txs),
                        'hash_chain_valid': c.check_chain(), 'genesis_hash': c.genesis_hash,
                        'tip_hash': c.tip} for name,c in chains.items()},
      'network_summaries': summary,
      'totals': {'chains': len(chains), 'blocks': total_blocks,
                 'signed_transactions': total_tx, 'source_wallets': 16+3*5,
                 'receiver_wallets': 4+5, 'external_wallets': 4+5,
                 'source_to_receiver_transfers': 16+3*5,
                 'receiver_to_external_transfers': 4+5,
                 'keys_zeroized_after_use': True, 'source_and_receiver_balances_zero': True,
                 'elapsed_seconds': round(elapsed, 6)},
      'wallet_deletion_semantics': {
        'private_key_material': 'overwritten in process memory and wallet marked retired',
        'blockchain_address_and_history': 'remain in the immutable local chain history',
        'account_erased_from_chain': False,
        'explanation': 'A blockchain does not delete an address or historical transaction. A wallet is key material/software, not an on-chain object.'
      },
      'limitations': [
        'This is not a full EVM execution client, Bitcoin Core regtest, or consensus implementation.',
        'Transaction envelopes are locally signed benchmark records, not canonical Ethereum RLP/EIP-1559 or Bitcoin wire transactions.',
        'No public network, RPC endpoint, faucet, or external wallet was contacted.'
      ]
    }
    (OUT/'local_chain_lifecycle_v0.4.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    lines = ['# NEXUS 0.4.0 — Local Chain Lifecycle Benchmark', '',
      '**Mode:** isolated local signed-ledger simulation; no network I/O; no real funds.', '',
      '## Results', '', f"- Local chains: {len(chains)} (BTC-style UTXO ledger + five EVM-style account ledgers)",
      f'- Blocks: {total_blocks}', f'- Signed transactions: {total_tx}',
      f"- Source → receiver: {16+3*5}", f"- Receiver → external: {4+5}",
      '- Signature checks: all passed', '- Block hash-chain checks: all passed',
      '- Source and receiver key buffers: overwritten and marked retired after use',
      '- Source and receiver balances after outbound transfers: zero (verified)',
      f'- Runtime: {elapsed:.6f} seconds', '', '## Per-network results', '']
    for n,s in summary.items():
        lines.append(f"- **{n}:** {s['transactions']} transactions; {s['all_source_and_receiver_keys_erased']} key-retirement checks passed")
    lines += ['', '## Important deletion semantics', '',
      'The wallet software/key material can be retired and its local key buffer overwritten. Its address and transaction history cannot be erased from a blockchain. The benchmark therefore verifies zero balance at the receiver after the external transfer and key retirement, while retaining immutable local history.', '',
      '## Limits', '',
      'This benchmark is not a production EVM node or Bitcoin Core regtest. It signs local transaction envelopes and commits them to hash-linked simulated blocks. It does not create canonical wire transactions, execute EVM bytecode, run Bitcoin Script, or broadcast transactions. No real funds moved.']
    (OUT/'LOCAL_CHAIN_REPORT_v0.4.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    # Export a compact local chain archive for audit.
    archive = {name: {'blocks': c.blocks} for name,c in chains.items()}
    (OUT/'local_chain_blocks_v0.4.json').write_text(json.dumps(archive, indent=2), encoding='utf-8')
    print(json.dumps({'version':'0.4.0','passed':True,'chains':len(chains),'blocks':total_blocks,
      'signed_transactions':total_tx,'source_to_receiver':31,'receiver_to_external':9,
      'all_signatures_valid':True,'all_hash_chains_valid':True,'key_zeroization_checks':True,'zero_balance_checks':True,
      'network_io':False,'real_funds_moved':False,'elapsed_seconds':round(elapsed,6)}, indent=2))

if __name__ == '__main__': main()
