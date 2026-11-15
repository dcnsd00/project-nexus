#!/usr/bin/env python3
"""NEXUS 0.5.0 local-node integration benchmark.

Runs ONLY against a local Bitcoin Core regtest node and five local Anvil nodes.
No mainnet/testnet/fork support, no configurable RPC host, no mnemonic import,
and no user-supplied private-key import. The only accounts are disposable
Bitcoin Core regtest wallets and Anvil's publicly-known development mnemonic.
"""
from __future__ import annotations

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent / "results"
OUT.mkdir(parents=True, exist_ok=True)

BTC_URL = "http://127.0.0.1:18443/"
BTC_USER = "nexus_local"
BTC_PASSWORD = os.environ.get("NEXUS_REGTEST_RPC_PASSWORD")
BTC_FORMATS = {
    "BTC_LEGACY_P2PKH": "legacy",
    "BTC_NESTED_SEGWIT_P2SH_P2WPKH": "p2sh-segwit",
    "BTC_NATIVE_SEGWIT_P2WPKH": "bech32",
    "BTC_TAPROOT_BIP86": "bech32m",
}
EVM_NODES = {
    "ETH": (31337, "http://127.0.0.1:18545"),
    "BASE": (8453, "http://127.0.0.1:18546"),
    "BNB": (56, "http://127.0.0.1:18547"),
    "POLYGON": (137, "http://127.0.0.1:18548"),
    "ARBITRUM": (42161, "http://127.0.0.1:18549"),
}
EVM_ACCOUNT_BALANCE_WEI = 10**18
GAS_LIMIT = 21_000
POLL_ATTEMPTS = 120
POLL_INTERVAL = 0.25


class BenchmarkError(RuntimeError):
    pass


class JsonRpcError(BenchmarkError):
    pass


