#!/usr/bin/env python3
"""Crypto Fieldstation: local-only, read-only research and puzzle workbench.
No wallet signing, no seed/private-key storage, no transaction broadcasting.
"""
from __future__ import annotations
import base64
import copy
import concurrent.futures as cf
import hashlib
import json
import math
import shutil
import subprocess
import multiprocessing as mp
import os
import re
import secrets
import sys
import threading
import time
import urllib.error
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from modules.data_paths import data_path

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = data_path("fieldstation")
ADDRESSES_FILE = DATA_DIR / "addresses.json"
JOURNAL_FILE = DATA_DIR / "journals.json"
LEADS_FILE = DATA_DIR / "leads.json"
HOST = "127.0.0.1"
PORT = int(os.environ.get("FIELDSTATION_PORT", "8765"))
MAX_CANDIDATES = 200_000
MAX_BODY = 12 * 1024 * 1024
ALLOWED_HASHES = {"sha256", "sha512", "md5", "sha1", "double_sha256"}

EVM_NETWORKS = {
    "ethereum": {"rpc": "https://ethereum-rpc.publicnode.com", "symbol": "ETH", "decimals": 18},
    "base": {"rpc": "https://mainnet.base.org", "symbol": "ETH", "decimals": 18},
    "arbitrum": {"rpc": "https://arb1.arbitrum.io/rpc", "symbol": "ETH", "decimals": 18},
    "optimism": {"rpc": "https://mainnet.optimism.io", "symbol": "ETH", "decimals": 18},
    "bnb": {"rpc": "https://bsc-dataseed.binance.org", "symbol": "BNB", "decimals": 18},
    "polygon": {"rpc": "https://polygon-bor-rpc.publicnode.com", "symbol": "POL", "decimals": 18},
    "avalanche": {"rpc": "https://api.avax.network/ext/bc/C/rpc", "symbol": "AVAX", "decimals": 18},
}
SOL_RPC = "https://api.mainnet.solana.com"

DEFAULT_ADDRESSES = [
    {"id": "puzzle-gsmg", "label": "GSMG — adresă publică a premiului", "chain": "bitcoin", "address": "1GSMG1JC9wtdSwfwApgj2xcmJPAwx7prBe", "kind": "public_target", "created_at": "2026-10-20T00:00:00Z"},
    {"id": "puzzle-aoi", "label": "Aoi Nakamoto — adresă publică a premiului", "chain": "bitcoin", "address": "14zMkTgaVXJcxdh4JdWi29MLRR44iUSG9W", "kind": "public_target", "created_at": "2026-10-20T00:00:00Z"},
    {"id": "puzzle-slm", "label": "Smith, Lyle & Moore — escrow public", "chain": "bitcoin", "address": "bc1q0akdjvrc2csau2n3gyxa3xcq0fss852x997m9y", "kind": "public_target", "created_at": "2026-10-20T00:00:00Z"},
]
DEFAULT_CASES = [
    {"id": "Aoi-RBB-077-S2", "name": "Aoi Nakamoto Real Big Block", "kind": "public_crypto_puzzle", "target_address": "14zMkTgaVXJcxdh4JdWi29MLRR44iUSG9W", "reward_published": "0.777 BTC", "status": "unresolved_in_local_journal", "notes": "Historical Wattpad text → MD5/BIP39/BIP44 hypothesis. Must recover exact historical text; do not infer wallet keys.", "sources": ["https://www.wattpad.com/720888559-second", "https://github.com/floflo777/open-crypto-puzzles/issues/39"]},
    {"id": "GSMG-5BTC-FINAL", "name": "GSMG.io 5 BTC Puzzle", "kind": "public_crypto_puzzle", "target_address": "1GSMG1JC9wtdSwfwApgj2xcmJPAwx7prBe", "reward_published": "Historical puzzle; explorer balance must be checked live", "status": "unresolved_in_local_journal", "notes": "OpenSSL Salted__ AES-256-CBC research. This workbench can test candidate passphrases only against supplied public-puzzle ciphertext; no wallet-key derivation.", "sources": ["https://gsmg.io/", "https://blockchain.com/explorer/addresses/btc/1GSMG1JC9wtdSwfwApgj2xcmJPAwx7prBe", "https://github.com/floflo777/open-crypto-puzzles/issues/46"]},
    {"id": "SLM-HUNT2-GLIMMER", "name": "Smith, Lyle & Moore Hunt #2", "kind": "public_crypto_puzzle", "target_address": "bc1q0akdjvrc2csau2n3gyxa3xcq0fss852x997m9y", "reward_published": "0.031777 BTC published; live balance not confirmed", "status": "unresolved_in_local_journal", "notes": "Public riddle/password-gate puzzle; exact current escrow state must be checked.", "sources": ["https://github.com/floflo777/open-crypto-puzzles/issues/48", "https://github.com/floflo777/open-crypto-puzzles/tree/main/2-mid-prizes/smith-lyle-moore-hunt-2-0-032btc"]},
    {"id": "PROOFOFSOLVE-2026-10-24", "name": "ProofOfSolve — free puzzles (upcoming)", "kind": "public_crypto_puzzle", "target_address": "", "reward_published": "Two free prizes reported, approx. 303,140 sats total; recheck rules and funding at launch", "status": "upcoming_unverified", "notes": "Do not treat as claimable before final rules, addresses and eligibility are verified.", "sources": ["https://proofofsolve.com", "https://github.com/floflo777/open-crypto-puzzles/issues/47"]},
]
DEFAULT_LEADS = [
    {"id": "sp1-bounty", "title": "SP1 official bug bounty", "type": "bug_bounty", "url": "https://immunefi.com/bug-bounty/sp1/information/", "status": "research_queue", "eligibility": "Romania not formally confirmed", "transferability": "USDC, program says KYC not required; verify current terms", "cost": "0 RON to read/run local tests; time required", "updated_at": "2026-10-20"},
    {"id": "1inch-aqua", "title": "1inch Aqua official bug bounty", "type": "bug_bounty", "url": "https://immunefi.com/bug-bounty/1inch-aqua/information/", "status": "research_queue", "eligibility": "Romania not formally confirmed", "transferability": "USDC; KYC required per program page", "cost": "0 RON to review; time required", "updated_at": "2026-10-20"},
    {"id": "proof-of-solve", "title": "ProofOfSolve official puzzle project", "type": "puzzle", "url": "https://proofofsolve.com", "status": "verify_at_launch", "eligibility": "Final rules must be checked", "transferability": "BTC prize addresses must be confirmed at launch", "cost": "Two puzzles reported free; third puzzle excluded because it requires payment", "updated_at": "2026-10-20"},
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return copy.deepcopy(default)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        # Preserve malformed file for manual recovery rather than overwrite it.
        backup = path.with_suffix(path.suffix + ".corrupt-backup")
        try:
            path.replace(backup)
        except Exception:
            pass
        save_json(path, default)
        return default


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)

# Importing Fieldstation is side-effect free. Persistent state is loaded only
# when the standalone service is explicitly started.
ADDRESSES = copy.deepcopy(DEFAULT_ADDRESSES)
JOURNALS: dict[str, Any] = {}
LEADS = copy.deepcopy(DEFAULT_LEADS)
CASES = DEFAULT_CASES

