import importlib.util
from pathlib import Path
import sys

MODULE = Path(__file__).with_name("nexus_v05_integration.py")
spec = importlib.util.spec_from_file_location("nexus_v05_integration", MODULE)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def test_rpc_refuses_non_loopback_endpoints():
    for url in (
        "https://mainnet.infura.io/v3/example",
        "http://192.0.2.10:8545",
        "http://example.com:8545",
    ):
        try:
            mod.RpcClient(url)
        except mod.BenchmarkError:
            pass
        else:
            raise AssertionError(f"Non-loopback URL was accepted: {url}")


def test_rpc_accepts_loopback_endpoints():
    mod.RpcClient("http://127.0.0.1:8545")
    mod.RpcClient("http://localhost:18443/")


def test_btc_satoshi_conversion_is_exact():
    assert mod.sats_from_btc("0.01234567") == 1_234_567
    assert mod.btc_amount_from_sats(100_000_000) == 1.0


def test_btc_sub_satoshi_precision_rejected():
    try:
        mod.sats_from_btc("0.000000001")
    except mod.BenchmarkError:
        pass
    else:
        raise AssertionError("Sub-satoshi precision should be rejected")


def test_evm_chain_configuration_is_local_and_expected():
    assert set(mod.EVM_NODES) == {"ETH", "BASE", "BNB", "POLYGON", "ARBITRUM"}
    assert [v[0] for v in mod.EVM_NODES.values()] == [31337, 8453, 56, 137, 42161]
    for _, url in mod.EVM_NODES.values():
        assert url.startswith("http://127.0.0.1:")


def test_bitcoin_address_types_cover_four_formats():
    assert set(mod.BTC_FORMATS.values()) == {"legacy", "p2sh-segwit", "bech32", "bech32m"}


def test_compose_isolated_and_has_no_mainnet_fork():
    compose = Path(__file__).with_name("docker-compose.yml").read_text(encoding="utf-8")
    assert "internal: true" in compose
    assert "--fork-url" not in compose
    assert "https://" not in compose
    for port in (18443, 18545, 18546, 18547, 18548, 18549):
        assert f'127.0.0.1:{port}:' in compose
