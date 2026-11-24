import faulthandler
import json
import os
import sys
import threading
from contextlib import asynccontextmanager
from pathlib import Path

import psutil
from fastapi.testclient import TestClient
import pytest
import nexus_master


def _emit_thread_snapshot(stage):
    process = psutil.Process(os.getpid())
    threads = threading.enumerate()
    try:
        children = process.children(recursive=True)
    except (psutil.Error, OSError):
        children = []
    print(
        "[NEXUS_THREAD_DIAG] "
        f"stage={stage} python_threads={len(threads)} "
        f"os_threads={process.num_threads()} child_processes={len(children)}",
        flush=True,
    )
    for thread in threads:
        print(
            f"[NEXUS_THREAD_DIAG] thread name={thread.name!r} "
            f"ident={thread.ident} daemon={thread.daemon} alive={thread.is_alive()}",
            flush=True,
        )
    for child in children:
        try:
            print(
                f"[NEXUS_THREAD_DIAG] child pid={child.pid} "
                f"name={child.name()} status={child.status()}",
                flush=True,
            )
        except (psutil.Error, OSError):
            pass


@pytest.fixture(scope="module")
def client():
    # These tests validate mining catalog/configuration routes only.
    # They must not start miners, runtime services, or background workers.
    original_lifespan = nexus_master.app.router.lifespan_context

    @asynccontextmanager
    async def route_test_lifespan(_app):
        yield

    nexus_master.app.router.lifespan_context = route_test_lifespan
    _emit_thread_snapshot("before_testclient_enter")
    faulthandler.dump_traceback_later(15, file=sys.__stderr__, repeat=False)
    try:
        with TestClient(nexus_master.app) as test_client:
            _emit_thread_snapshot("after_testclient_enter")
            yield test_client
    finally:
        faulthandler.cancel_dump_traceback_later()
        nexus_master.app.router.lifespan_context = original_lifespan


def test_vtc_veinpool_catalog_has_operator_documented_endpoint(client):
    data = client.get('/api/mining/pools').json()
    pool = next(p for p in data['pools'] if p['id'] == 'veinpool-vtc-eu')
    assert pool['coin'] == 'VTC'
    assert pool['algorithm'] == 'Verthash'
    assert (pool['host'], pool['port'], pool['ssl_port']) == ('veinpool.fr', 3710, 13710)
    assert 'SOLO' not in pool['mode']


def test_srbminer_verthash_is_in_supported_algorithms():
    assert 'Verthash' in nexus_master.mining_controller.MINERS['srbminer']['algorithms']


def test_vtc_compatibility_passes_with_sufficient_vram_and_installed_srbminer(client, monkeypatch):
    monkeypatch.setattr(nexus_master.mining_controller, '_resolve_binary', lambda mid: 'C:/miners/SRBMiner-MULTI.exe')
    monkeypatch.setattr(nexus_master, '_nvidia', lambda: {'available': True, 'gpus': [{'name':'GTX 1650 Ti','memory_mib':'4096'}]})
    r = client.post('/api/mining/compatibility', json={'pool_id':'veinpool-vtc-eu','miner_id':'srbminer','device':'GPU'})
    assert r.status_code == 200
    assert r.json()['compatible'] is True
    assert r.json()['algorithm'] == 'Verthash'


def test_vtc_config_returns_real_srbminer_preview_without_starting(client, monkeypatch):
    monkeypatch.setattr(nexus_master.mining_controller, '_resolve_binary', lambda mid: 'C:/miners/SRBMiner-MULTI.exe')
    monkeypatch.setattr(nexus_master, '_nvidia', lambda: {'available': True, 'gpus': [{'name':'GTX 1650 Ti','memory_mib':'4096'}]})
    r = client.post('/api/mining/config', json={
        'pool_id':'veinpool-vtc-eu','wallet':'V'+'a'*33,'worker':'nexus-test',
        'miner_id':'srbminer','device':'GPU','mining_mode':'POOL'
    })
    assert r.status_code == 200, r.text
    d = r.json()
    assert d['execution'] == 'not_started'
    assert d['pool_account_api_available'] is False
    assert '--algorithm' in d['command_preview'] and 'Verthash' in d['command_preview']


def test_vtc_solo_pool_mode_is_rejected(client):
    r = client.post('/api/mining/config', json={
        'pool_id':'veinpool-vtc-eu','wallet':'V'+'a'*33,'mining_mode':'SOLO_POOL'
    })
    assert r.status_code == 400
    assert 'SOLO' in r.json()['detail']


def test_pool_tcp_test_uses_selected_catalog_endpoint(client, monkeypatch):
    import socket

    class FakeSocket:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def close(self): pass

    monkeypatch.setattr(socket, 'create_connection', lambda addr, timeout=0: (addr, timeout) and FakeSocket())
    r = client.post('/api/mining/pool-test', json={'pool_id':'veinpool-vtc-eu','use_ssl':False})
    assert r.status_code == 200
    assert r.json()['ok'] is True
    assert r.json()['host'] == 'veinpool.fr'
    assert r.json()['port'] == 3710
    assert 'does not authenticate' in r.json()['scope']


def test_woolypooly_vtc_pool_has_operator_published_endpoint(client):
    data = client.get('/api/mining/pools').json()
    pool = next(p for p in data['pools'] if p['id'] == 'woolypooly-vtc')
    assert pool['host'] == 'pool.woolypooly.com'
    assert pool['port'] == 3102
    assert pool['ssl_port'] is None
    assert pool['mode'] == 'PPLNS'