# Preserve the material state captured in the preceding research report. These are
# explicitly dated historical observations, not claimed as new checks in this run.
INITIAL_JOURNALS = {
    "Aoi-RBB-077-S2": [
        {"timestamp":"2026-10-19T18:53:00Z", "status":"verificat în jurnalul anterior; neverificat din nou azi", "experiment":"snapshot public on-chain consemnat în raportul anterior", "result":"0.77700000 BTC; 1 UTXO confirmat; 0 UTXO pending. Snapshot-ul nu a fost reinterogat independent în această instalare.", "sources":["https://github.com/floflo777/open-crypto-puzzles/issues/39", "https://www.wattpad.com/720888559-second"], "next_step":"recuperare a unei copii istorice verificabile a textului; dacă nu este accesibilă, notează acces neverificat", "resources_used":"citire documentară anterioară; niciun brute-force atribuit acestei rulări"},
        {"timestamp":"previous report; exact test time not preserved", "status":"neconcludent", "experiment":"familii anterioare de serializare, capitalizare și selecție de paragrafe", "result":"nu este consemnată o potrivire exactă; nu repeta fără o copie istorică nouă sau ipoteză nouă", "sources":["https://github.com/floflo777/open-crypto-puzzles/issues/39"], "next_step":"găsește sursa arhivistică concretă a textului din 2019", "resources_used":"valorile vechi sunt păstrate numai ca rezumat; rate/compute exacte indisponibile"}
    ],
    "GSMG-5BTC-FINAL": [
        {"timestamp":"2026-10-20", "status":"verificat prin snapshotul public consemnat; query exact time not preserved", "experiment":"snapshot explorer pentru adresa premiului", "result":"1.25649674 BTC afișat; 129 tranzacții; ultima tranzacție listată pe 2026-10-13. Nu este interogare independentă de nod și soldul nu conferă drept de claim.", "sources":["https://blockchain.com/explorer/addresses/btc/1GSMG1JC9wtdSwfwApgj2xcmJPAwx7prBe"], "next_step":"reverifică live soldul și regulile oficiale înainte de a raporta disponibilitatea", "resources_used":"consultare web documentată în raportul anterior; compute nefolosit"},
        {"timestamp":"2026-09-03", "status":"istoric; folosit doar ca diferență de comparație", "experiment":"snapshot anterior al soldului", "result":"1.25635374 BTC; față de snapshotul din 2026-10-20 diferența aritmetică este +0.00014300 BTC, compatibilă cu dust, nu dovadă de premiu nou", "sources":["https://blockchain.com/explorer/addresses/btc/1GSMG1JC9wtdSwfwApgj2xcmJPAwx7prBe"], "next_step":"nu interpreta diferența ca revendicare sau supliment de premiu", "resources_used":"calcul aritmetic 1.25649674 - 1.25635374"},
        {"timestamp":"previous report; exact test time not preserved", "status":"neconcludent; nu repeta automat", "experiment":"familii de reducere/partiționare/hash consemnate anterior", "result":"jurnalul public menționează 335 milioane reduceri de obiect 256 simboluri, 490.314 partiționări 16+7, alte lecturi Base58; sweeps de 1.358.577 candidați pentru poarta mică au dat 0 match. Datele brute nu sunt montate în această instalare.", "sources":["https://github.com/floflo777/open-crypto-puzzles/blob/main/1-big-prizes/gsmg-io-5btc-puzzle/analysis/leads.md", "https://github.com/floflo777/open-crypto-puzzles/blob/main/1-big-prizes/gsmg-io-5btc-puzzle/analysis/tested.md", "https://github.com/floflo777/open-crypto-puzzles/issues/46"], "next_step":"extrage fluxul original de 285 litere și documentează cele 29 simboluri eliminate", "resources_used":"istoric public de cercetare; nu s-au repetat aceste spații în instalarea curentă"},
        {"timestamp":"previous report; exact test time not preserved", "status":"discrepanță documentară", "experiment":"reconciliere a surselor pentru cele 11.473 plaintexturi cu padding valid", "result":"analysis/leads.md consemnează relectură prin 40 transformări extinse fără match, în timp ce issue #46 descrie un follow-up încă deschis; versiunea de cod/setul de date trebuie reconcilate", "sources":["https://github.com/floflo777/open-crypto-puzzles/blob/main/1-big-prizes/gsmg-io-5btc-puzzle/analysis/leads.md", "https://github.com/floflo777/open-crypto-puzzles/issues/46"], "next_step":"verifică snapshotul commitului, inputul exact și logurile înainte de repetarea experimentului", "resources_used":"citire de jurnal; nicio rulare de candidat acum"}
    ],
    "SLM-HUNT2-GLIMMER": [
        {"timestamp":"2026-08-16", "status":"istoric; neverificat live în raportul anterior", "experiment":"snapshot de escrow consemnat în README", "result":"3.177700 BTC primit, 0 cheltuit la data snapshotului; soldul curent nu este confirmat", "sources":["https://github.com/floflo777/open-crypto-puzzles/tree/main/2-mid-prizes/smith-lyle-moore-hunt-2-0-032btc"], "next_step":"verifică soldul live înainte de a interpreta recompensa disponibilă", "resources_used":"snapshot documentar, nu rulare curentă"},
        {"timestamp":"2026-10-19", "status":"update publicat; nevalidat ca soluție", "experiment":"rute/porți publicate în issue", "result":"West /message; East /take-a-big-breath; South /havingfunwiththeurl-ilovedthisshowasakid-sosomuch. Title Case este o ipoteză nouă de testat pentru West; pista exactă East/South rămâne neconcludentă.", "sources":["https://github.com/floflo777/open-crypto-puzzles/issues/48"], "next_step":"testează doar variante motivate din formularea publică și consemnează fiecare încercare; verifică disponibilitatea escrowului", "resources_used":"cercetare documentară; aproximativ 5.000 de candidați au fost consemnați ca testați anterior, acoperirea nu este certificată"}
    ],
    "PROOFOFSOLVE-2026-10-24": [
        {"timestamp":"2026-10-19", "status":"estimare de planificare; verificare la lansare obligatorie", "experiment":"verificare pre-lansare în catalog public", "result":"două puzzle-uri raportate gratuite, aproximativ 151.568 și 151.572 sats (303.140 sats împreună); regula finală, eligibilitatea, adreselor exacte și finanțarea nu trebuie presupuse", "sources":["https://proofofsolve.com", "https://github.com/floflo777/open-crypto-puzzles/issues/47"], "next_step":"la data lansării verifică regulile oficiale, soldurile și eligibility; nu plăti taxa pentru Alcatraz", "resources_used":"cercetare web/documentară; nicio revendicare"}
    ]
}
def ensure_data_loaded() -> None:
    """Load and seed persistent state only during explicit Fieldstation startup."""
    global ADDRESSES, JOURNALS, LEADS
    ADDRESSES = load_json(ADDRESSES_FILE, DEFAULT_ADDRESSES)
    JOURNALS = load_json(JOURNAL_FILE, {})
    LEADS = load_json(LEADS_FILE, DEFAULT_LEADS)
    seeded = False
    for case_id, entries in INITIAL_JOURNALS.items():
        if case_id not in JOURNALS:
            JOURNALS[case_id] = copy.deepcopy(entries)
            seeded = True
    if seeded:
        save_json(JOURNAL_FILE, JOURNALS)



STATE_LOCK = threading.RLock()
STATE: dict[str, Any] = {
    "running": False, "stop_requested": False, "job_id": None, "mode": "idle",
    "started_at": None, "elapsed_seconds": 0.0, "attempts": 0, "rate": 0.0,
    "total": 0, "progress": 0.0, "workers": 0, "result": None, "error": None,
    "log": [], "last_balance_refresh": None, "balances": {}, "opportunity_updates": [],
}
STOP_EVENT = threading.Event()
JOB_THREAD: threading.Thread | None = None
SERVER: ThreadingHTTPServer | None = None

# Optional REAL mining runner. No binaries are bundled or downloaded by the app.
# It only starts a user-provided, locally placed ccminer-compatible executable.
MINER_DIR = APP_DIR / "miners"
MINER_BIN = MINER_DIR / "ccminer"
MINER_LOCK = threading.RLock()
MINER_STOP_EVENT = threading.Event()
MINER_PROC = None
MINER_READER_THREAD: threading.Thread | None = None
MINER_WATCHDOG_THREAD: threading.Thread | None = None
MINER_WALLET_FOR_REDACTION = ""
# Conservative mobile thermal guard. Termux:API reports battery temperature, not SoC temperature.
MINER_START_TEMP_MAX_C = 37.0
MINER_WARN_TEMP_C = 37.5
MINER_STOP_TEMP_C = 39.0
MINER_CPU_START_MAX_C = 65.0
MINER_CPU_WARN_C = 68.0
MINER_CPU_STOP_C = 75.0
MINER_START_BATTERY_MIN_PCT = 30
MINER_STOP_BATTERY_MIN_PCT = 20
MINER_THERMAL_POLL_SECONDS = 20
MINER_MAX_THREADS = 2
MINER_MAX_MINUTES = 30
REAL_MINER: dict[str, Any] = {
    "status": "not_configured", "running": False, "pid": None, "started_at": None,
    "elapsed_seconds": 0, "coin": "VRSC / VerusHash", "pool": "", "worker": "",
    "threads": 0, "max_minutes": 0, "hashrate": "—", "accepted_shares": 0,
    "rejected_shares": 0, "log": [], "error": None,
    "battery_temperature_c": None, "cpu_temperature_c": None, "battery_percentage": None,
    "battery_health": None, "battery_plugged": None,
    "thermal_guard": "inactive", "stop_reason": None,
    "note": "Nu este configurat. Nu este inclus niciun miner binar.",
}


def log(message: str) -> None:
    with STATE_LOCK:
        STATE["log"].append({"at": utc_now(), "message": str(message)[:600]})
        STATE["log"] = STATE["log"][-100:]


def journal(case_id: str, entry: dict[str, Any]) -> None:
    if not case_id:
        return
    with STATE_LOCK:
        entries = JOURNALS.setdefault(case_id, [])
        entries.append({"timestamp": utc_now(), **entry})
        JOURNALS[case_id] = entries[-1000:]
        save_json(JOURNAL_FILE, JOURNALS)


def get_default_workers() -> int:
    # Conservative defaults for a phone; the UI allows 1-4 workers with a hard cap.
    return max(1, min(2, (os.cpu_count() or 2) - 1, 4))


def transform_candidate(text: str, transform: str) -> str:
    if transform == "exact": return text
    if transform == "strip": return text.strip()
    if transform == "lower": return text.lower()
    if transform == "upper": return text.upper()
    if transform == "title": return text.title()
    if transform == "reverse": return text[::-1]
    if transform == "sha256_hex": return hashlib.sha256(text.encode("utf-8")).hexdigest()
    if transform == "md5_hex": return hashlib.md5(text.encode("utf-8")).hexdigest()
    if transform == "newline_lf": return text + "\n"
    if transform == "newline_crlf": return text + "\r\n"
    if transform == "remove_spaces": return re.sub(r"\s+", "", text)
    raise ValueError(f"Transformare neacceptată: {transform}")


def digest_bytes(data: bytes, algorithm: str) -> bytes:
    if algorithm == "double_sha256":
        return hashlib.sha256(hashlib.sha256(data).digest()).digest()
    return hashlib.new(algorithm, data).digest()


def hash_batch(items: list[tuple[str, str]], algorithm: str, target_hex: str) -> dict[str, Any]:
    tested = 0
    matches = []
    for candidate, variant in items:
        tested += 1
        digest = digest_bytes(candidate.encode("utf-8"), algorithm).hex()
        if digest.lower() == target_hex.lower():
            matches.append({"candidate": candidate, "variant": variant, "digest": digest})
    return {"tested": tested, "matches": matches}


def has_leading_zero_bits(digest: bytes, bits: int) -> bool:
    if bits <= 0:
        return True
    return int.from_bytes(digest, "big") >> (256 - bits) == 0


def pow_batch(prefix: str, start_nonce: int, count: int, bits: int) -> dict[str, Any]:
    tested = 0
    found = None
    for nonce in range(start_nonce, start_nonce + count):
        candidate = f"{prefix}:{nonce}".encode("utf-8")
        digest = hashlib.sha256(candidate).digest()
        tested += 1
        if has_leading_zero_bits(digest, bits):
            found = {"nonce": nonce, "input": candidate.decode(), "hash": digest.hex(), "leading_zero_bits": bits}
            break
    return {"tested": tested, "found": found}


