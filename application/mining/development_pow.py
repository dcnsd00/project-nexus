"""Consensus-aware SHA-256d research helpers; never submits work to public pools."""
from __future__ import annotations
import hashlib


def define_experiment(network: str, algorithm: str, candidate_id: str | None = None) -> dict:
    network = str(network).lower()
    if network not in {'regtest', 'testnet'}:
        raise ValueError('Development PoW accepts regtest or testnet only')
    algorithm = str(algorithm).lower()
    equivalent = algorithm in {'sha256d', 'bitcoin-sha256d'}
    return {'network': network, 'algorithm': algorithm, 'candidate_id': candidate_id or algorithm,
            'consensus_equivalent': equivalent, 'research_only': not equivalent,
            'public_pool_submission_allowed': False,
            'note': 'Consensus verification is valid only for the exact 80-byte header and target.'}


def verify_sha256d_header(header_hex: str, target_hex: str) -> dict:
    try:
        header = bytes.fromhex(header_hex)
        target_bytes = bytes.fromhex(target_hex)
    except (TypeError, ValueError):
        return {'valid': False, 'reason': 'invalid_hex'}
    if len(header) != 80 or len(target_bytes) != 32:
        return {'valid': False, 'reason': 'invalid_length'}
    digest = hashlib.sha256(hashlib.sha256(header).digest()).digest()
    value = int.from_bytes(digest, 'little')
    target = int.from_bytes(target_bytes, 'big')
    return {'valid': value <= target, 'digest_hex': digest[::-1].hex(),
            'hash_integer': value, 'target_integer': target,
            'consensus_equivalent': True, 'network_submission': False}


def run_development_worker(engine: str, request: dict, status_path: str, stop_event_path: str) -> int:
    """Bounded local SHA-256d CPU experiment; GPU remains unavailable without a verified backend."""
    import json, os, time
    from pathlib import Path
    status_file, stop_file = Path(status_path), Path(stop_event_path)
    status_file.parent.mkdir(parents=True, exist_ok=True)
    status = {'engine': engine, 'pid': os.getpid(), 'state': 'starting', 'heartbeat_unix': time.time(),
              'miner_id': 'nexus-development-pow', 'algorithm': request.get('algorithm', 'sha256d'),
              'hashrate_hs': None, 'accepted_shares': 0, 'rejected_shares': 0,
              'pool_connected': False, 'authorized': False, 'last_error': None,
              'network': request.get('network', 'regtest'), 'research_only': True}
    def save():
        tmp = status_file.with_suffix('.tmp')
        tmp.write_text(json.dumps(status), encoding='utf-8')
        os.replace(tmp, status_file)
    if engine == 'gpu':
        status.update(state='failed', last_error='backend_unavailable')
        save()
        return 2
    try:
        exp = define_experiment(status['network'], status['algorithm'])
    except ValueError:
        status.update(state='failed', last_error='invalid_network')
        save()
        return 2
    if exp['research_only']:
        status.update(state='failed', last_error='non_consensus_algorithm_requires_research_executor')
        save()
        return 2
    try:
        attempts = int(request.get('attempts', 100000))
    except (TypeError, ValueError):
        status.update(state='failed', last_error='invalid_attempts')
        save()
        return 2
    if not 1 <= attempts <= 1000000:
        status.update(state='failed', last_error='invalid_attempts')
        save()
        return 2
    header = bytearray(80)
    start = time.perf_counter()
    status['state'] = 'running'
    save()
    done = 0
    while done < attempts and not stop_file.exists():
        header[76:80] = done.to_bytes(4, 'little')
        hashlib.sha256(hashlib.sha256(header).digest()).digest()
        done += 1
        if done % 5000 == 0:
            elapsed = max(time.perf_counter() - start, 1e-9)
            status.update(hashrate_hs=done / elapsed, heartbeat_unix=time.time())
            save()
    elapsed = max(time.perf_counter() - start, 1e-9)
    status.update(state='stopped', hashrate_hs=done / elapsed, heartbeat_unix=time.time(),
                  experiment={'attempts': done, 'duration_seconds': elapsed, 'consensus_verified': False,
                              'note': 'Local synthetic-header benchmark; not a block template and no pool submission.'})
    save()
    return 0
