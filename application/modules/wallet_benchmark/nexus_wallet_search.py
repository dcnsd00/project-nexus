from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Iterable

from nexus_wallet_formats import detect_wallet_format, detect_keyfile

DEFAULT_EXTENSIONS = {".json", ".dat", ".wallet", ".keys", ".key", ".txt", ".keystore", ".ldb"}
SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "Windows",
    "Program Files", "Program Files (x86)", "AppData", "Temp"
}
MAX_CANDIDATE_READ = 1_048_576
MAX_FILE_SIZE = 10 * 1024 * 1024
_BIP38_RE = re.compile(r"(?<![1-9A-HJ-NP-Za-km-z])6P[1-9A-HJ-NP-Za-km-z]{56}(?![1-9A-HJ-NP-Za-km-z])")


def _json_wallet_format(path: Path) -> tuple[str | None, str | None]:
    try:
        with path.open("rb") as handle:
            raw = handle.read(MAX_CANDIDATE_READ + 1)
        if len(raw) > MAX_CANDIDATE_READ:
            return None, "JSON candidate exceeds inspection limit"
        payload = json.loads(raw.decode("utf-8-sig"))
        detected = detect_wallet_format(payload)
        fmt = detected.get("format")
        if fmt in {"WEB3_SECRET_STORAGE_V3", "NEXUS_AESGCM_V1", "SOLANA_KEYPAIR_JSON"}:
            return fmt, "JSON structure validated"
        return None, "JSON file; no supported wallet structure detected"
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return None, "JSON structure not readable or invalid"


def _text_wallet_format(path: Path) -> tuple[str | None, str | None]:
    try:
        with path.open("rb") as handle:
            raw = handle.read(MAX_CANDIDATE_READ + 1)
        if len(raw) > MAX_CANDIDATE_READ:
            return None, "Text candidate exceeds inspection limit"
        text = raw.decode("utf-8-sig", errors="strict")
        match = _BIP38_RE.search(text)
        if match:
            return "BITCOIN_BIP38_0142_OR_0143_CANDIDATE", "encrypted BIP38 marker found; checksum/variant not yet verified"
    except (OSError, UnicodeDecodeError):
        pass
    return None, None


def _candidate_for(path: Path) -> tuple[str | None, str, str]:
    """Return (format, status, detection basis); do not treat filenames as proof."""
    name = path.name.lower()
    suffix = path.suffix.lower()

    if name == "wallet.dat":
        return "BITCOIN_CORE_WALLET_CANDIDATE", "CANDIDATE_UNVERIFIED", "filename wallet.dat; verify by loading in local Bitcoin Core"

    if suffix in {".json", ".keystore"} or name == "keystore":
        fmt, reason = _json_wallet_format(path)
        if fmt:
            return fmt, "FORMAT_CANDIDATE", reason or "JSON structure markers found; cryptographic validation still required"
        return None, "UNCLASSIFIED", reason or "unsupported JSON"

    if suffix in {".txt", ".key", ".keys"}:
        fmt, reason = _text_wallet_format(path)
        if fmt:
            return fmt, "CANDIDATE_UNVERIFIED", reason or "encrypted key marker found"

    if suffix == ".keys":
        return "MONERO_KEYS_CANDIDATE", "CANDIDATE_UNVERIFIED", "filename extension only; open with official Monero wallet software"
    if suffix == ".wallet" or "electrum" in name:
        return "ELECTRUM_WALLET_CANDIDATE", "CANDIDATE_UNVERIFIED", "filename/path heuristic only; verify with Electrum"
    if suffix == ".ldb" and "nkbihfbeogaeaoehlefnkodbefgpgknn" in str(path).lower():
        return "METAMASK_BROWSER_VAULT_CANDIDATE", "CANDIDATE_UNVERIFIED", "MetaMask extension storage path heuristic only"

    detected = detect_keyfile(path)
    fmt = detected.get("format")
    if fmt and fmt not in {"UNKNOWN_FILE", "UNKNOWN_JSON", "UNKNOWN_TEXT", "UNKNOWN"}:
        return fmt, "CANDIDATE_UNVERIFIED", detected.get("method", "format hint only")
    return None, "UNCLASSIFIED", detected.get("method", "unsupported file")


def search_wallet_files(
    root: str,
    max_files: int = 5000,
    max_depth: int = 8,
    extensions: Iterable[str] = DEFAULT_EXTENSIONS,
    now_ts: float | None = None,
) -> dict:
    """Metadata-only discovery in an explicitly selected local directory.

    This is not a blockchain search. File modification age is reported only as
    filesystem metadata and must never be interpreted as the wallet's last-chain
    activity. No password attempts or private-key extraction occur here.
    """
    base = Path(root).expanduser().resolve(strict=True)
    if not base.is_dir():
        raise ValueError("Search root must be an existing directory")
    if base == Path(base.anchor):
        raise ValueError("Refusing to scan a filesystem root; select a specific folder")
    if not 1 <= max_files <= 20000 or not 0 <= max_depth <= 16:
        raise ValueError("Search limits out of range")

    allowed = {x.lower() if x.startswith(".") else "." + x.lower() for x in extensions}
    now = float(now_ts if now_ts is not None else time.time())
    found: list[dict] = []
    scanned = 0
    skipped = 0
    unclassified = 0
    truncated = False

    for current, dirs, files in os.walk(base, followlinks=False):
        cur = Path(current)
        depth = len(cur.relative_to(base).parts)
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not (cur / d).is_symlink()]
        if depth >= max_depth:
            dirs[:] = []

        for name in files:
            path = cur / name
            if path.is_symlink():
                skipped += 1
                continue
            if path.suffix.lower() not in allowed and name.lower() not in {"wallet.dat", "keystore"}:
                continue
            if scanned >= max_files:
                truncated = True
                break
            scanned += 1
            try:
                st = path.stat()
                if not path.is_file() or st.st_size > MAX_FILE_SIZE:
                    skipped += 1
                    continue
                fmt, status, basis = _candidate_for(path)
                if not fmt:
                    unclassified += 1
                    continue
                file_age_days = max(0, int((now - st.st_mtime) // 86400))
                digest = None
                # Fingerprint candidate contents without retaining them or exposing secrets.
                if st.st_size <= MAX_CANDIDATE_READ:
                    h = hashlib.sha256()
                    with path.open("rb") as handle:
                        for chunk in iter(lambda: handle.read(65536), b""):
                            h.update(chunk)
                    digest = h.hexdigest()
                found.append({
                    "path": str(path),
                    "name": path.name,
                    "format": fmt,
                    "status": status,
                    "detection_basis": basis,
                    "size_bytes": st.st_size,
                    "modified_at": st.st_mtime,
                    "file_age_days": file_age_days,
                    "file_age_is_not_chain_inactivity": True,
                    "sha256_file_fingerprint": digest,
                    "private_key_read": False,
                    "decryption_attempted": False,
                })
            except (OSError, ValueError):
                skipped += 1
        if truncated:
            break

    return {
        "root": str(base),
        "results": found,
        "candidate_count": len(found),
        "scanned_files": scanned,
        "unclassified_files": unclassified,
        "skipped_files": skipped,
        "truncated": truncated,
        "scope": "selected local files only; no public blockchain address search",
        "chain_activity_checked": False,
        "private_keys_extracted": False,
    }