def openssl_evp_bytes_to_key(password: bytes, salt: bytes, digest_name: str, length: int = 48) -> bytes:
    if digest_name not in ("md5", "sha256", "sha1"):
        raise ValueError("Digest KDF permis: md5, sha1 sau sha256")
    out = b""
    prev = b""
    while len(out) < length:
        prev = hashlib.new(digest_name, prev + password + salt).digest()
        out += prev
    return out[:length]


def aes_batch(items: list[tuple[str, str, str]], ciphertext_b64: str, kdf_digest: str,
              target_plain_sha256: str | None) -> dict[str, Any]:
    try:
        from Crypto.Cipher import AES  # optional: pycryptodome
    except Exception as e:
        return {"tested": 0, "matches": [], "padding_valid": [], "error": "PyCryptodome is not installed. Install it optionally with: pip install pycryptodome"}
    try:
        raw = base64.b64decode(ciphertext_b64, validate=True)
    except Exception:
        return {"tested": 0, "matches": [], "padding_valid": [], "error": "Ciphertext-ul nu este Base64 valid."}
    if len(raw) < 32 or raw[:8] != b"Salted__" or (len(raw) - 16) % 16 != 0:
        return {"tested": 0, "matches": [], "padding_valid": [], "error": "Aștept format OpenSSL Base64 Salted__ cu AES-CBC."}
    salt, enc = raw[8:16], raw[16:]
    tested = 0
    matches, padding_valid = [], []
    for original, variant, passphrase in items:
        tested += 1
        try:
            key_iv = openssl_evp_bytes_to_key(passphrase.encode("utf-8"), salt, kdf_digest, 48)
            plaintext = AES.new(key_iv[:32], AES.MODE_CBC, key_iv[32:48]).decrypt(enc)
            pad = plaintext[-1]
            if pad < 1 or pad > 16 or plaintext[-pad:] != bytes([pad]) * pad:
                continue
            plaintext = plaintext[:-pad]
            plain_hex = hashlib.sha256(plaintext).hexdigest()
            printable_ratio = sum((32 <= b < 127) or b in (9, 10, 13) for b in plaintext) / max(1, len(plaintext))
            summary = {"candidate": original, "variant": variant, "passphrase_sha256": hashlib.sha256(passphrase.encode()).hexdigest(), "plaintext_sha256": plain_hex, "plaintext_bytes": len(plaintext), "printable_ratio": round(printable_ratio, 4)}
            padding_valid.append(summary)
            if target_plain_sha256 and plain_hex.lower() == target_plain_sha256.lower():
                matches.append(summary)
        except Exception:
            continue
    return {"tested": tested, "matches": matches, "padding_valid": padding_valid}


def chunks(items: list[Any], size: int):
    for i in range(0, len(items), size):
        yield items[i:i+size]


def update_progress(increment: int, total: int, started: float) -> None:
    elapsed = max(0.001, time.monotonic() - started)
    with STATE_LOCK:
        STATE["attempts"] += increment
        STATE["elapsed_seconds"] = round(elapsed, 2)
        STATE["rate"] = round(STATE["attempts"] / elapsed, 2)
        STATE["total"] = total
        STATE["progress"] = min(100.0, round(STATE["attempts"] / total * 100, 2)) if total > 0 else 0.0


def execute_batches(mode: str, tasks: list[Any], worker_fn, worker_args: tuple, workers: int,
                    batch_size: int, total_items: int) -> tuple[list[Any], int]:
    """Bounded process queue with stop checks between small task batches."""
    results: list[Any] = []
    submitted = iter(chunks(tasks, batch_size))
    pending: set[cf.Future] = set()
    tested_total = 0
    started = time.monotonic()
    ctx = mp.get_context("spawn")
    with cf.ProcessPoolExecutor(max_workers=workers, mp_context=ctx) as executor:
        for _ in range(workers * 2):
            if STOP_EVENT.is_set(): break
            try: batch = next(submitted)
            except StopIteration: break
            pending.add(executor.submit(worker_fn, batch, *worker_args))
        while pending:
            if STOP_EVENT.is_set():
                for future in pending: future.cancel()
                break
            done, pending = cf.wait(pending, timeout=0.25, return_when=cf.FIRST_COMPLETED)
            if not done:
                continue
            for future in done:
                result = future.result()
                tested = int(result.get("tested", 0))
                tested_total += tested
                update_progress(tested, total_items, started)
                results.extend(result.get("matches", []))
                results.extend(result.get("found_items", []))
                if result.get("found"):
                    results.append(result["found"])
                    STOP_EVENT.set()
                if STOP_EVENT.is_set():
                    for queued in pending: queued.cancel()
                    break
                try: batch = next(submitted)
                except StopIteration: continue
                pending.add(executor.submit(worker_fn, batch, *worker_args))
    return results, tested_total


def reset_job(mode: str, workers: int, total: int) -> None:
    with STATE_LOCK:
        STATE.update({"running": True, "stop_requested": False, "job_id": secrets.token_hex(6),
                      "mode": mode, "started_at": utc_now(), "elapsed_seconds": 0.0,
                      "attempts": 0, "rate": 0.0, "total": total, "progress": 0.0,
                      "workers": workers, "result": None, "error": None})
        STATE["log"].append({"at": utc_now(), "message": f"Lucrare pornită: {mode}; workers={workers}; items={total}."})
        STATE["log"] = STATE["log"][-100:]
    STOP_EVENT.clear()


def stop_job() -> None:
    STOP_EVENT.set()
    with STATE_LOCK:
        STATE["stop_requested"] = True
        log_message = "Oprire cerută de utilizator; nu se mai programează loturi noi."
        STATE["log"].append({"at": utc_now(), "message": log_message})
        STATE["log"] = STATE["log"][-100:]


def finish_job(result: dict[str, Any], error: str | None = None) -> None:
    with STATE_LOCK:
        elapsed = max(0.001, STATE.get("elapsed_seconds", 0.0))
        STATE["running"] = False
        STATE["stop_requested"] = False
        STATE["elapsed_seconds"] = round(elapsed, 2)
        STATE["result"] = result
        STATE["error"] = error
        STATE["log"].append({"at": utc_now(), "message": error or "Lucrare încheiată; verificați statutul rezultatului."})
        STATE["log"] = STATE["log"][-100:]


def start_hash_job(case_id: str, algorithm: str, target: str, candidate_text: str, transforms: list[str], workers: int):
    global JOB_THREAD
    if len(candidate_text.encode("utf-8")) > 8 * 1024 * 1024:
        raise ValueError("Fișierul candidaților este prea mare (max. 8 MiB).")
    if algorithm not in ALLOWED_HASHES:
        raise ValueError("Algoritm de hash neacceptat.")
    if not re.fullmatch(r"[0-9a-fA-F]{32,128}", target):
        raise ValueError("Ținta trebuie să fie un hash hex exact (32–128 caractere).")
    expected_len = {"md5":32, "sha1":40, "sha256":64, "sha512":128, "double_sha256":64}[algorithm]
    if len(target) != expected_len:
        raise ValueError(f"Lungimea țintei pentru {algorithm} trebuie să fie {expected_len} caractere hex.")
    if not transforms:
        transforms = ["exact"]
    allowed_transforms = {"exact", "strip", "lower", "upper", "title", "reverse", "sha256_hex", "md5_hex", "newline_lf", "newline_crlf", "remove_spaces"}
    if any(t not in allowed_transforms for t in transforms):
        raise ValueError("Transformare necunoscută.")
    lines = candidate_text.splitlines()
    if not lines:
        raise ValueError("Introdu cel puțin un candidat, câte unul pe linie.")
    if len(lines) > MAX_CANDIDATES:
        raise ValueError(f"Maximum {MAX_CANDIDATES} linii candidate la o rulare.")
    variants, seen = [], set()
    for line in lines:
        for transform in transforms:
            value = transform_candidate(line, transform)
            key = (value, transform)
            if key not in seen:
                if len(variants) >= MAX_CANDIDATES:
                    raise ValueError(f"Transformările depășesc limita de {MAX_CANDIDATES} teste; micșorează setul.")
                variants.append(key); seen.add(key)
    workers = max(1, min(4, int(workers)))
    reset_job("exact_hash_match", workers, len(variants))

    def run():
        started = time.monotonic()
        all_matches, tested = [], 0
        actual_workers = workers
        try:
            items = [(candidate, variant) for candidate, variant in variants]
            try:
                all_matches, tested = execute_batches("exact_hash_match", items, hash_batch, (algorithm, target), workers, 2000, len(items))
            except Exception as parallel_exc:
                # Safe fallback: the tool remains usable if Android's Python cannot spawn workers.
                log(f"Multiprocessing indisponibil; fallback secvențial: {parallel_exc}")
                actual_workers = 1
                with STATE_LOCK: STATE["workers"] = 1
                all_matches, tested = [], 0
                for batch in chunks(items, 2000):
                    if STOP_EVENT.is_set(): break
                    res = hash_batch(batch, algorithm, target)
                    tested += res["tested"]; all_matches.extend(res["matches"])
                    update_progress(res["tested"], len(items), started)
            elapsed = max(0.001, time.monotonic() - started)
            result = {"case_id": case_id, "algorithm": algorithm, "target": target.lower(), "tested": tested,
                      "match_count": len(all_matches), "matches": all_matches,
                      "status": "VERIFIED_EXACT_DIGEST_MATCH" if all_matches else ("STOPPED_NO_MATCH" if STOP_EVENT.is_set() else "NO_MATCH_IN_TESTED_SET"),
                      "workers_used": actual_workers, "elapsed_seconds": round(elapsed,2), "measured_candidates_per_second": round(tested/elapsed,2),
                      "scope_note": "Numai candidații furnizați și transformările selectate; nu s-au căutat chei/seed-uri de portofele."}
            journal(case_id, {"status": result["status"], "experiment": "exact hash comparison", "algorithm": algorithm, "target": target.lower(), "candidates_tested": tested, "workers_used": actual_workers, "rate_per_second": round(tested/elapsed,2), "matches": all_matches, "result": "eșuat" if not all_matches else "verificat exact", "sources": [], "next_step": "verifică algoritmul și sursa candidate-list înainte de a interpreta potrivirea"})
            finish_job(result)
        except Exception as exc:
            finish_job({"status": "ERROR"}, str(exc))
    JOB_THREAD = threading.Thread(target=run, name="hash-job", daemon=True); JOB_THREAD.start()


