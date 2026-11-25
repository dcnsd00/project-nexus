"""Canonical pool endpoint and login formatting helpers. No network or secret storage."""
from __future__ import annotations
from typing import Any


def pool_endpoint(pool: dict[str, Any], use_tls: bool = False) -> tuple[str | None, int | None]:
    if use_tls:
        return pool.get('ssl_host') or pool.get('host'), pool.get('ssl_port')
    return pool.get('host'), pool.get('port')


def pool_username(pool: dict[str, Any], identity: str, worker: str = 'nexus-worker') -> str:
    fmt = pool.get('worker_format', 'WALLET.worker')
    if fmt == 'ACCOUNT.worker':
        return f'{identity}.{worker}'
    if fmt == 'BTC_ADDRESS':
        return identity
    if fmt == 'BTC_ADDRESS[.worker]':
        return f'{identity}.{worker}' if worker else identity
    if fmt == 'KRYPTEX_SOLO_PREFIX':
        return f"{pool.get('solo_username_prefix', 'solo:')}{identity}"
    if fmt == 'WALLET':
        return identity
    return f'{identity}.{worker}'


def pool_identity_label(pool: dict[str, Any]) -> str:
    return 'Username / subaccount' if pool.get('auth_type') == 'account_worker' else 'Adresa publică de wallet'
