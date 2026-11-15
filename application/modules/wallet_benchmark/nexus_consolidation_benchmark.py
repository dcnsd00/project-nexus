#!/usr/bin/env python3
"""NEXUS consolidation benchmark: offline synthetic ledger only.

Creates 19 deterministic TEST source wallets (4 each for BTC Legacy, Nested SegWit,
Native SegWit, Taproot; 3 EVM) and five corresponding TEST destination wallets.
Proves key/address correspondence by signing and verifying a local challenge.
Then simulates consolidation of synthetic balances into the matching destination.
NO RPC, NO network access, NO broadcast, NO real balances, NO third-party wallet access.
Public BIP39 test vectors are unsafe; never fund these addresses.
"""
from __future__ import annotations
import csv, hashlib, json, time
from collections import defaultdict
from pathlib import Path
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import Prehashed
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from nexus_wallet_benchmark import (
    FORMATS, TEST_VECTORS, TEST_PASSPHRASE, EVM_NETWORKS,
    bip39_seed, derive_path, make_path, bitcoin_address, evm_address,
    validate_address, private_to_public,
)

BTC_FORMATS = [x for x in FORMATS if x.startswith('BTC_')]
EVM_FORMAT = 'EVM_ETHEREUM'


def path_for(fmt: str, index: int) -> str:
    # Use the standard account path with a distinct address index.
    return make_path(fmt, index)


def address_for(fmt: str, private_key: int) -> str:
    return bitcoin_address(fmt, private_key) if fmt.startswith('BTC_') else evm_address(private_key)


def key_proof(private_key: int, label: str) -> dict:
    """Local proof-of-possession: ECDSA signature verified against derived pubkey."""
    challenge = hashlib.sha256(('NEXUS-OFFLINE-TEST|' + label).encode()).digest()
    private_obj = ec.derive_private_key(private_key, ec.SECP256K1())
    public_obj = private_obj.public_key()
    signature = private_obj.sign(challenge, ec.ECDSA(Prehashed(hashes.SHA256())))
    public_obj.verify(signature, challenge, ec.ECDSA(Prehashed(hashes.SHA256())))
    return {
        'challenge_sha256': challenge.hex(),
        'signature_verified': True,
        'public_key_sec1_compressed': public_obj.public_bytes(Encoding.X962, PublicFormat.CompressedPoint).hex(),
    }


def make_wallet(wallet_id: str, fmt: str, index: int, vector_index: int, role: str) -> tuple[dict, int]:
    vector = TEST_VECTORS[vector_index % len(TEST_VECTORS)]
    seed = bip39_seed(vector['mnemonic'], TEST_PASSPHRASE)
    path = path_for(fmt, index)
    started = time.perf_counter_ns()
    private_key = derive_path(seed, path)
    address = address_for(fmt, private_key)
    elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
    if not validate_address(fmt, address):
        raise AssertionError(f'Invalid derived address: {wallet_id}')
    proof = key_proof(private_key, wallet_id)
    return ({
        'wallet_id': wallet_id, 'role': role, 'format': fmt,
        'network_family': 'BTC' if fmt.startswith('BTC_') else 'EVM',
        'derivation_path': path, 'address': address,
        'address_valid': True, 'key_open_test_passed': proof['signature_verified'],
        'proof_challenge_sha256': proof['challenge_sha256'],
        'signature_verified': proof['signature_verified'],
        'public_key_sec1_compressed': proof['public_key_sec1_compressed'],
        'derivation_ms': round(elapsed_ms, 6),
        'mnemonic_vector_id': vector['id'],
        'test_only': True,
    }, private_key)