def start_aes_job(case_id: str, ciphertext_b64: str, candidate_text: str, pass_transforms: list[str],
                  kdf_digest: str, target_plain_sha256: str, workers: int):
    global JOB_THREAD
    if len(candidate_text.encode("utf-8")) > 8 * 1024 * 1024: raise ValueError("Lista de candidați depășește 8 MiB.")
    if kdf_digest not in ("md5", "sha1", "sha256"): raise ValueError("KDF neacceptat.")
    if target_plain_sha256 and not re.fullmatch(r"[0-9a-fA-F]{64}", target_plain_sha256): raise ValueError("SHA-256 plaintext trebuie să aibă 64 caractere hex.")
    try: import Crypto.Cipher.AES  # noqa: F401
    except Exception: raise ValueError("Funcția AES necesită pachetul opțional pycryptodome; instalează-l numai dacă dorești această funcție.")
    candidate_lines = candidate_text.splitlines()
    if not candidate_lines: raise ValueError("Introdu candidați; nu se generează o wordlist automat.")
    if len(candidate_lines) > MAX_CANDIDATES: raise ValueError(f"Maximum {MAX_CANDIDATES} candidați.")
    allowed = {"raw", "sha256_hex", "md5_hex", "strip", "lower", "upper", "title"}
    if any(t not in allowed for t in pass_transforms): raise ValueError("Transformare de passphrase necunoscută.")
    if not pass_transforms: pass_transforms = ["raw"]
    items, seen = [], set()
    for candidate in candidate_lines:
        for transform in pass_transforms:
            if transform == "raw": val = candidate
            elif transform == "sha256_hex": val = hashlib.sha256(candidate.encode()).hexdigest()
            elif transform == "md5_hex": val = hashlib.md5(candidate.encode()).hexdigest()
            else: val = transform_candidate(candidate, transform)
            key = (candidate, transform, val)
            if key not in seen: items.append(key); seen.add(key)
    if len(items) > MAX_CANDIDATES: raise ValueError(f"Maximum {MAX_CANDIDATES} essais après transformations.")
    workers = max(1, min(4, int(workers)))
    reset_job("openssl_aes_candidate_lab", workers, len(items))

    def run():
        started = time.monotonic(); tested = 0; padding = []; matches = []; error = None
        try:
            # AES workload uses process workers in bounded chunks. A padding-valid candidate is NOT a verified solution.
            ctx = mp.get_context("spawn")
            with cf.ProcessPoolExecutor(max_workers=workers, mp_context=ctx) as executor:
                task_iter = iter(chunks(items, 250))
                pending: set[cf.Future] = set()
                for _ in range(workers * 2):
                    if STOP_EVENT.is_set(): break
                    try: b = next(task_iter)
                    except StopIteration: break
                    pending.add(executor.submit(aes_batch, b, ciphertext_b64, kdf_digest, target_plain_sha256 or None))
                while pending:
                    if STOP_EVENT.is_set():
                        for f in pending: f.cancel()
                        break
                    done, pending = cf.wait(pending, timeout=.25, return_when=cf.FIRST_COMPLETED)
                    for future in done:
                        res = future.result(); tested += res.get("tested", 0)
                        padding.extend(res.get("padding_valid", [])); matches.extend(res.get("matches", []))
                        if res.get("error"): error = res["error"]
                        update_progress(res.get("tested", 0), len(items), started)
                        if STOP_EVENT.is_set(): break
                        try: b = next(task_iter)
                        except StopIteration: continue
                        pending.add(executor.submit(aes_batch, b, ciphertext_b64, kdf_digest, target_plain_sha256 or None))
            status = "VERIFIED_EXACT_PLAINTEXT_SHA256_MATCH" if matches else ("STOPPED" if STOP_EVENT.is_set() else ("PADDING_VALID_UNVERIFIED" if padding else "NO_VALID_PADDING"))
            result = {"case_id": case_id, "status": status, "kdf_digest": kdf_digest, "target_plaintext_sha256": target_plain_sha256 or None,
                      "tested": tested, "exact_match_count": len(matches), "exact_matches": matches,
                      "padding_valid_candidates_unverified": padding[:100], "padding_valid_total": len(padding), "error": error,
                      "security_note": "Padding valid is not proof. Only exact plaintext SHA-256 match is labelled verified. Plaintext is not displayed; no wallet-key derivation is performed."}
            journal(case_id, {"status": status, "experiment": "OpenSSL Salted__ AES-256-CBC candidate test", "kdf_digest": kdf_digest, "candidates_tested": tested, "workers_used": workers, "rate_per_second": round(tested/max(.001,time.monotonic()-started),2), "exact_matches": matches, "padding_valid_total": len(padding), "result": "verificat exact" if matches else "neconcludent/eșuat", "sources": [], "next_step": "obține un SHA-256 independent al plaintextului așteptat; padding-ul singur nu validează soluția"})
            finish_job(result, error)
        except Exception as exc:
            finish_job({"status": "ERROR"}, str(exc))
    JOB_THREAD = threading.Thread(target=run, name="aes-job", daemon=True); JOB_THREAD.start()


def start_pow_job(prefix: str, bits: int, max_seconds: int, workers: int):
    global JOB_THREAD
    if len(prefix) > 200 or not prefix: raise ValueError("Prefixul trebuie să aibă 1–200 caractere.")
    bits = int(bits); max_seconds = int(max_seconds); workers = int(workers)
    if not 1 <= bits <= 32: raise ValueError("Dificultatea demonstrativă trebuie să fie 1–32 biți.")
    if not 1 <= max_seconds <= 900: raise ValueError("Durata permisă este 1–900 secunde.")
    workers = max(1, min(4, workers))
    reset_job("sha256_toy_pow_benchmark", workers, 0)

    def run():
        started = time.monotonic(); nonce_start = 0; batch_size = 10000; total = 0; found = None
        try:
            ctx = mp.get_context("spawn")
            with cf.ProcessPoolExecutor(max_workers=workers, mp_context=ctx) as executor:
                while not STOP_EVENT.is_set() and time.monotonic() - started < max_seconds and found is None:
                    futures = []
                    for i in range(workers * 2):
                        futures.append(executor.submit(pow_batch, prefix, nonce_start + i*batch_size, batch_size, bits))
                    pending = set(futures)
                    for future in cf.as_completed(pending, timeout=max(1, max_seconds - (time.monotonic()-started))):
                        if STOP_EVENT.is_set():
                            for f in pending: f.cancel()
                            break
                        res = future.result(); total += res.get("tested", 0)
                        update_progress(res.get("tested",0), 0, started)
                        if res.get("found"):
                            found = res["found"]; STOP_EVENT.set(); break
                        pending.discard(future)
                    nonce_start += workers * 2 * batch_size
            elapsed = max(.001, time.monotonic()-started)
            status = "FOUND_TOY_POW_NONCE" if found else ("STOPPED" if STATE.get("stop_requested") else ("TIME_LIMIT_REACHED" if elapsed >= max_seconds else "NO_MATCH"))
            result = {"status": status, "prefix": prefix, "difficulty_bits": bits, "tested": total, "elapsed_seconds": round(elapsed,2), "hashes_per_second": round(total/elapsed,2), "found": found,
                      "warning": "Acesta este un benchmark PoW SHA-256 demonstrativ. Nu minează Bitcoin sau altă monedă și nu creează recompense transferabile."}
            journal("LOCAL-CPU-POW-BENCHMARK", {"status": status, "experiment": "toy SHA-256 proof-of-work benchmark", "difficulty_bits": bits, "tested": total, "seconds": round(elapsed,2), "hashes_per_second": round(total/elapsed,2), "found": found, "result": "benchmark; nu este coin-mining", "next_step": "compară viteza/temperatura la 1 și 2 worker-i; oprește dacă telefonul se încălzește"})
            finish_job(result)
        except cf.TimeoutError:
            elapsed=max(.001,time.monotonic()-started)
            finish_job({"status":"TIME_LIMIT_REACHED","tested":total,"elapsed_seconds":round(elapsed,2),"hashes_per_second":round(total/elapsed,2),"found":found,"warning":"Nu minează o monedă reală."})
        except Exception as exc:
            finish_job({"status":"ERROR"}, str(exc))
    JOB_THREAD = threading.Thread(target=run, name="pow-job", daemon=True); JOB_THREAD.start()


def _miner_safe_status() -> dict[str, Any]:
    with MINER_LOCK:
        out = dict(REAL_MINER)
        out["log"] = list(REAL_MINER.get("log", []))[-60:]
        if MINER_PROC is not None and MINER_PROC.poll() is None and REAL_MINER.get("started_monotonic"):
            out["elapsed_seconds"] = max(0, int(time.monotonic() - REAL_MINER["started_monotonic"]))
            out["running"] = True
        out.pop("started_monotonic", None)
        return out


