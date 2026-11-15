"""Offline RandomX benchmark adapter for the NEXUS-managed XMRig binary.

This is a local benchmark only: no pool URL, wallet, credentials, or shares are used.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Iterable


def _resolve_xmrig() -> str | None:
    from mining.controller import _resolve_binary
    return _resolve_binary('xmrig')


def build_xmrig_benchmark_command(binary: str, threads: int, dataset: str = '1M') -> list[str]:
    if not isinstance(binary, str) or not binary.strip():
        raise ValueError('XMRig binary path is required')
    if isinstance(threads, bool) or not isinstance(threads, int) or not 1 <= threads <= 256:
        raise ValueError('threads must be an integer from 1 to 256')
    if dataset not in {'1M', '10M'}:
        raise ValueError('dataset must be 1M or 10M')
    return [binary, f'--bench={dataset}', f'--threads={threads}', '--no-color']


def _rate_to_hs(value: str, suffix: str) -> float:
    multiplier = {'': 1.0, 'k': 1e3, 'm': 1e6, 'g': 1e9}[suffix.lower()]
    return float(value) * multiplier


def parse_xmrig_benchmark_output(output: str) -> dict:
    # XMRig prints: speed 10s/60s/15m 1.23k 1.20k 1.10k H/s
    pattern = re.compile(
        r'speed\s+10s/60s/15m\s+'
        r'([0-9]+(?:\.[0-9]+)?)([kKmMgG]?)\s+'
        r'([0-9]+(?:\.[0-9]+)?)([kKmMgG]?)\s+'
        r'([0-9]+(?:\.[0-9]+)?)([kKmMgG]?)\s*H/s', re.I
    )
    matches = list(pattern.finditer(output or ''))
    if not matches:
        return {'algorithm': 'RandomX', 'hashrate_hs': None, 'rates_hs': None, 'unit': 'H/s'}
    match = matches[-1]
    rates = [_rate_to_hs(match.group(i), match.group(i + 1)) for i in (1, 3, 5)]
    return {'algorithm': 'RandomX', 'hashrate_hs': rates[1], 'rates_hs': {
        '10s': rates[0], '60s': rates[1], '15m': rates[2]}, 'unit': 'H/s'}


def run_benchmark(threads: int, dataset: str = '1M', timeout_seconds: int = 180) -> dict:
    binary = _resolve_xmrig()
    base = {'algorithm': 'RandomX', 'backend': 'XMRig', 'threads': threads,
            'dataset': dataset, 'network': 'offline_benchmark', 'pool_connected': False,
            'authorized': False, 'accepted_shares': 0, 'automatic_application': False}
    if not binary:
        native = _resolve_native_benchmark()
        if native:
            native_mode = 'fast' if dataset == '10M' else 'light'
            return run_native_reference_benchmark(threads, mode=native_mode, seed=1, nonces=1000)
        return {**base, 'state': 'backend_unavailable', 'hashrate_hs': None,
                'reason': 'Nici XMRig, nici randomx-benchmark nativ nu sunt instalate/detectate.'}
    try:
        command = build_xmrig_benchmark_command(binary, threads, dataset)
    except ValueError as exc:
        return {**base, 'state': 'invalid_request', 'hashrate_hs': None, 'reason': str(exc)}
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, int) or not 10 <= timeout_seconds <= 300:
        return {**base, 'state': 'invalid_request', 'hashrate_hs': None,
                'reason': 'timeout_seconds must be from 10 to 300'}
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout_seconds,
                                check=False, shell=False)
    except subprocess.TimeoutExpired:
        return {**base, 'state': 'timeout', 'hashrate_hs': None, 'command': command}
    except OSError as exc:
        return {**base, 'state': 'execution_error', 'hashrate_hs': None,
                'reason': f'{type(exc).__name__}: {exc}'}
    parsed = parse_xmrig_benchmark_output((result.stdout or '') + '\n' + (result.stderr or ''))
    if result.returncode != 0:
        return {**base, **parsed, 'state': 'miner_error', 'exit_code': result.returncode,
                'output_tail': ((result.stderr or result.stdout or '')[-2000:])}
    if parsed['hashrate_hs'] is None:
        return {**base, **parsed, 'state': 'unparsed_output', 'exit_code': result.returncode,
                'output_tail': ((result.stdout or '')[-2000:])}
    return {**base, **parsed, 'state': 'completed', 'exit_code': 0,
            'measurement_source': 'XMRig offline benchmark output'}


def run_thread_sweep(thread_counts: Iterable[int], dataset: str = '1M') -> dict:
    counts = list(thread_counts)
    if not counts or len(counts) > 8 or len(set(counts)) != len(counts):
        raise ValueError('thread_counts must contain 1 to 8 unique values')
    results = [run_benchmark(threads=count, dataset=dataset) for count in counts]
    completed = [item for item in results if item.get('state') == 'completed']
    best = max(completed, key=lambda item: item['hashrate_hs']) if completed else None
    return {'algorithm': 'RandomX', 'dataset': dataset, 'results': results,
            'best_threads': best['threads'] if best else None,
            'best_hashrate_hs': best['hashrate_hs'] if best else None,
            'recommendation_only': True, 'automatic_application': False,
            'pool_shares_required_for_production_decision': True}


def _resolve_synthetic_blocks_binary() -> str | None:
    candidates = []
    configured = os.environ.get('NEXUS_RANDOMX_BLOCK_BENCHMARK')
    if configured:
        candidates.append(Path(configured))
    root = Path(__file__).resolve().parents[1]
    names = ('randomx-20block-benchmark.exe', 'randomx-20block-benchmark')
    for name in names:
        candidates.extend((root / 'build' / 'randomx' / name,
                           root / 'miners' / name))
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return None


def build_synthetic_blocks_command(binary: str, threads: int,
                                   hashes_per_block: int = 1000) -> list[str]:
    if not isinstance(binary, str) or not binary.strip():
        raise ValueError('20-block benchmark binary path is required')
    if isinstance(threads, bool) or not isinstance(threads, int) or not 1 <= threads <= 64:
        raise ValueError('threads must be an integer from 1 to 64')
    if (isinstance(hashes_per_block, bool) or not isinstance(hashes_per_block, int)
            or not 100 <= hashes_per_block <= 50000):
        raise ValueError('hashes_per_block must be from 100 to 50000')
    return [binary, str(threads), str(hashes_per_block), 'fast']


def parse_synthetic_blocks_output(output: str) -> dict:
    text = output or ''
    mode = re.search(r'^mode=(fast|light)\s+flags=(0x[0-9a-f]+)', text, re.M | re.I)
    elapsed = re.search(r'^benchmark_seconds=([0-9]+(?:\.[0-9]+)?)', text, re.M)
    config = re.search(r'^threads=(\d+) blocks=(\d+) hashes_per_block=(\d+)\s*$', text, re.M)
    totals = re.search(r'^total_hashes=(\d+) total_hits=(\d+)\s*$', text, re.M)
    rate_match = re.search(r'^hashrate_hs=([0-9]+(?:\.[0-9]+)?)\s*$', text, re.M)
    blocks = []
    pattern = re.compile(
        r'^block=(\d+) height=(\d+) target_zero_bits=(\d+) hashes=(\d+) hits=(\d+) first_nonce=(none|\d+)'
        r'(?: first_hash=([0-9a-f]{64}))?\s*$',
        re.M | re.I
    )
    for match in pattern.finditer(text):
        blocks.append({
            'block': int(match.group(1)), 'height': int(match.group(2)),
            'target_zero_bits': int(match.group(3)), 'hashes': int(match.group(4)),
            'hits': int(match.group(5)),
            'first_nonce': None if match.group(6) == 'none' else int(match.group(6)),
            'first_hash': match.group(7).lower() if match.group(7) else None,
        })
    base = {
        'algorithm': 'RandomX', 'mode': mode.group(1) if mode else None,
        'flags': mode.group(2) if mode else None, 'pool_connected': False,
        'authorized': False, 'accepted_shares': 0, 'automatic_application': False,
        'network': 'offline_synthetic_benchmark', 'synthetic_blocks': True,
        'blocks': blocks, 'block_count': len(blocks), 'hashrate_hs': None,
    }
    if not (mode and elapsed and config and totals and rate_match and len(blocks) == 20):
        return {**base, 'state': 'unparsed_output',
                'reason': 'Output incomplete: expected 20 blocks, timing, totals and measured hashrate.'}
    threads, block_count, per_block = map(int, config.groups())
    total_hashes, total_hits = map(int, totals.groups())
    rate = float(rate_match.group(1))
    if block_count != 20 or total_hashes != block_count * per_block or rate <= 0:
        return {**base, 'state': 'unparsed_output',
                'reason': 'Benchmark totals are inconsistent.'}
    if any(b['hashes'] != per_block for b in blocks):
        return {**base, 'state': 'unparsed_output',
                'reason': 'Per-block hash counts are inconsistent.'}
    if sum(b['hits'] for b in blocks) != total_hits:
        return {**base, 'state': 'unparsed_output',
                'reason': 'Per-block hit counts are inconsistent.'}
    return {**base, 'state': 'completed', 'threads': threads,
            'hashes_per_block': per_block, 'total_hashes': total_hashes,
            'total_hits': total_hits, 'benchmark_seconds': float(elapsed.group(1)),
            'hashrate_hs': rate, 'unit': 'H/s',
            'hit_blocks': sum(1 for block in blocks if block['hits'] > 0),
            'difficulty_model': 'leading_zero_bits_8_to_14_lab_target',
            'measurement_source': 'NEXUS 20-block harness using RandomX v1.2.3 native API'}

def run_synthetic_blocks_benchmark(threads: int = 4, hashes_per_block: int = 1000,
                                   timeout_seconds: int = 300) -> dict:
    binary = _resolve_synthetic_blocks_binary()
    base = {'algorithm': 'RandomX', 'backend': 'RandomX v1.2.3 20-block harness',
            'threads': threads, 'hashes_per_block': hashes_per_block,
            'network': 'offline_synthetic_benchmark', 'pool_connected': False,
            'authorized': False, 'accepted_shares': 0, 'automatic_application': False,
            'synthetic_blocks': True, 'hashrate_hs': None}
    if not binary:
        return {**base, 'state': 'backend_unavailable',
                'reason': 'Compilati randomx-20block-benchmark nu a fost găsit. Rulează tools/build_randomx_20block_benchmark.'}
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, int) or not 10 <= timeout_seconds <= 600:
        return {**base, 'state': 'invalid_request', 'reason': 'timeout_seconds must be from 10 to 600'}
    try:
        command = build_synthetic_blocks_command(binary, threads, hashes_per_block)
    except ValueError as exc:
        return {**base, 'state': 'invalid_request', 'reason': str(exc)}
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                timeout=timeout_seconds, check=False, shell=False)
    except subprocess.TimeoutExpired:
        return {**base, 'state': 'timeout'}
    except OSError as exc:
        return {**base, 'state': 'execution_error',
                'reason': f'{type(exc).__name__}: {exc}'}
    parsed = parse_synthetic_blocks_output((result.stdout or '') + '\n' + (result.stderr or ''))
    if result.returncode != 0:
        return {**base, **parsed, 'state': 'benchmark_error',
                'exit_code': result.returncode,
                'output_tail': (result.stderr or result.stdout or '')[-2000:]}
    return {**base, **parsed, 'exit_code': 0} if parsed['state'] == 'completed' else {
        **base, **parsed, 'exit_code': result.returncode}


def _resolve_native_benchmark() -> str | None:
    candidates = []
    configured = os.environ.get('NEXUS_RANDOMX_BENCHMARK')
    if configured:
        candidates.append(Path(configured))
    root = Path(__file__).resolve().parents[1]
    names = ('randomx-benchmark.exe', 'randomx-benchmark')
    for name in names:
        candidates.extend((root / 'miners' / name,
                           root / 'build' / 'randomx' / 'Release' / name,
                           root / 'build' / 'randomx' / name))
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return None


def build_native_benchmark_command(binary: str, threads: int, mode: str = 'fast',
                                   seed: int = 1, nonces: int = 1000) -> list[str]:
    if not isinstance(binary, str) or not binary.strip():
        raise ValueError('RandomX benchmark binary path is required')
    if isinstance(threads, bool) or not isinstance(threads, int) or not 1 <= threads <= 256:
        raise ValueError('threads must be an integer from 1 to 256')
    if mode not in {'fast', 'light'}:
        raise ValueError('mode must be fast or light')
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 2**32 - 1:
        raise ValueError('seed must be an unsigned 32-bit integer')
    if isinstance(nonces, bool) or not isinstance(nonces, int) or not 1 <= nonces <= 10_000_000:
        raise ValueError('nonces must be from 1 to 10000000')
    return [binary, '--mine' if mode == 'fast' else '--verify', '--jit',
            '--threads', str(threads), '--init', str(min(threads, 8)),
            '--nonces', str(nonces), '--seed', str(seed)]


def parse_native_benchmark_output(output: str) -> dict:
    text = output or ''
    rate = re.search(r'Performance:\s*([0-9]+(?:\.[0-9]+)?)\s*hashes per second', text, re.I)
    ms_rate = re.search(r'Performance:\s*([0-9]+(?:\.[0-9]+)?)\s*ms per hash', text, re.I)
    hashrate = float(rate.group(1)) if rate else (
        1000.0 / float(ms_rate.group(1)) if ms_rate and float(ms_rate.group(1)) > 0 else None)
    digest = re.search(r'Calculated result:\s*([0-9a-f]{64})', text, re.I)
    mode = 'fast' if 'full memory mode (2080 MiB)' in text else (
        'light' if 'light memory mode (256 MiB)' in text else None)
    return {'algorithm': 'RandomX', 'hashrate_hs': hashrate, 'unit': 'H/s',
            'calculated_result': digest.group(1).lower() if digest else None,
            'mode': mode, 'jit': 'JIT compiled mode' in text,
            'hardware_aes': 'hardware AES mode' in text}


def run_native_reference_benchmark(threads: int, mode: str = 'fast', seed: int = 1,
                                   nonces: int = 1000, timeout_seconds: int = 180) -> dict:
    binary = _resolve_native_benchmark()
    base = {'algorithm': 'RandomX', 'backend': 'RandomX reference v1.2.3',
            'threads': threads, 'mode': mode, 'seed': seed, 'nonces': nonces,
            'network': 'offline_synthetic_benchmark', 'pool_connected': False,
            'authorized': False, 'accepted_shares': 0, 'automatic_application': False}
    if not binary:
        return {**base, 'state': 'backend_unavailable', 'hashrate_hs': None,
                'reason': 'Compilati randomx-benchmark nu a fost găsit. Rulează tools/build_randomx_benchmark.'}
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, int) or not 10 <= timeout_seconds <= 600:
        return {**base, 'state': 'invalid_request', 'hashrate_hs': None,
                'reason': 'timeout_seconds must be from 10 to 600'}
    try:
        command = build_native_benchmark_command(binary, threads, mode, seed, nonces)
    except ValueError as exc:
        return {**base, 'state': 'invalid_request', 'hashrate_hs': None, 'reason': str(exc)}
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                timeout=timeout_seconds, check=False, shell=False)
    except subprocess.TimeoutExpired:
        return {**base, 'state': 'timeout', 'hashrate_hs': None}
    except OSError as exc:
        return {**base, 'state': 'execution_error', 'hashrate_hs': None,
                'reason': f'{type(exc).__name__}: {exc}'}
    parsed = parse_native_benchmark_output((result.stdout or '') + '\n' + (result.stderr or ''))
    if result.returncode != 0 or parsed['hashrate_hs'] is None or not parsed['calculated_result']:
        return {**base, **parsed, 'state': 'miner_error' if result.returncode else 'unparsed_output',
                'exit_code': result.returncode,
                'output_tail': (result.stderr or result.stdout or '')[-2000:]}
    return {**base, **parsed, 'state': 'completed', 'exit_code': 0,
            'measurement_source': 'official RandomX v1.2.3 reference benchmark'}
