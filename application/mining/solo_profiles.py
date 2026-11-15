"""Explicit solo-mining modes: operator solo pool, local regtest, self-hosted node proxy."""
from __future__ import annotations
import re
from typing import Any
from urllib.parse import urlparse
from mining.pool_config import pool_endpoint, pool_username, pool_identity_label

class SoloProfileError(ValueError):
    pass


def is_solo_pool(pool: dict[str, Any]) -> bool:
    return 'SOLO' in str(pool.get('mode', '')).upper()


def build_solo_pool_profile(pool: dict[str, Any], wallet: str, worker: str = 'nexus-solo', password: str = 'x', use_tls: bool = False) -> dict[str, Any]:
    if not is_solo_pool(pool):
        raise SoloProfileError('Pool-ul nu are endpoint SOLO documentat.')
    host, port = pool_endpoint(pool, use_tls)
    if not host or not port:
        raise SoloProfileError('Host sau port lipsă pentru modul SOLO selectat.')
    if use_tls and not pool.get('ssl_port'):
        raise SoloProfileError('Pool-ul nu publică un port TLS confirmat.')
    wallet = wallet.strip() if isinstance(wallet, str) else ''
    if not 3 <= len(wallet) <= 256 or any(ch.isspace() for ch in wallet):
        raise SoloProfileError('Adresa publică de payout nu este validă.')
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', worker):
        raise SoloProfileError('Worker invalid; folosește 1–64 caractere alfanumerice, . _ sau -.')
    fmt = pool.get('worker_format', 'WALLET.worker')
    username = pool_username(pool, wallet, worker)
    protocol = pool.get('tls_scheme', 'ssl') if use_tls else 'tcp'
    return {
        'mode': 'SOLO_POOL', 'pool_id': pool['id'], 'operator': pool['pool'],
        'coin': pool['coin'], 'algorithm': pool['algorithm'],
        'stratum': f'stratum+{protocol}://{host}:{int(port)}',
        'host': host, 'port': int(port), 'tls': bool(use_tls),
        'username': username, 'worker': worker, 'password': password,
        'worker_format': fmt, 'pool_fee_note': pool.get('solo_fee_note') or pool.get('fee_note'),
        'backup_ports': (pool.get('backup_ssl_ports', []) if use_tls else pool.get('backup_ports', [])),
        'backup_hosts': pool.get('backup_hosts', []),
        'share_difficulty_default': pool.get('share_difficulty_default'),
        'share_difficulty_high': pool.get('share_difficulty_high'),
        'auth_type': pool.get('auth_type', 'wallet'),
        'identity_label': pool_identity_label(pool),
        'solo_requires_account_mode': bool(pool.get('solo_requires_account_mode', False)),
        'activation_note': ('Activează modul SOLO din dashboard-ul operatorului înainte de conectare.' if pool.get('solo_requires_account_mode') else 'Endpoint-ul selectat este dedicat modului SOLO.'),
        'tls_available': bool(pool.get('ssl_port')),
        'primary_endpoint': {'host': host, 'port': int(port), 'transport': protocol},
        'password_hint': pool.get('password_hint') or 'x (unless the operator specifies otherwise)',
        'min_payout': pool.get('min_payout'),
        'payout_asset': pool.get('payout_asset') or pool['coin'],
        'payout_rule': pool.get('solo_payout') or 'Reward only if this miner/pool finds and confirms a valid block.',
        'fee_note': pool.get('solo_fee_note') or pool.get('fee_note'),
        'payment_scheme': pool.get('payment_scheme') or pool.get('mode'),
        'device_class': pool.get('device_class', []),
        'source': pool.get('source'),
        'launch_external_device_only': any(x in pool.get('device_class', []) for x in ('ASIC','ESP32')),
        'share_note': 'Shares validate contributed work at the pool; accepted shares do not equal a block reward in SOLO mode.',
        'mining_started': False,
    }


def build_local_node_profile(mode: str, rpc_url: str = 'http://127.0.0.1:18443', network: str = 'regtest',
                             payout_script_hex: str | None = None, stratum_proxy: str = 'ckpool',
                             stratum_port: int = 3333, rpc_cookie_path: str | None = None) -> dict[str, Any]:
    parsed = urlparse(rpc_url)
    if parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1','localhost','::1'):
        raise SoloProfileError('Bitcoin Core RPC permis numai pe HTTP loopback; nu expune credentialele în rețea.')
    if mode == 'LOCAL_REGTEST':
        if network != 'regtest':
            raise SoloProfileError('Adaptorul CPU intern este permis doar pe regtest.')
        if not payout_script_hex or len(payout_script_hex) % 2 or not re.fullmatch(r'[0-9a-fA-F]+', payout_script_hex):
            raise SoloProfileError('Payout script hex valid este necesar pentru regtest.')
        if len(payout_script_hex) > 20000:
            raise SoloProfileError('Payout script prea mare.')
        return {'mode': mode, 'network': 'regtest', 'rpc_url': rpc_url,
                'rpc_auth': 'cookie_file' if rpc_cookie_path else 'rpc_user_password',
                'rpc_cookie_configured': bool(rpc_cookie_path), 'payout_script_hex': payout_script_hex,
                'adapter': 'Bitcoin Core JSON-RPC + bounded CPU SHA-256d regtest adapter',
                'block_template_method': 'getblocktemplate', 'submit_method': 'submitblock',
                'mempool_policy': 'current adapter accepts empty mempool template only',
                'mainnet_writes': False, 'mining_started': False}
    if mode == 'LOCAL_NODE_STRATUM_PROXY':
        if network not in ('main','test','signet','regtest'):
            raise SoloProfileError('Rețea Bitcoin necunoscută.')
        if not 1 <= int(stratum_port) <= 65535:
            raise SoloProfileError('Port Stratum invalid.')
        if stratum_proxy != 'ckpool':
            raise SoloProfileError('În acest milestone, șablonul proxy suportat este CKPool.')
        return {'mode': mode, 'network': network, 'rpc_url': rpc_url,
                'rpc_cookie_configured': bool(rpc_cookie_path), 'proxy': 'ckpool',
                'stratum_listen_host': '127.0.0.1', 'stratum_listen_port': int(stratum_port),
                'requires': ['Bitcoin Core full node on the same host', 'CKPool built from verified source',
                             'local RPC credentials/cookie readable by CKPool', 'ASIC/Stratum V1 miner'],
                'architecture': 'ASIC -> local CKPool Stratum -> Bitcoin Core getblocktemplate/submitblock',
                'generated_config_only': True, 'proxy_started': False, 'nexus_submitted_any_block': False,
                'potential_public_chain_submission': network == 'main',
                'warning': 'NEXUS does not install or run CKPool. On mainnet, a manually launched proxy/node could submit a valid block if found; review and approve that external setup yourself.'}
    raise SoloProfileError('Mod local necunoscut.')