def read_android_cpu_temperature() -> float | None:
    """Try readable Linux thermal zones; Android vendors may deny these files."""
    root = Path("/sys/class/thermal")
    temperatures: list[float] = []
    if not root.is_dir():
        return None
    cpu_terms = ("cpu", "soc", "ap-thermal", "gpu", "cluster", "tsens")
    for zone in root.glob("thermal_zone*"):
        try:
            zone_type = (zone / "type").read_text(encoding="utf-8", errors="ignore").strip().lower()
            if not any(term in zone_type for term in cpu_terms):
                continue
            raw = float((zone / "temp").read_text(encoding="utf-8", errors="ignore").strip())
            # Kernel thermal sysfs usually reports millidegrees Celsius; some devices report °C.
            if abs(raw) >= 1000:
                raw /= 1000.0
            elif abs(raw) >= 200:
                raw /= 10.0
            if math.isfinite(raw) and -10 <= raw <= 150:
                temperatures.append(raw)
        except Exception:
            continue
    return round(max(temperatures), 1) if temperatures else None


def read_android_battery_status() -> dict[str, Any]:
    """Read Android battery telemetry using Termux:API. Never invent a temperature."""
    command = shutil.which("termux-battery-status")
    if not command:
        raise ValueError(
            "Protecția termică nu este disponibilă: lipsește termux-battery-status. "
            "Instalează aplicația Termux:API din aceeași sursă ca Termux și rulează «pkg install termux-api». "
            "Minarea este blocată până când senzorul poate fi citit."
        )
    try:
        completed = subprocess.run([command], capture_output=True, text=True, timeout=6, check=False)
    except Exception as exc:
        raise ValueError(f"Nu pot citi senzorul de baterie prin Termux:API ({type(exc).__name__}); minarea rămâne blocată/oprită.") from exc
    if completed.returncode != 0:
        raise ValueError("Termux:API nu a putut citi bateria; verifică aplicația Termux:API și permisiunile. Minarea rămâne blocată/oprită.")
    try:
        raw = json.loads(completed.stdout)
        temperature = float(raw["temperature"])
        percentage = float(raw["percentage"])
        health = str(raw.get("health", "UNKNOWN")).upper()
        plugged = str(raw.get("plugged", "UNKNOWN")).upper()
        status = str(raw.get("status", "UNKNOWN")).upper()
    except Exception as exc:
        raise ValueError("Răspunsul Termux:API nu conține temperatură/procent valide; minarea rămâne blocată/oprită.") from exc
    if not math.isfinite(temperature) or not -10 <= temperature <= 100:
        raise ValueError("Temperatura raportată de Termux:API este invalidă; minarea rămâne blocată/oprită.")
    if not math.isfinite(percentage) or not 0 <= percentage <= 100:
        raise ValueError("Procentul bateriei raportat de Termux:API este invalid; minarea rămâne blocată/oprită.")
    return {"temperature": temperature, "cpu_temperature": read_android_cpu_temperature(), "percentage": percentage, "health": health, "plugged": plugged, "status": status}


def _publish_battery_status(battery: dict[str, Any]) -> None:
    with MINER_LOCK:
        REAL_MINER["battery_temperature_c"] = round(float(battery["temperature"]), 1)
        cpu_temp = battery.get("cpu_temperature")
        REAL_MINER["cpu_temperature_c"] = round(float(cpu_temp), 1) if cpu_temp is not None else None
        REAL_MINER["battery_percentage"] = round(float(battery["percentage"]))
        REAL_MINER["battery_health"] = str(battery.get("health", "UNKNOWN"))
        REAL_MINER["battery_plugged"] = str(battery.get("plugged", "UNKNOWN"))
        temp = float(battery["temperature"])
        REAL_MINER["thermal_guard"] = "warning" if temp >= MINER_WARN_TEMP_C else "active"


def battery_safety_reason(battery: dict[str, Any], starting: bool) -> str | None:
    """Return a human-readable reason to block/stop mining, or None if safe enough to continue."""
    try:
        temp = float(battery["temperature"])
        pct = float(battery["percentage"])
        health = str(battery.get("health", "UNKNOWN")).upper()
        plugged = str(battery.get("plugged", "UNKNOWN")).upper()
    except Exception:
        return "Datele senzorului bateriei sunt incomplete; opresc pentru siguranță."
    if not math.isfinite(temp) or not math.isfinite(pct):
        return "Datele termice/baterie sunt invalide; opresc pentru siguranță."
    if health != "GOOD":
        return f"Starea bateriei este {health}, nu GOOD; minarea nu este permisă."
    try:
        cpu_temp = battery.get("cpu_temperature")
        cpu_temp = float(cpu_temp) if cpu_temp is not None else None
    except Exception:
        cpu_temp = None
    if cpu_temp is not None and math.isfinite(cpu_temp):
        if starting and cpu_temp >= MINER_CPU_START_MAX_C:
            return f"Senzorul CPU/SoC raportează {cpu_temp:.1f}°C; pornește numai sub {MINER_CPU_START_MAX_C:.1f}°C."
        if not starting and cpu_temp >= MINER_CPU_STOP_C:
            return f"Oprire termică: senzorul CPU/SoC a ajuns la {cpu_temp:.1f}°C (prag {MINER_CPU_STOP_C:.1f}°C)."
    if plugged != "UNPLUGGED":
        return "Telefonul este conectat la alimentare; pentru acest profil termic conservator, minarea este blocată/oprită."
    if starting:
        if temp >= MINER_START_TEMP_MAX_C:
            return f"Bateria are {temp:.1f}°C; pornește numai sub {MINER_START_TEMP_MAX_C:.1f}°C și după răcire."
        if pct < MINER_START_BATTERY_MIN_PCT:
            return f"Bateria este la {pct:.0f}%; pentru protecție, pornește numai de la {MINER_START_BATTERY_MIN_PCT}% în sus."
    else:
        if temp >= MINER_STOP_TEMP_C:
            return f"Oprire termică: bateria a ajuns la {temp:.1f}°C (prag {MINER_STOP_TEMP_C:.1f}°C)."
        if pct <= MINER_STOP_BATTERY_MIN_PCT:
            return f"Oprire de protecție: bateria a scăzut la {pct:.0f}%."
    return None

def _append_miner_log(message: str) -> None:
    msg = str(message).strip()
    if not msg:
        return
    wallet = MINER_WALLET_FOR_REDACTION
    if wallet:
        msg = msg.replace(wallet, "[adresa-wallet-redactată]")
    with MINER_LOCK:
        lines = REAL_MINER.setdefault("log", [])
        lines.append({"at": utc_now(), "message": msg[:500]})
        REAL_MINER["log"] = lines[-80:]


def _miner_reader(proc) -> None:
    global MINER_PROC
    try:
        stream = proc.stdout
        if stream is not None:
            for raw in iter(stream.readline, ""):
                line = raw.strip()
                if not line:
                    continue
                wallet = MINER_WALLET_FOR_REDACTION
                if wallet:
                    line = line.replace(wallet, "[adresa-wallet-redactată]")
                hash_match = re.search(r"\b([0-9]+(?:\.[0-9]+)?)\s*((?:k|M|G|T)?H/s)\b", line)
                share_match = re.search(r"accepted\s*:?\s*(\d+)\s*/\s*(\d+)", line, re.IGNORECASE)
                with MINER_LOCK:
                    if hash_match:
                        REAL_MINER["hashrate"] = f"{hash_match.group(1)} {hash_match.group(2)}"
                    if share_match:
                        REAL_MINER["accepted_shares"] = int(share_match.group(1))
                        REAL_MINER["rejected_shares"] = max(0, int(share_match.group(2)) - int(share_match.group(1)))
                    elif re.search(r"\baccepted\b", line, re.IGNORECASE):
                        REAL_MINER["accepted_shares"] = int(REAL_MINER.get("accepted_shares", 0)) + 1
                    elif re.search(r"\brejected\b|\binvalid share\b", line, re.IGNORECASE):
                        REAL_MINER["rejected_shares"] = int(REAL_MINER.get("rejected_shares", 0)) + 1
                _append_miner_log(line)
    except Exception as exc:
        _append_miner_log(f"Citire log miner: {type(exc).__name__}: {exc}")
    finally:
        try:
            code = proc.wait(timeout=2)
        except Exception:
            code = proc.poll()
        with MINER_LOCK:
            if MINER_PROC is proc:
                REAL_MINER["running"] = False
                REAL_MINER["pid"] = None
                REAL_MINER["elapsed_seconds"] = max(0, int(time.monotonic() - REAL_MINER.get("started_monotonic", time.monotonic())))
                if REAL_MINER.get("stop_reason") == "Limită de timp atinsă.":
                    REAL_MINER["status"] = "stopped_time_limit"
                elif REAL_MINER.get("stop_reason") and REAL_MINER.get("stop_reason") != "Oprire manuală de către utilizator.":
                    REAL_MINER["status"] = "stopped_safety_guard"
                else:
                    REAL_MINER["status"] = "stopped" if MINER_STOP_EVENT.is_set() else ("finished" if code == 0 else "exited_with_error")
                REAL_MINER["running"] = False
                if code not in (0, None) and not REAL_MINER.get("error") and REAL_MINER.get("status") != "stopped_safety_guard":
                    REAL_MINER["error"] = f"Minerul s-a închis cu codul {code}. Verifică logul, poolul și binarul."
                REAL_MINER["note"] = "Acțiunile poolului/share-urile nu garantează payout; verifică pragurile și istoricul poolului."
                MINER_PROC = None
        _append_miner_log(f"Proces miner încheiat (cod {code}).")