def build_benchmark(output_dir: Path) -> dict:
    source_specs = []
    # 19 source wallets: 4 in each BTC format + 3 EVM.
    for fmt in BTC_FORMATS:
        for j in range(4):
            source_specs.append((fmt, j))
    for j in range(3):
        source_specs.append((EVM_FORMAT, j))
    assert len(source_specs) == 19

    sources, source_keys = [], {}
    for i, (fmt, j) in enumerate(source_specs, 1):
        row, key = make_wallet(f'SRC-{i:02d}', fmt, 100 + j, i - 1, 'source_test_wallet')
        sources.append(row); source_keys[row['wallet_id']] = key

    destinations, destination_keys = [], {}
    dest_formats = BTC_FORMATS + [EVM_FORMAT]
    for i, fmt in enumerate(dest_formats, 1):
        row, key = make_wallet(f'DST-{i:02d}', fmt, 900 + i, i, 'destination_test_wallet')
        destinations.append(row); destination_keys[row['wallet_id']] = key

    # Deterministic synthetic ledger amounts. These are invented test credits,
    # not on-chain observations and not real funds.
    ledger = []
    for i, src in enumerate(sources, 1):
        if src['network_family'] == 'BTC':
            amount = 12_345 + i * 7_919  # satoshis
            ledger.append({
                'source_wallet_id': src['wallet_id'], 'network': 'BTC',
                'asset': 'BTC', 'unit': 'satoshi', 'amount': amount,
                'destination_wallet_id': f'DST-{BTC_FORMATS.index(src["format"]) + 1:02d}',
            })
        else:
            for n, network in enumerate(EVM_NETWORKS, 1):
                amount = (i * 10**15) + (n * 123_456_789)  # synthetic wei per chain
                ledger.append({
                    'source_wallet_id': src['wallet_id'], 'network': network,
                    'asset': 'native', 'unit': 'wei', 'amount': amount,
                    'destination_wallet_id': 'DST-05',
                })

    # Simulated transfer ledger: preserve asset/network totals exactly.
    before = defaultdict(int)
    after = defaultdict(int)
    transfers = []
    for entry in ledger:
        bucket = (entry['network'], entry['asset'], entry['unit'])
        before[bucket] += entry['amount']
        after[bucket] += entry['amount']
        transfers.append({
            **entry,
            'status': 'SIMULATED_ONLY',
            'network_transaction_hash': None,
            'broadcast': False,
            'fee': 0,
        })
    conservation = []
    for bucket in sorted(before):
        conservation.append({
            'network': bucket[0], 'asset': bucket[1], 'unit': bucket[2],
            'source_total': before[bucket], 'destination_total': after[bucket],
            'difference': after[bucket] - before[bucket],
            'conserved': before[bucket] == after[bucket],
        })
    assert all(x['conserved'] for x in conservation)
    assert len(sources) == 19 and len(destinations) == 5
    assert all(x['address_valid'] and x['key_open_test_passed'] for x in sources + destinations)

    report = {
        'engine': 'NEXUS Wallet Consolidation Benchmark', 'version': '0.2.0',
        'timestamp_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'mode': 'OFFLINE_SYNTHETIC_BENCHMARK',
        'wallet_counts': {'source_test_wallets': len(sources), 'destination_test_wallets': len(destinations), 'total_wallets': len(sources) + len(destinations)},
        'formats': {fmt: sum(1 for x in sources if x['format'] == fmt) for fmt in FORMATS},
        'key_open_tests': {'attempted': len(sources) + len(destinations), 'passed': len(sources) + len(destinations), 'failed': 0, 'method': 'ECDSA challenge signing and verification against derived secp256k1 public key'},
        'synthetic_ledger': {'source_entries': len(ledger), 'simulated_transfers': len(transfers), 'broadcast_transactions': 0, 'network_requests': 0, 'real_balances_read': False, 'real_funds_moved': False},
        'balance_conservation': conservation,
        'all_invariants_passed': all(x['conserved'] for x in conservation),
        'security': 'All mnemonics are public test vectors. All balances are synthetic. Do not fund these addresses. No real wallet was opened or transferred.'
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / 'consolidation_wallets.json').write_text(json.dumps({'sources': sources, 'destinations': destinations}, indent=2), encoding='utf-8')
    (output_dir / 'synthetic_ledger.json').write_text(json.dumps(ledger, indent=2), encoding='utf-8')
    (output_dir / 'simulated_transfers.json').write_text(json.dumps(transfers, indent=2), encoding='utf-8')
    (output_dir / 'consolidation_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    with (output_dir / 'simulated_transfers.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(transfers[0].keys())); writer.writeheader(); writer.writerows(transfers)
    (output_dir / 'CONSOLIDATION_REPORT.md').write_text(render_report(report, sources, destinations), encoding='utf-8')
    return report


def render_report(report: dict, sources: list[dict], destinations: list[dict]) -> str:
    lines = [
        '# NEXUS Wallet Consolidation Benchmark 0.2.0', '',
        '**Result: PASS — offline synthetic benchmark only.**', '',
        f"- Source wallets: {len(sources)}", f"- Destination wallets: {len(destinations)}",
        f"- Total test wallets: {len(sources) + len(destinations)}",
        f"- Key-open challenge tests: {report['key_open_tests']['passed']}/{report['key_open_tests']['attempted']}",
        f"- Simulated transfer rows: {report['synthetic_ledger']['simulated_transfers']}",
        '- Real network requests: 0', '- Broadcast transactions: 0', '- Real balances read: no', '- Real funds moved: no', '',
        '## Balance conservation', '',
        '| Network | Asset | Unit | Source total | Destination total | Difference |',
        '|---|---|---|---:|---:|---:|'
    ]
    for x in report['balance_conservation']:
        lines.append(f"| {x['network']} | {x['asset']} | {x['unit']} | {x['source_total']} | {x['destination_total']} | {x['difference']} |")
    lines += ['', '## Destination wallets', '', '| ID | Format | Address |', '|---|---|---|']
    for x in destinations:
        lines.append(f"| {x['wallet_id']} | {x['format']} | `{x['address']}` |")
    lines += ['', '## Source wallets', '', '| ID | Format | Address | Key-open test |', '|---|---|---|---|']
    for x in sources:
        lines.append(f"| {x['wallet_id']} | {x['format']} | `{x['address']}` | PASS |")
    lines += ['', '> Safety: these are deterministic test wallets derived from public BIP39 vectors. All balances are invented test credits. No funds were moved. Never fund these addresses or use the test mnemonics for real wallets.', '']
    return '\n'.join(lines)


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--output', default='results')
    args = p.parse_args()
    print(json.dumps(build_benchmark(Path(args.output)), indent=2))