class RpcClient:
    """Minimal stdlib JSON-RPC client; endpoints are hard-coded to loopback."""
    def __init__(self, url: str, user: str | None = None, password: str | None = None):
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise BenchmarkError(f"Refusing non-loopback RPC endpoint: {url}")
        self.url = url
        self.auth = None
        if user is not None and password is not None:
            token = base64.b64encode(f"{user}:{password}".encode()).decode()
            self.auth = f"Basic {token}"
        self._id = 0

    def call(self, method: str, params: list[Any] | None = None) -> Any:
        self._id += 1
        body = json.dumps({"jsonrpc": "2.0", "id": self._id,
                           "method": method, "params": params or []}).encode()
        headers = {"Content-Type": "application/json"}
        if self.auth:
            headers["Authorization"] = self.auth
        req = urllib.request.Request(self.url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                payload = json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            raise JsonRpcError(f"RPC HTTP {exc.code} at {self.url}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise JsonRpcError(f"RPC unavailable at {self.url}: {exc}") from exc
        if payload.get("error"):
            raise JsonRpcError(f"{method}: {payload['error']}")
        return payload.get("result")


@dataclass
class WalletRpc:
    root: RpcClient
    name: str

    def call(self, method: str, params: list[Any] | None = None) -> Any:
        return self.root.call(method, params) if not self.name else self._wallet_call(method, params)

    def _wallet_call(self, method: str, params: list[Any] | None = None) -> Any:
        if not BTC_PASSWORD:
            raise BenchmarkError("Set NEXUS_REGTEST_RPC_PASSWORD for the local Bitcoin Core regtest node.")
        url = BTC_URL.rstrip("/") + "/wallet/" + urllib.parse.quote(self.name, safe="")
        client = RpcClient(url, BTC_USER, BTC_PASSWORD)
        return client.call(method, params)


def btc_rpc() -> RpcClient:
    if not BTC_PASSWORD:
        raise BenchmarkError("Set NEXUS_REGTEST_RPC_PASSWORD for the local Bitcoin Core regtest node.")
    return RpcClient(BTC_URL, BTC_USER, BTC_PASSWORD)


def sats_from_btc(value: Any) -> int:
    sats = Decimal(str(value)) * Decimal(100_000_000)
    if sats != sats.to_integral_value():
        raise BenchmarkError(f"Bitcoin RPC amount has sub-satoshi precision: {value}")
    return int(sats)


def btc_amount_from_sats(sats: int) -> float:
    if sats <= 0:
        raise BenchmarkError("Refusing non-positive BTC transfer")
    return float(Decimal(sats) / Decimal(100_000_000))


def wait_for_rpc(client: RpcClient, method: str, params: list[Any] | None = None) -> Any:
    last_error: Exception | None = None
    for _ in range(POLL_ATTEMPTS):
        try:
            return client.call(method, params)
        except Exception as exc:  # node may still be starting
            last_error = exc
            time.sleep(POLL_INTERVAL)
    raise BenchmarkError(f"Node did not become ready: {last_error}")


def bitcoin_transfer(wallet: WalletRpc, to_addr: str, sats: int, node: RpcClient,
                     miner_addr: str, label: str) -> dict[str, Any]:
    txid = wallet.call("sendtoaddress", [to_addr, btc_amount_from_sats(sats), "", "", True])
    node.call("generatetoaddress", [1, miner_addr])
    tx = wallet.call("gettransaction", [txid])
    if int(tx.get("confirmations", 0)) < 1:
        raise BenchmarkError(f"BTC transaction not confirmed: {txid}")
    decoded = node.call("decoderawtransaction", [tx["hex"]])
    vin = decoded.get("vin", [])
    input_signatures_present = bool(vin) and all(
        bool(v.get("scriptSig", {}).get("hex")) or bool(v.get("txinwitness"))
        for v in vin
    )
    if not input_signatures_present:
        raise BenchmarkError(f"BTC input signature/witness data missing: {txid}")
    return {"label": label, "txid": txid, "confirmations": tx["confirmations"],
            "fee_btc": str(tx.get("fee", "unknown")),
            "input_signature_or_witness_present": input_signatures_present,
            "blockheight": tx.get("blockheight")}


def run_bitcoin() -> dict[str, Any]:
    root = btc_rpc()
    info = wait_for_rpc(root, "getblockchaininfo")
    if info.get("chain") != "regtest":
        raise BenchmarkError(f"Bitcoin node is not regtest (chain={info.get('chain')!r})")

    names = ["nexus05_btc_miner"]
    for fmt in BTC_FORMATS:
        slug = fmt.lower().replace("_", "")
        names += [f"nexus05_{slug}_src", f"nexus05_{slug}_rcv", f"nexus05_{slug}_ext"]
    for name in names:
        root.call("createwallet", [name])

    miner = WalletRpc(root, names[0])
    miner_addr = miner.call("getnewaddress", ["regtest-miner", "bech32"])
    root.call("generatetoaddress", [101, miner_addr])

    fmt_results: dict[str, Any] = {}
    total_funding = total_spends = 0
    for fmt, address_type in BTC_FORMATS.items():
        slug = fmt.lower().replace("_", "")
        src = WalletRpc(root, f"nexus05_{slug}_src")
        rcv = WalletRpc(root, f"nexus05_{slug}_rcv")
        ext = WalletRpc(root, f"nexus05_{slug}_ext")
        src_addr = src.call("getnewaddress", ["source", address_type])
        rcv_addr = rcv.call("getnewaddress", ["receiver", address_type])
        ext_addr = ext.call("getnewaddress", ["external-test", address_type])

        # This is testcoin funding from the isolated regtest miner wallet.
        funding_txid = miner.call("sendtoaddress", [src_addr, 1.0, "NEXUS local funding", "", True])
        miner.call("generatetoaddress", [1, miner_addr])
        funding = miner.call("gettransaction", [funding_txid, True, True])
        if int(funding.get("confirmations", 0)) < 1:
            raise BenchmarkError(f"BTC funding transaction not confirmed: {funding_txid}")
        total_funding += 1

        src_before = sats_from_btc(src.call("getbalance"))
        if src_before <= 0:
            raise BenchmarkError(f"No confirmed test funds in {fmt} source wallet")
        tx_src_rcv = bitcoin_transfer(src, rcv_addr, src_before, root, miner_addr,
                                      f"{fmt}: source -> receiver")
        total_spends += 1
        src_after = sats_from_btc(src.call("getbalance"))
        rcv_before = sats_from_btc(rcv.call("getbalance"))
        if src_after != 0 or rcv_before <= 0:
            raise BenchmarkError(f"BTC source/receiver balance invariant failed for {fmt}")

        tx_rcv_ext = bitcoin_transfer(rcv, ext_addr, rcv_before, root, miner_addr,
                                      f"{fmt}: receiver -> external test wallet")
        total_spends += 1
        rcv_after = sats_from_btc(rcv.call("getbalance"))
        ext_after = sats_from_btc(ext.call("getbalance"))
        src_utxos = src.call("listunspent", [1, 9999999])
        rcv_utxos = rcv.call("listunspent", [1, 9999999])
        if rcv_after != 0 or ext_after <= 0 or src_utxos or rcv_utxos:
            raise BenchmarkError(f"BTC post-transfer UTXO/balance invariant failed for {fmt}")

        fmt_results[fmt] = {
            "address_type": address_type,
            "addresses": {"source": src_addr, "receiver": rcv_addr, "external_test": ext_addr},
            "transactions": [
                {"label": f"{fmt}: miner -> source funding", "txid": funding_txid,
                 "confirmations": funding["confirmations"]},
                tx_src_rcv, tx_rcv_ext,
            ],
            "final_balances_sats": {"source": src_after, "receiver": rcv_after,
                                     "external_test": ext_after},
            "source_unspent_outputs": len(src_utxos),
            "receiver_unspent_outputs": len(rcv_utxos),
            "source_and_receiver_zero_balance": src_after == 0 and rcv_after == 0,
        }

    # Unload sender and receiver wallet files from the live daemon. The files
    # still exist inside this disposable container until compose down removes it.
    retired = []
    for fmt in BTC_FORMATS:
        slug = fmt.lower().replace("_", "")
        for role in ("src", "rcv"):
            wallet_name = f"nexus05_{slug}_{role}"
            root.call("unloadwallet", [wallet_name])
            retired.append(wallet_name)

    return {
        "node_version": root.call("getnetworkinfo").get("subversion"),
        "chain": info["chain"], "starting_height": info["blocks"],
        "ending_height": root.call("getblockchaininfo")["blocks"],
        "formats": fmt_results,
        "funding_transactions": total_funding,
        "spend_transactions": total_spends,
        "retired_unloaded_wallets": retired,
        "all_source_receiver_balances_zero": all(
            v["source_and_receiver_zero_balance"] for v in fmt_results.values()),
        "history_persisted_in_regtest": True,
    }


def wait_receipt(client: RpcClient, tx_hash: str) -> dict[str, Any]:
    for _ in range(POLL_ATTEMPTS):
        receipt = client.call("eth_getTransactionReceipt", [tx_hash])
        if receipt is not None:
            if int(receipt["status"], 16) != 1:
                raise BenchmarkError(f"EVM transaction reverted: {tx_hash}")
            return receipt
        time.sleep(POLL_INTERVAL)
    raise BenchmarkError(f"Timed out waiting for EVM receipt: {tx_hash}")


def evm_send_and_confirm(client: RpcClient, chain_name: str, chain_id: int,
                         sender: str, recipient: str, value_wei: int,
                         gas_price_wei: int, label: str) -> dict[str, Any]:
    if value_wei <= 0:
        raise BenchmarkError(f"Refusing non-positive EVM value for {label}")
    tx_hash = client.call("eth_sendTransaction", [{
        "from": sender, "to": recipient, "value": hex(value_wei),
        "gas": hex(GAS_LIMIT), "gasPrice": hex(gas_price_wei),
        "chainId": hex(chain_id),
    }])
    receipt = wait_receipt(client, tx_hash)
    tx = client.call("eth_getTransactionByHash", [tx_hash])
    if not tx or int(tx.get("r", "0x0"), 16) == 0 or int(tx.get("s", "0x0"), 16) == 0:
        raise BenchmarkError(f"Transaction is missing a valid node-produced signature: {tx_hash}")
    block = client.call("eth_getBlockByNumber", [receipt["blockNumber"], False])
    return {
        "label": label, "tx_hash": tx_hash,
        "chain_id": chain_id, "status": int(receipt["status"], 16),
        "block_number": int(receipt["blockNumber"], 16),
        "block_hash": receipt["blockHash"],
        "gas_used": int(receipt["gasUsed"], 16),
        "effective_gas_price_wei": int(receipt.get("effectiveGasPrice", hex(gas_price_wei)), 16),
        "signature_r_nonzero": int(tx["r"], 16) != 0,
        "signature_s_nonzero": int(tx["s"], 16) != 0,
        "block_timestamp": int(block["timestamp"], 16),
    }


def evm_balance(client: RpcClient, address: str) -> int:
    return int(client.call("eth_getBalance", [address, "latest"]), 16)


def run_evm(name: str, chain_id: int, url: str) -> dict[str, Any]:
    client = RpcClient(url)
    version = wait_for_rpc(client, "web3_clientVersion")
    if "anvil" not in str(version).lower():
        raise BenchmarkError(f"Expected Anvil at {url}, received client {version!r}")
    actual_chain_id = int(wait_for_rpc(client, "eth_chainId"), 16)
    if actual_chain_id != chain_id:
        raise BenchmarkError(f"{name}: wrong local chain id {actual_chain_id}, expected {chain_id}")
    accounts = client.call("eth_accounts")
    if len(accounts) < 3:
        raise BenchmarkError(f"{name}: Anvil node did not provide 3 dev accounts")
    source, receiver, external = accounts[:3]

    # Restrict balances to 1 test ETH and zero, respectively. These are local
    # Anvil accounts from the public development mnemonic; never use elsewhere.
    for addr, value in ((source, EVM_ACCOUNT_BALANCE_WEI),
                        (receiver, 0), (external, 0)):
        client.call("anvil_setBalance", [addr, hex(value)])

    gas_price = int(client.call("eth_gasPrice"), 16)
    fee_budget = GAS_LIMIT * gas_price
    src_balance_before = evm_balance(client, source)
    if src_balance_before <= fee_budget:
        raise BenchmarkError(f"{name}: source test balance cannot cover gas")
    tx1 = evm_send_and_confirm(client, name, chain_id, source, receiver,
                               src_balance_before - fee_budget, gas_price,
                               f"{name}: source -> receiver")
    src_balance_after = evm_balance(client, source)
    receiver_before = evm_balance(client, receiver)
    if src_balance_after != 0 or receiver_before <= fee_budget:
        raise BenchmarkError(f"{name}: source->receiver balance invariant failed")

    tx2 = evm_send_and_confirm(client, name, chain_id, receiver, external,
                               receiver_before - fee_budget, gas_price,
                               f"{name}: receiver -> external test account")
    receiver_after = evm_balance(client, receiver)
    external_after = evm_balance(client, external)
    if receiver_after != 0 or external_after <= 0:
        raise BenchmarkError(f"{name}: receiver->external balance invariant failed")

    return {
        "node_version": version, "chain_id": chain_id,
        "addresses": {"source": source, "receiver": receiver, "external_test": external},
        "transactions": [tx1, tx2],
        "final_balances_wei": {"source": src_balance_after,
                                "receiver": receiver_after,
                                "external_test": external_after},
        "source_and_receiver_zero_balance": src_balance_after == 0 and receiver_after == 0,
        "history_persisted_in_local_anvil": True,
    }


def main() -> int:
    started = time.perf_counter()
    result: dict[str, Any] = {
        "engine": "NEXUS Local Node Integration Benchmark",
        "version": "0.5.0",
        "execution_mode": "LOCAL_BITCOIN_REGTEST_AND_LOCAL_ANVIL_ONLY",
        "public_rpc": False, "mainnet": False, "fork_mode": False,
        "real_funds_moved": False, "test_funds_only": True,
        "key_source": "Bitcoin Core temporary regtest wallets + Anvil public development mnemonic",
    }
    try:
        result["BTC"] = run_bitcoin()
        result["EVM"] = {}
        for name, (chain_id, url) in EVM_NODES.items():
            result["EVM"][name] = run_evm(name, chain_id, url)
        btc = result["BTC"]
        evm = result["EVM"]
        assert btc["all_source_receiver_balances_zero"]
        assert all(v["source_and_receiver_zero_balance"] for v in evm.values())
        tx_count = sum(len(v["transactions"]) for v in btc["formats"].values()) + sum(
            len(v["transactions"]) for v in evm.values())
        result["summary"] = {
            "evm_nodes": len(evm), "btc_address_formats": len(BTC_FORMATS),
            "btc_wallet_funding_transactions": btc["funding_transactions"],
            "btc_transactions_total": sum(len(v["transactions"]) for v in btc["formats"].values()),
            "evm_transactions": sum(len(v["transactions"]) for v in evm.values()),
            "transactions_total": tx_count,
            "source_receiver_wallet_balances_zero": True,
            "all_transaction_receipts_successful": True,
            "evm_rpc_signatures_present": True,
            "all_endpoints_loopback": True,
        }
        result["elapsed_seconds"] = round(time.perf_counter() - started, 3)
        result["status"] = "PASS"
        (OUT / "node_integration_v0.5.json").write_text(json.dumps(result, indent=2))
        report = [
            "# NEXUS 0.5.0 — Local Node Integration Report", "",
            f"**Status:** {result['status']}",
            f"**Elapsed:** {result['elapsed_seconds']} s",
            f"**Total successful transactions:** {tx_count}",
            f"**Bitcoin:** {btc['chain']} on Bitcoin Core {btc['node_version']}",
            f"**EVM:** {len(evm)} isolated Anvil nodes; no forks or public RPC.", "",
            "## BTC address formats", "",
        ]
        for fmt, item in btc["formats"].items():
            report.append(f"- **{fmt}:** 3 confirmed transactions; source and receiver balances zero; external test wallet funded.")
        report += ["", "## EVM local nodes", ""]
        for name, item in evm.items():
            report.append(f"- **{name} (chain ID {item['chain_id']}):** 2 successful signed transactions; source and receiver balances zero.")
        report += [
            "", "## Scope and deletion semantics", "",
            "All transactions were executed on private local nodes using test funds only. This does not interact with public Bitcoin, Ethereum, Base, BNB, Polygon, or Arbitrum networks.",
            "A blockchain address and confirmed transaction history are not deleted by emptying a wallet. Bitcoin sender/receiver wallets are unloaded after use. Anvil state exists only in node memory. Run the cleanup script to remove the disposable containers and their local chain state.",
            "Private keys are not exported. Anvil uses its published development mnemonic, which must never be used to hold funds.",
        ]
        (OUT / "NODE_INTEGRATION_REPORT_v0.5.md").write_text("\n".join(report) + "\n")
        print(json.dumps(result["summary"], indent=2))
        print(f"PASS: report written to {OUT / 'NODE_INTEGRATION_REPORT_v0.5.md'}")
        return 0
    except Exception as exc:
        result["status"] = "FAIL"
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["elapsed_seconds"] = round(time.perf_counter() - started, 3)
        (OUT / "node_integration_v0.5.json").write_text(json.dumps(result, indent=2))
        print(result["error"], file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