def _miner_watchdog(proc, deadline: float) -> None:
    """Enforce a hard run limit and periodically fail-safe on Android battery telemetry."""
    next_thermal_check = 0.0
    last_warning = None
    while proc.poll() is None:
        if MINER_STOP_EVENT.is_set():
            return
        now = time.monotonic()
        if now >= deadline:
            _append_miner_log("Limită automată de timp atinsă; opresc procesul pentru protecția telefonului.")
            with MINER_LOCK:
                REAL_MINER["stop_reason"] = "Limită de timp atinsă."
                REAL_MINER["thermal_guard"] = "stopped_time_limit"
            MINER_STOP_EVENT.set()
            try: proc.terminate()
            except Exception: pass
            return
        if now >= next_thermal_check:
            try:
                battery = read_android_battery_status()
                _publish_battery_status(battery)
                reason = battery_safety_reason(battery, starting=False)
                if float(battery["temperature"]) >= MINER_WARN_TEMP_C and last_warning != round(float(battery["temperature"])):
                    last_warning = round(float(battery["temperature"]))
                    _append_miner_log(f"Atenție termică: temperatura bateriei raportată de Android este {float(battery['temperature']):.1f}°C. Monitorizare activă.")
                cpu_temp = battery.get("cpu_temperature")
                if cpu_temp is not None and float(cpu_temp) >= MINER_CPU_WARN_C:
                    _append_miner_log(f"Atenție CPU/SoC: senzorul termic raportă {float(cpu_temp):.1f}°C; pragul de oprire este {MINER_CPU_STOP_C:.1f}°C.")
            except Exception as exc:
                reason = f"Protecția termică nu mai poate citi bateria: {str(exc)[:180]}"
            if reason:
                _append_miner_log(reason + " Oprire automată.")
                with MINER_LOCK:
                    REAL_MINER["stop_reason"] = reason
                    REAL_MINER["thermal_guard"] = "stopped_safety_guard"
                    REAL_MINER["error"] = reason
                MINER_STOP_EVENT.set()
                try: proc.terminate()
                except Exception: pass
                return
            next_thermal_check = now + MINER_THERMAL_POLL_SECONDS
        time.sleep(1)

def start_real_miner(wallet: str, pool_host: str, pool_port: int, worker: str, threads: int, max_minutes: int, consent: bool) -> dict[str, Any]:
    global MINER_PROC, MINER_READER_THREAD, MINER_WATCHDOG_THREAD, MINER_WALLET_FOR_REDACTION
    if not consent:
        raise ValueError("Bifează confirmarea că adresa este a ta și că accepți consumul CPU/rețeaua poolului.")
    wallet = wallet.strip()
    if not re.fullmatch(r"R[1-9A-HJ-NP-Za-km-z]{25,40}", wallet):
        raise ValueError("Adresa VRSC nu are formatul așteptat. Copiază adresa de primire din Verus Mobile/Desktop; nu folosi seed sau cheie privată.")
    pool_host = pool_host.strip().lower().rstrip(".")
    if len(pool_host) > 253 or not pool_host or any(not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label) for label in pool_host.split(".")):
        raise ValueError("Hostname pool invalid. Introdu doar hostname-ul oficial, fără protocol, cale sau URL complet.")
    pool_port = int(pool_port); threads = int(threads); max_minutes = int(max_minutes)
    if not 1 <= pool_port <= 65535: raise ValueError("Portul trebuie să fie între 1 și 65535.")
    if not 1 <= threads <= MINER_MAX_THREADS: raise ValueError("Protecția telefonului permite maximum 2 thread-uri; recomand 1.")
    if not 1 <= max_minutes <= MINER_MAX_MINUTES: raise ValueError("Protecția telefonului limitează fiecare rundă la maximum 30 de minute.")
    worker = worker.strip() or "xiaomi17tpro"
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,24}", worker): raise ValueError("Numele workerului poate conține doar litere, cifre, _ sau -, max. 24 caractere.")
    if not MINER_BIN.is_file():
        raise ValueError("Nu există binarul minerului. Crypto Fieldstation nu descarcă și nu include binare. Pune un ccminer compatibil VerusHash, verificat dintr-o sursă de încredere, în crypto_fieldstation/miners/ccminer și acordă-i permisiunea de execuție.")
    if not os.access(MINER_BIN, os.X_OK):
        raise ValueError("Binarul miners/ccminer nu este executabil. În Termux rulează chmod +x miners/ccminer după ce verifici sursa și integritatea lui.")
    if not MINER_BIN.is_file() or MINER_BIN.resolve().parent != MINER_DIR.resolve():
        raise ValueError("Binarul trebuie să fie fișierul local fix miners/ccminer, nu o cale externă.")

    # Fail-closed: mining is not permitted if Android's battery telemetry is unavailable.
    battery = read_android_battery_status()
    _publish_battery_status(battery)
    safety_reason = battery_safety_reason(battery, starting=True)
    if safety_reason:
        _append_miner_log("Start refuzat: " + safety_reason)
        raise ValueError(safety_reason)

    with MINER_LOCK:
        if MINER_PROC is not None and MINER_PROC.poll() is None:
            raise ValueError("Minerul rulează deja. Oprește-l înainte de a porni altul.")
        MINER_STOP_EVENT.clear()
        url = f"stratum+tcp://{pool_host}:{pool_port}"
        username = f"{wallet}.{worker}"
        command = [str(MINER_BIN), "-a", "verus", "-o", url, "-u", username, "-p", "x", "-t", str(threads)]
        try:
            proc = __import__("subprocess").Popen(
                command, cwd=str(MINER_DIR), stdin=__import__("subprocess").DEVNULL,
                stdout=__import__("subprocess").PIPE, stderr=__import__("subprocess").STDOUT,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
                close_fds=True,
            )
        except Exception as exc:
            raise ValueError(f"Nu pot porni minerul: {type(exc).__name__}: {exc}") from exc
        MINER_PROC = proc
        MINER_WALLET_FOR_REDACTION = wallet
        REAL_MINER.update({
            "status": "starting", "running": True, "pid": proc.pid, "started_at": utc_now(),
            "started_monotonic": time.monotonic(), "elapsed_seconds": 0, "coin": "VRSC / VerusHash",
            "pool": f"{pool_host}:{pool_port}", "worker": worker, "threads": threads,
            "max_minutes": max_minutes, "hashrate": "—", "accepted_shares": 0,
            "rejected_shares": 0, "log": [], "error": None,
            "battery_temperature_c": round(float(battery["temperature"]), 1),
            "cpu_temperature_c": round(float(battery["cpu_temperature"]), 1) if battery.get("cpu_temperature") is not None else None,
            "battery_percentage": round(float(battery["percentage"])),
            "battery_health": battery.get("health"), "battery_plugged": battery.get("plugged"),
            "thermal_guard": "active", "stop_reason": None,
            "note": "Protecție activă: Termux:API monitorizează temperatura bateriei; max. 2 thread-uri și 30 min. Senzorul bateriei nu este temperatura SoC/CPU.",
        })
    _append_miner_log(f"Pornit VerusHash miner; pool={pool_host}:{pool_port}; worker={worker}; threads={threads}; limită={max_minutes} min.")
    MINER_READER_THREAD = threading.Thread(target=_miner_reader, args=(proc,), name="real-miner-reader", daemon=True)
    MINER_READER_THREAD.start()
    MINER_WATCHDOG_THREAD = threading.Thread(target=_miner_watchdog, args=(proc, time.monotonic() + max_minutes * 60), name="real-miner-watchdog", daemon=True)
    MINER_WATCHDOG_THREAD.start()
    journal("REAL-MINING-VRSC", {
        "status": "running; payout not yet verified", "experiment": "VerusHash CPU mining via user-provided ccminer-compatible binary",
        "result": f"Process started; pool={pool_host}:{pool_port}; worker={worker}; threads={threads}; time limit={max_minutes} min. Wallet address intentionally omitted from journal.",
        "sources": ["https://verus.io/mining", "https://docs.verus.io/economy/start-mining.html"],
        "next_step": "verify accepted shares in miner log and pool dashboard; confirm payout threshold and transaction on-chain",
        "resources_used": f"user's own CPU; no paid compute; {threads} thread(s); max {max_minutes} minutes; thermal guard via Termux:API; actual energy use not measured",
    })
    return _miner_safe_status()


def stop_real_miner() -> dict[str, Any]:
    global MINER_PROC
    with MINER_LOCK:
        proc = MINER_PROC
        if proc is None or proc.poll() is not None:
            REAL_MINER["running"] = False
            if REAL_MINER.get("status") in ("not_configured", "starting"):
                REAL_MINER["status"] = "stopped"
            return _miner_safe_status()
        MINER_STOP_EVENT.set()
        REAL_MINER["status"] = "stopping"
        REAL_MINER["stop_reason"] = "Oprire manuală de către utilizator."
    _append_miner_log("Oprire manuală cerută de utilizator.")
    try:
        proc.terminate()
        try: proc.wait(timeout=4)
        except Exception:
            proc.kill()
            proc.wait(timeout=2)
    except Exception as exc:
        _append_miner_log(f"Eroare la oprire: {type(exc).__name__}: {exc}")
    return _miner_safe_status()


def http_json(url: str, payload: dict | None = None, timeout: float = 7.0) -> Any:
    headers = {"User-Agent": "CryptoFieldstation/1.0 (read-only public research; no transactions)", "Accept": "application/json"}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8"); headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read(2_000_000)
        if response.status < 200 or response.status >= 300: raise RuntimeError(f"HTTP {response.status}")
        return json.loads(raw.decode("utf-8"))


def is_valid_public_address(entry: dict) -> tuple[bool, str]:
    chain = entry.get("chain", "")
    if chain == "bitcoin":
        address = entry.get("address", "")
        # Syntax plausibility only; Esplora response is the network-side check.
        okay = bool(re.fullmatch(r"(?:[13][a-km-zA-HJ-NP-Z1-9]{25,34}|bc1[ac-hj-np-z02-9]{11,71})", address))
        return okay, "Sintaxă Bitcoin plauzibilă; checksum-ul va fi verificat de endpointul public."
    if chain in EVM_NETWORKS:
        address = entry.get("address", "")
        return bool(re.fullmatch(r"0x[0-9a-fA-F]{40}", address)), "Adresă EVM de 20 bytes; checksum-ul EIP-55 nu este validat aici."
    if chain == "solana":
        address = entry.get("address", "")
        return bool(re.fullmatch(r"[1-9A-HJ-NP-Za-km-z]{32,44}", address)), "Base58 plausibility only; on-chain account must be checked."
    return False, "Chain nesuportat."


