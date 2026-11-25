"""Public Bitcoin block-data collector using the Mempool.space REST API."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from .bitcoin import parse_header, verify_coinbase_reward, verify_merkle_root

BASE_URL = "https://mempool.space/api"


class MempoolClient:
    def __init__(self, base_url: str = BASE_URL, timeout: float = 20.0,
                 pause_seconds: float = 0.15, retries: int = 3):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.pause_seconds = max(0.0, pause_seconds)
        self.retries = max(0, retries)

    def _get_text(self, path: str) -> str:
        url = f"{self.base_url}/{path.lstrip('/')}"
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "NEXUS-RCSC/0.1 (research; read-only)",
                     "Accept": "application/json, text/plain"},
        )
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    return response.read().decode("utf-8").strip()
            except urllib.error.HTTPError as exc:
                last_error = exc
                # Do not retry permanent client errors (e.g. 400/404). Retry
                # rate limiting and server-side failures only.
                retryable = exc.code == 429 or 500 <= exc.code <= 599
                if not retryable or attempt >= self.retries:
                    raise RuntimeError(f"GET {url} failed with HTTP {exc.code}") from exc
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
                try:
                    delay = min(max(float(retry_after), 0.0), 30.0) if retry_after else min(2 ** attempt, 8)
                except (TypeError, ValueError):
                    delay = min(2 ** attempt, 8)
                time.sleep(delay)
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(min(2 ** attempt, 8))
        raise RuntimeError(f"GET {url} failed: {last_error}") from last_error

    def get_json(self, path: str) -> Any:
        # A successful HTTP response can still contain a truncated or invalid
        # JSON body. Retry that response a bounded number of times as well.
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                return json.loads(self._get_text(path))
            except json.JSONDecodeError as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(min(2 ** attempt, 8))
        raise RuntimeError(f"GET {self.base_url}/{path.lstrip('/')} returned invalid JSON: {last_error}") from last_error

    def get_text(self, path: str) -> str:
        return self._get_text(path)

    def fetch_recent(self, count: int = 10, start_height: int | None = None) -> list[dict[str, Any]]:
        if count < 1:
            raise ValueError("count must be at least 1")
        if count > 5_000:
            raise ValueError("For public API safety, count is capped at 5000 per run")
        if start_height is None:
            start_height = int(self.get_text("blocks/tip/height"))

        summaries: list[dict[str, Any]] = []
        cursor = start_height
        while len(summaries) < count and cursor >= 0:
            batch = self.get_json(f"blocks/{cursor}")
            if not isinstance(batch, list) or not batch:
                break
            summaries.extend(batch)
            cursor = int(batch[-1]["height"]) - 1
        summaries = summaries[:count]

        records: list[dict[str, Any]] = []
        for summary in summaries:
            record: dict[str, Any] = {
                "height": int(summary["height"]),
                "block_hash_reported": summary["id"],
                "timestamp": int(summary["timestamp"]),
                "version_reported": summary.get("version"),
                "merkle_root_reported": summary.get("merkle_root"),
                "previous_block_hash_reported": summary.get("previousblockhash"),
                "nonce_reported": summary.get("nonce"),
                "bits_reported": summary.get("bits"),
                "difficulty": summary.get("difficulty"),
                "tx_count": summary.get("tx_count"),
                "size_bytes": summary.get("size"),
                "weight": summary.get("weight"),
                "source": "mempool.space public REST API",
                "collected_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            try:
                block_hash = str(summary["id"])
                header_hex = self.get_text(f"block/{block_hash}/header").strip('"')
                parsed = parse_header(header_hex)
                record.update(parsed)
                record["reported_hash_matches_header"] = (
                    parsed["block_hash"] == block_hash
                )
                record["reported_fields_match_header"] = all([
                    parsed["version"] == summary.get("version"),
                    parsed["previous_block_hash"] == summary.get("previousblockhash"),
                    parsed["merkle_root"] == summary.get("merkle_root"),
                    parsed["timestamp"] == summary.get("timestamp"),
                    parsed["bits"] == summary.get("bits"),
                    parsed["nonce"] == summary.get("nonce"),
                ])
                status = self.get_json(f"block/{block_hash}/status")
                record["in_best_chain"] = status.get("in_best_chain")

                coinbase_txid = self.get_text(f"block/{block_hash}/txid/0").strip('"')
                tx = self.get_json(f"tx/{coinbase_txid}")
                reward = verify_coinbase_reward(int(summary["height"]), tx.get("vout", []))
                record["coinbase_txid"] = coinbase_txid
                record.update(reward)
                record["coinbase_output_count"] = len(tx.get("vout", []))
                coinbase_vin = (tx.get("vin") or [{}])[0]
                record["coinbase_scriptsig_hex"] = coinbase_vin.get("scriptsig")
                record["coinbase_scriptsig_asm"] = coinbase_vin.get("scriptsig_asm")
                record["coinbase_witness"] = coinbase_vin.get("witness")
                record["coinbase_is_coinbase"] = coinbase_vin.get("is_coinbase")
                record["coinbase_subsidy_comparison_valid"] = True

                # Rebuild the Merkle root from the complete ordered txid list.
                expected_tx_count = summary.get("tx_count")
                txids = self.get_json(f"block/{block_hash}/txids")
                txids_valid_shape = isinstance(txids, list) and all(
                    isinstance(txid, str) and len(txid) == 64
                    and all(char in "0123456789abcdefABCDEF" for char in txid)
                    for txid in txids
                )
                txids_unique = txids_valid_shape and len(set(txid.lower() for txid in txids)) == len(txids)
                txids_coinbase_first = bool(txids_valid_shape and txids and txids[0].lower() == coinbase_txid.lower())
                txids_complete = bool(
                    txids_valid_shape and txids_unique and txids_coinbase_first and txids
                    and (expected_tx_count is None or len(txids) == int(expected_tx_count))
                )
                record["txids_coinbase_first"] = txids_coinbase_first
                record["txids_expected_count"] = expected_tx_count
                record["txids_returned_count"] = len(txids) if isinstance(txids, list) else 0
                record["txids_unique"] = bool(txids_unique)
                record["txids_complete"] = bool(txids_complete)
                if txids_complete:
                    record.update(verify_merkle_root(parsed["merkle_root"], txids))
                else:
                    record["merkle_root_valid"] = False
                    record["merkle_verification_error"] = (
                        "Transaction ID list is malformed, duplicated, missing coinbase at index 0, empty, or does not match tx_count"
                    )

                # Verify each transaction page against the canonical ordered txid
                # list. Missing, duplicated, reordered or malformed rows must not
                # be counted as a complete fee sample.
                fees = 0
                fee_tx_count = 0
                fee_errors: list[str] = []
                if txids_complete:
                    for offset in range(0, len(txids), 25):
                        expected_page_ids = txids[offset:offset + 25]
                        try:
                            page = self.get_json(f"block/{block_hash}/txs/{offset}")
                            if not isinstance(page, list):
                                raise ValueError("transaction page is not a list")
                            actual_page_ids = [item.get("txid") if isinstance(item, dict) else None for item in page]
                            if actual_page_ids != expected_page_ids:
                                raise ValueError("transaction page txids do not match canonical txid order")
                            for tx_item in page:
                                if tx_item["txid"] == coinbase_txid:
                                    continue
                                fee = tx_item.get("fee")
                                if isinstance(fee, bool) or not isinstance(fee, int) or fee < 0:
                                    raise ValueError(f"invalid fee value for txid {tx_item['txid']}")
                                fees += fee
                                fee_tx_count += 1
                        except Exception as fee_exc:
                            fee_errors.append(f"offset {offset}: {type(fee_exc).__name__}: {fee_exc}")
                            break
                else:
                    fee_errors.append("fee pages skipped because the canonical txid list is incomplete")
                record["transaction_fees_sats"] = fees if not fee_errors else None
                record["fee_transactions_count"] = fee_tx_count
                record["fees_complete"] = not fee_errors and fee_tx_count == max(0, len(txids) - 1)
                record["fee_collection_errors"] = fee_errors
                record["coinbase_claim_matches_subsidy_plus_fees"] = (
                    record["coinbase_total_sats"] == record["scheduled_subsidy_sats"] + fees
                    if record["fees_complete"] else None
                )
            except Exception as exc:  # retain block record and expose data gaps
                record["collection_error"] = f"{type(exc).__name__}: {exc}"
            records.append(record)
            if self.pause_seconds:
                time.sleep(self.pause_seconds)
        return records

