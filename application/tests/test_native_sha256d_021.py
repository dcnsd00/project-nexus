import hashlib
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from mining.bitcoin_pow_engine import scan_nonce_range
from mining.native_sha256d import native_status, scan_nonce_range_native

GENESIS_HEADER = bytes.fromhex(
    "010000000000000000000000000000000000000000000000000000000000000000000000"
    "3ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a"
    "29ab5f49ffff001d1dac2b7c"
)
GENESIS_NONCE = 2083236893
GENESIS_TARGET = int("00000000ffff0000000000000000000000000000000000000000000000000000", 16)


def test_native_library_builds_and_reports_cpu_dispatch():
    status = native_status()
    if not status["available"]:
        pytest.skip(status.get("error") or "native C compiler unavailable")
    assert status["variants"]
    assert status["selected_variant"] in status["variants"]
    assert Path(status["path"]).is_file()
    assert status["portable_dispatch"] is True


def test_all_supported_native_variants_verify_genesis_with_thread_remainders():
    status = native_status()
    if not status["available"]:
        pytest.skip(status.get("error") or "native C compiler unavailable")
    # Start at the known genesis nonce: this validates the canonical digest and
    # block-target path without spending CI time brute-scanning one million
    # unrelated nonces. The 35-item range still exercises thread/vector tails.
    for variant in status["variants"]:
        result = scan_nonce_range_native(
            GENESIS_HEADER, GENESIS_NONCE, 35,
            GENESIS_TARGET, GENESIS_TARGET, variant=variant, threads=4,
        )
        assert result["status"] == "share_candidate", (variant, result)
        assert result["nonce"] == GENESIS_NONCE
        assert result["checked"] == 35
        assert result["meets_block_target"] is True
        assert result["hash_internal_hex"] == hashlib.sha256(
            hashlib.sha256(GENESIS_HEADER[:76] + GENESIS_NONCE.to_bytes(4, "little")).digest()
        ).hexdigest()


def test_native_scanner_checks_exact_non_multiple_range_without_false_share():
    status = native_status()
    if not status["available"]:
        pytest.skip(status.get("error") or "native C compiler unavailable")
    tiny_target = 1
    for variant in status["variants"]:
        result = scan_nonce_range_native(
            GENESIS_HEADER, 1234567, 1003, tiny_target,
            variant=variant, threads=7,
        )
        assert result["status"] == "range_exhausted"
        assert result["checked"] == 1003


def test_native_early_exit_variants_do_not_drop_easy_pool_shares():
    status = native_status()
    if not status["available"]:
        pytest.skip(status.get("error") or "native C compiler unavailable")
    # Deliberately easy target with a non-zero most-significant target byte.
    # AVX/early-exit paths must fall back to full target comparison here.
    easy_target = int("7f" + "ff" * 31, 16)
    for variant in status["variants"]:
        result = scan_nonce_range_native(
            GENESIS_HEADER, 1234567, 17, easy_target,
            variant=variant, threads=4,
        )
        assert result["status"] == "share_candidate"
        assert result["checked"] == 17
        assert result["meets_share_target"] is True


def test_cli_rejects_invalid_thread_count_and_variant():
    root = Path(__file__).resolve().parents[1]
    compiler = shutil.which("gcc") or shutil.which("clang")
    if not compiler:
        pytest.skip("native C compiler unavailable")
    build = root / "mining" / "native" / "build"
    build.mkdir(parents=True, exist_ok=True)
    exe = build / ("nexus_miner_test.exe" if os.name == "nt" else "nexus_miner_test")
    source = root / "mining" / "native" / "miner.c"
    compiled = subprocess.run([compiler, "-O2", "-pthread", "-o", str(exe), str(source)], capture_output=True, text=True)
    if compiled.returncode:
        pytest.fail(compiled.stderr[-2000:])
    bad_threads = subprocess.run([str(exe), "run", "1", "0", "1"], capture_output=True, text=True)
    bad_variant = subprocess.run([str(exe), "run", "9", "1", "1"], capture_output=True, text=True)
    assert bad_threads.returncode != 0
    assert bad_variant.returncode != 0


def test_native_scanner_uses_explicit_header_bytes_and_ignores_untrusted_compact_target():
    status = native_status()
    if not status["available"]:
        pytest.skip(status.get("error") or "native C compiler unavailable")
    header = bytearray(GENESIS_HEADER)
    header[72:76] = b'\xff\xff\xff\xff'  # malformed nBits; explicit pool target is authoritative here
    target = int("7f" + "ff" * 31, 16)
    result = scan_nonce_range_native(bytes(header), 7, 9, target, variant=status['selected_variant'], threads=2)
    assert result['status'] == 'share_candidate'
    assert result['checked'] == 9

def test_native_scanner_prioritizes_block_candidate_over_later_pool_shares():
    status = native_status()
    if not status["available"]:
        pytest.skip(status.get("error") or "native C compiler unavailable")

    share_target = (1 << 256) - 1
    start_nonce = 1234567
    # Pick a deterministic 4-nonce range where the final hash is above the
    # first hash. The first nonce is a block candidate by construction, while
    # every nonce is still a valid pool share.
    while True:
        def hash_value(nonce):
            header = GENESIS_HEADER[:76] + nonce.to_bytes(4, "little")
            digest = hashlib.sha256(hashlib.sha256(header).digest()).digest()
            return int.from_bytes(digest[::-1], "big")

        first_value = hash_value(start_nonce)
        last_value = hash_value(start_nonce + 3)
        if last_value > first_value:
            break
        start_nonce += 1

    block_target = first_value
    for variant in status["variants"]:
        result = scan_nonce_range_native(
            GENESIS_HEADER, start_nonce, 4, share_target, block_target,
            variant=variant, threads=4,
        )
        assert result["status"] == "share_candidate", (variant, result)
        assert result["nonce"] == start_nonce, (variant, result)
        assert result["meets_share_target"] is True
        assert result["meets_block_target"] is True
        assert result["checked"] == 4


def test_native_scanner_rejects_block_target_easier_than_share_target():
    with pytest.raises(ValueError, match="block_target"):
        scan_nonce_range_native(
            GENESIS_HEADER, 0, 1, 1, 2,
        )


def test_python_fallback_prioritizes_block_candidate_over_pool_share():
    share_target = (1 << 256) - 1
    start_nonce = 1234567

    def hash_value(nonce):
        header = GENESIS_HEADER[:76] + nonce.to_bytes(4, "little")
        digest = hashlib.sha256(hashlib.sha256(header).digest()).digest()
        return int.from_bytes(digest[::-1], "big")

    while hash_value(start_nonce + 3) <= hash_value(start_nonce):
        start_nonce += 1
    block_target = hash_value(start_nonce)

    result = scan_nonce_range(
        GENESIS_HEADER, start_nonce, 4, share_target, block_target,
    )
    assert result["status"] == "share_candidate"
    assert result["nonce"] == start_nonce
    assert result["meets_share_target"] is True
    assert result["meets_block_target"] is True