def rpc_evm(network: str, method: str, params: list) -> Any:
    res = http_json(EVM_NETWORKS[network]["rpc"], {"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
    if "error" in res: raise RuntimeError(str(res["error"])[:300])
    return res.get("result")


def get_native_balance(entry: dict) -> dict:
    chain, address = entry["chain"], entry["address"]
    result = {"id": entry["id"], "label": entry["label"], "kind": entry.get("kind", "watch_only"), "chain": chain, "address": address, "checked_at": utc_now(), "status": "error"}
    if chain == "bitcoin":
        data = http_json("https://blockstream.info/api/address/" + urllib.parse.quote(address, safe=""))
        cs, ms = data.get("chain_stats", {}), data.get("mempool_stats", {})
        confirmed = int(cs.get("funded_txo_sum",0)) - int(cs.get("spent_txo_sum",0))
        mempool = int(ms.get("funded_txo_sum",0)) - int(ms.get("spent_txo_sum",0))
        result.update({"status":"ok", "asset":"BTC", "confirmed_base_units":confirmed, "confirmed":confirmed/1e8, "mempool_delta_sats":mempool, "tx_count":cs.get("tx_count",0), "source":"Blockstream Esplora public API"})
    elif chain in EVM_NETWORKS:
        wei_hex = rpc_evm(chain,"eth_getBalance",[address,"latest"])
        wei = int(wei_hex,16)
        conf = EVM_NETWORKS[chain]
        result.update({"status":"ok", "asset":conf["symbol"], "base_units":str(wei), "balance":wei/(10**conf["decimals"]), "source":"Public JSON-RPC endpoint", "rpc_network":chain})
        contract = entry.get("token_contract")
        if contract:
            if not re.fullmatch(r"0x[0-9a-fA-F]{40}", contract): raise ValueError("Contract ERC-20 invalid sintactic.")
            data_field = "0x70a08231" + ("0"*24) + address[2:].lower()
            raw_hex = rpc_evm(chain,"eth_call",[{"to":contract,"data":data_field},"latest"])
            decimals_hex = rpc_evm(chain,"eth_call",[{"to":contract,"data":"0x313ce567"},"latest"])
            decimals = int(decimals_hex,16)
            raw = int(raw_hex,16)
            result["token"] = {"contract":contract,"raw_balance":str(raw),"decimals":decimals,"balance":raw/(10**decimals),"symbol":"ERC-20 (symbol not resolved)"}
    elif chain == "solana":
        res = http_json(SOL_RPC,{"jsonrpc":"2.0","id":1,"method":"getBalance","params":[address,{"commitment":"finalized"}]})
        if "error" in res: raise RuntimeError(str(res["error"])[:300])
        lamports = int(res["result"]["value"])
        result.update({"status":"ok","asset":"SOL","base_units":str(lamports),"balance":lamports/1e9,"slot":res["result"].get("context",{}).get("slot"),"source":"Solana public JSON-RPC"})
    else:
        raise ValueError("Chain nesuportat")
    return result


def refresh_balances() -> dict:
    with STATE_LOCK:
        entries = list(ADDRESSES)
    results = {}
    for entry in entries:
        try:
            valid, validation_note = is_valid_public_address(entry)
            if not valid:
                results[entry["id"]] = {"id":entry["id"],"label":entry.get("label"),"chain":entry.get("chain"),"address":entry.get("address"),"checked_at":utc_now(),"status":"invalid_syntax","validation_note":validation_note}
                continue
            balance = get_native_balance(entry)
            balance["validation_note"] = validation_note
            results[entry["id"]] = balance
        except Exception as exc:
            results[entry["id"]] = {"id":entry["id"],"label":entry.get("label"),"chain":entry.get("chain"),"address":entry.get("address"),"checked_at":utc_now(),"status":"unavailable_or_error","error":str(exc)[:250],"note":"Endpointul public poate fi indisponibil sau limitat; încearcă din nou. Nu interpreta eroarea ca sold zero."}
    with STATE_LOCK:
        STATE["balances"] = results; STATE["last_balance_refresh"] = utc_now()
    journal("PUBLIC-ADDRESS-MONITOR", {"status":"snapshot", "experiment":"read-only public chain balance check", "results": [{"id":v.get("id"),"chain":v.get("chain"),"status":v.get("status"),"asset":v.get("asset"),"balance":v.get("balance"),"confirmed":v.get("confirmed"),"checked_at":v.get("checked_at"),"source":v.get("source")} for v in results.values()], "result":"snapshot; this does not establish ownership or claim rights", "next_step":"verify reward rules/owner eligibility separately"})
    return results


def refresh_github_sources() -> list[dict]:
    urls = [
        ("open-crypto-puzzles issues", "https://api.github.com/repos/floflo777/open-crypto-puzzles/issues?state=all&sort=updated&direction=desc&per_page=8"),
        ("ProofOfSolve issues", "https://api.github.com/repos/ProofOfSolve/puzzles/issues?state=all&sort=updated&direction=desc&per_page=8"),
        ("Block Zero latest commits", "https://api.github.com/repos/Rexemre/blockzero-core/commits?per_page=5"),
        ("Perihelion latest commits", "https://api.github.com/repos/perihelion-dev/perihelion/commits?per_page=5"),
    ]
    found = []
    for name, url in urls:
        try:
            payload = http_json(url, timeout=8)
            if not isinstance(payload, list): payload = [payload]
            for item in payload:
                if "html_url" in item:
                    found.append({"source":name,"title":item.get("title") or item.get("commit",{}).get("message","Commit").splitlines()[0],"url":item["html_url"],"updated_at":item.get("updated_at") or item.get("commit",{}).get("committer",{}).get("date"),"status":"new_public_update_to_review"})
        except Exception as exc:
            found.append({"source":name,"title":"Source unavailable on this check","url":url,"updated_at":utc_now(),"status":"unverified_error","error":str(exc)[:180]})
    with STATE_LOCK:
        STATE["opportunity_updates"] = found[:32]
    journal("GLOBAL-SOURCE-WATCH", {"status":"completed_with_possible_errors", "experiment":"read-only GitHub public source check", "sources_checked":[u for _,u in urls],"items_returned":len(found),"result":"Discovery only; no reward/eligibility is validated by an issue update alone", "next_step":"review each source, then verify official rules, chain state, transferability and Romania eligibility"})
    return found


def build_handoff(include_watch_only: bool = False) -> dict:
    with STATE_LOCK:
        addresses = [dict(a) for a in ADDRESSES if include_watch_only or a.get("kind") == "public_target"]
        public_ids = {a.get("id") for a in addresses}
        # Clone and scrub monitor journal entries so watch-only balances/IDs cannot leak via history.
        safe_journals = json.loads(json.dumps(JOURNALS))
        if not include_watch_only:
            monitor_entries = safe_journals.get("PUBLIC-ADDRESS-MONITOR", [])
            safe_monitor = []
            for entry in monitor_entries:
                copied = dict(entry)
                copied["results"] = [r for r in copied.get("results", []) if r.get("id") in public_ids]
                if copied["results"]:
                    safe_monitor.append(copied)
            if safe_monitor:
                safe_journals["PUBLIC-ADDRESS-MONITOR"] = safe_monitor
            else:
                safe_journals.pop("PUBLIC-ADDRESS-MONITOR", None)
        handoff = {
            "generated_at": utc_now(),
            "tool": "Crypto Fieldstation", "version": "1.0.0", "cost_spent_ron": 0,
            "connection_mode": "manual ChatGPT handoff; no direct push to ChatGPT and no paid model API",
            "privacy": {"watch_only_addresses_included": bool(include_watch_only), "private_keys_or_seed_phrases": "never collected or exported", "wallet_transactions": "not supported"},
            "current_state": {k: STATE.get(k) for k in ["running","mode","started_at","elapsed_seconds","attempts","rate","total","progress","workers","result","error","last_balance_refresh","opportunity_updates"]},
            "public_target_balance_snapshots": {k:v for k,v in STATE.get("balances", {}).items() if k in public_ids},
            "public_targets": addresses,
            "cases": CASES,
            "journals": safe_journals,
            "research_leads": LEADS,
            "instructions_for_assistant": ["Treat each case as a distinct journal.","Preserve prior results and timestamps; do not claim older runs as current.","Mark facts/estimates/assumptions/failures/unverified clearly.","When the bundle is uploaded to ChatGPT, use available web/research/GitHub/Exa/Firecrawl tools where connected to independently refresh primary sources; do not imply this local process is directly connected to them.","A padding-valid AES result is not a solution.","Only exact digest match is a verified match.","A public address balance is not ownership or claim eligibility.","Do not derive wallet keys or submit transactions."]
        }
    return handoff


def add_public_address(payload: dict) -> dict:
    chain = payload.get("chain", "")
    label = str(payload.get("label", "Watch-only address")).strip()[:120]
    address = str(payload.get("address", "")).strip()
    kind = payload.get("kind", "watch_only")
    if kind not in ("watch_only", "public_target"): raise ValueError("Tipul adresei trebuie să fie watch_only sau public_target.")
    entry = {"id": secrets.token_hex(6), "label": label or "Watch-only address", "chain": chain, "address": address, "kind": kind, "created_at": utc_now()}
    if chain in EVM_NETWORKS and payload.get("token_contract"):
        contract = str(payload["token_contract"]).strip()
        if not re.fullmatch(r"0x[0-9a-fA-F]{40}", contract): raise ValueError("Contract ERC-20 invalid sintactic.")
        entry["token_contract"] = contract
    okay, note = is_valid_public_address(entry)
    if not okay: raise ValueError(f"Adresa nu trece verificarea sintactică: {note}")
    with STATE_LOCK:
        if len(ADDRESSES) >= 30:
            raise ValueError("Limită locală de 30 intrări pentru a evita supraîncărcarea endpointurilor publice.")
        if any(a.get("chain") == chain and a.get("address", "").lower() == address.lower() and a.get("token_contract", "").lower() == entry.get("token_contract", "").lower() for a in ADDRESSES):
            raise ValueError("Adresa este deja monitorizată.")
        ADDRESSES.append(entry); save_json(ADDRESSES_FILE, ADDRESSES)
    log(f"Adresă adăugată în mod read-only: {label} ({chain}).")
    return entry


def api_response(handler: BaseHTTPRequestHandler, status: int, data: Any) -> None:
    raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(raw)))
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'")
    handler.end_headers(); handler.wfile.write(raw)


class Handler(BaseHTTPRequestHandler):
    server_version = "CryptoFieldstation/1.1"
    def log_message(self, fmt, *args):
        # Keep local logs low-noise; no request body is logged.
        sys.stderr.write("[fieldstation] " + (fmt % args) + "\n")

    def _host_ok(self) -> bool:
        host = self.headers.get("Host", "")
        return host in (f"127.0.0.1:{PORT}", f"localhost:{PORT}", "127.0.0.1", "localhost")

    def _origin_ok(self) -> bool:
        origin = self.headers.get("Origin")
        if not origin: return True  # CLI clients on loopback
        return origin in (f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}")

    def _read_json(self) -> dict:
        try: length = int(self.headers.get("Content-Length", "0"))
        except ValueError: raise ValueError("Content-Length invalid.")
        if length > MAX_BODY: raise ValueError("Cerere prea mare.")
        raw = self.rfile.read(length) if length else b"{}"
        try: data = json.loads(raw.decode("utf-8"))
        except Exception: raise ValueError("JSON invalid.")
        if not isinstance(data, dict): raise ValueError("Corpul trebuie să fie un obiect JSON.")
        return data

    def do_GET(self):
        if not self._host_ok(): return api_response(self, 403, {"error":"Host rejected"})
        if self.path in ("/", "/index.html"):
            try: raw = (APP_DIR / "index.html").read_bytes()
            except Exception: raw = b"Crypto Fieldstation UI missing"
            self.send_response(200); self.send_header("Content-Type","text/html; charset=utf-8"); self.send_header("Content-Length",str(len(raw))); self.send_header("Cache-Control","no-store"); self.end_headers(); self.wfile.write(raw); return
        if self.path == "/api/state":
            with STATE_LOCK:
                data = {**STATE, "addresses": ADDRESSES, "cases": CASES, "journals": JOURNALS, "leads": LEADS,
                        "supported_networks": {**{"bitcoin":{"symbol":"BTC"}, "solana":{"symbol":"SOL"}}, **{k:{"symbol":v["symbol"]} for k,v in EVM_NETWORKS.items()}},
                        "optional_aes_available": self._aes_available(), "real_miner": _miner_safe_status()}
            return api_response(self, 200, data)
        if self.path == "/api/export":
            return api_response(self, 200, build_handoff(False))
        if self.path.startswith("/api/journal/"):
            case_id = self.path[len("/api/journal/"):]
            return api_response(self, 200, {"case_id":case_id,"entries":JOURNALS.get(case_id, [])})
        return api_response(self, 404, {"error":"Not found"})

    @staticmethod
    def _aes_available() -> bool:
        try: import Crypto.Cipher.AES  # noqa: F401
        except Exception: return False
        return True

    def do_POST(self):
        if not self._host_ok() or not self._origin_ok(): return api_response(self, 403, {"error":"Local-only origin/host rejected"})
        try:
            body = self._read_json()
            if self.path == "/api/hash/start":
                with STATE_LOCK:
                    if STATE["running"]: raise ValueError("Există deja o lucrare activă; oprește-o înainte de alta.")
                start_hash_job(str(body.get("case_id", "UNASSIGNED"))[:100], str(body.get("algorithm","sha256")), str(body.get("target","")), str(body.get("candidate_text","")), list(body.get("transforms",[])), int(body.get("workers",get_default_workers())))
                return api_response(self, 202, {"accepted":True,"job_id":STATE["job_id"]})
            if self.path == "/api/aes/start":
                with STATE_LOCK:
                    if STATE["running"]: raise ValueError("Există deja o lucrare activă; oprește-o înainte de alta.")
                start_aes_job(str(body.get("case_id","GSMG-5BTC-FINAL")), str(body.get("ciphertext_b64","")), str(body.get("candidate_text","")), list(body.get("pass_transforms",["raw"])), str(body.get("kdf_digest","md5")), str(body.get("target_plain_sha256","")), int(body.get("workers",get_default_workers())))
                return api_response(self, 202, {"accepted":True,"job_id":STATE["job_id"]})
            if self.path == "/api/pow/start":
                with STATE_LOCK:
                    if STATE["running"]: raise ValueError("Există deja o lucrare activă; oprește-o înainte de alta.")
                start_pow_job(str(body.get("prefix","fieldstation-demo")), int(body.get("bits",18)), int(body.get("max_seconds",60)), int(body.get("workers",get_default_workers())))
                return api_response(self, 202, {"accepted":True,"job_id":STATE["job_id"]})
            if self.path == "/api/stop":
                stop_job(); return api_response(self, 200, {"stopping":True})
            if self.path == "/api/miner/start":
                status = start_real_miner(str(body.get("wallet", "")), str(body.get("pool_host", "")), int(body.get("pool_port", 0)), str(body.get("worker", "xiaomi17tpro")), int(body.get("threads", 2)), int(body.get("max_minutes", 30)), bool(body.get("consent", False)))
                return api_response(self, 202, {"accepted": True, "miner": status})
            if self.path == "/api/miner/stop":
                return api_response(self, 200, {"miner": stop_real_miner()})
            if self.path == "/api/balances/refresh":
                threading.Thread(target=refresh_balances, name="balance-refresh", daemon=True).start()
                return api_response(self, 202, {"started":True})
            if self.path == "/api/addresses/add":
                entry = add_public_address(body); return api_response(self, 201, {"added":entry})
            if self.path == "/api/addresses/delete":
                entry_id = str(body.get("id",""))
                with STATE_LOCK:
                    before = len(ADDRESSES)
                    ADDRESSES[:] = [a for a in ADDRESSES if a.get("id") != entry_id]
                    if len(ADDRESSES) == before: raise ValueError("ID-ul adresei nu există.")
                    save_json(ADDRESSES_FILE, ADDRESSES); STATE["balances"].pop(entry_id,None)
                return api_response(self, 200, {"deleted":entry_id})
            if self.path == "/api/research/refresh":
                threading.Thread(target=refresh_github_sources, name="source-refresh", daemon=True).start()
                return api_response(self, 202, {"started":True})
            if self.path == "/api/journal/add":
                case_id = str(body.get("case_id","UNASSIGNED"))[:100]
                entry = {"status":str(body.get("status","note"))[:100],"experiment":str(body.get("experiment","manual note"))[:200],"hypothesis":str(body.get("hypothesis",""))[:2000],"prediction":str(body.get("prediction",""))[:2000],"result":str(body.get("result",""))[:2000],"sources":body.get("sources",[])[:20] if isinstance(body.get("sources",[]),list) else [],"next_step":str(body.get("next_step",""))[:2000],"resources_used":str(body.get("resources_used","none recorded"))[:500]}
                journal(case_id,entry); return api_response(self,201,{"saved":True,"case_id":case_id})
            if self.path == "/api/lead/add":
                url = str(body.get("url",""))
                if not re.match(r"^https://", url): raise ValueError("Folosește numai URL-uri HTTPS publice.")
                lead = {"id":secrets.token_hex(6),"title":str(body.get("title","New lead"))[:180],"type":str(body.get("type","unclassified"))[:80],"url":url[:1000],"status":"unverified", "eligibility": "unverified", "transferability":"unverified", "cost": "unverified", "updated_at":utc_now()}
                with STATE_LOCK: LEADS.append(lead); save_json(LEADS_FILE,LEADS)
                return api_response(self,201,{"added":lead})
            if self.path == "/api/shutdown":
                api_response(self, 200, {"stopping_server":True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            return api_response(self,404,{"error":"Not found"})
        except ValueError as exc:
            return api_response(self,400,{"error":str(exc)})
        except Exception as exc:
            log(f"Eroare API {self.path}: {exc}")
            return api_response(self,500,{"error":str(exc)[:500]})


def main():
    global SERVER
    if sys.version_info < (3, 9):
        print("Necesită Python 3.9+."); sys.exit(2)
    ensure_data_loaded()
    SERVER = ThreadingHTTPServer((HOST, PORT), Handler)
    SERVER.daemon_threads = True
    print(f"Crypto Fieldstation rulează local: http://{HOST}:{PORT}")
    print("Siguranță: numai citire pentru lanțuri; fără seed/private keys, semnături sau tranzacții.")
    try:
        if "--open-browser" in sys.argv:
            # Termux helper is optional; browser can be opened manually otherwise.
            import subprocess
            try: subprocess.Popen(["termux-open-url", f"http://{HOST}:{PORT}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception: pass
        SERVER.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        print("\nOprire solicitată.")
    finally:
        STOP_EVENT.set()
        try:
            stop_real_miner()
        except Exception:
            pass
        SERVER.server_close()
        print("Crypto Fieldstation oprit.")

if __name__ == "__main__":
    main()
