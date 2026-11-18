"""Optional native SHA-256d scanner for NEXUS Stratum V1.

The C library scans exact caller-supplied Bitcoin header/nonce ranges. It does
not open sockets or submit shares. If a native compiler/library is unavailable,
the caller can transparently fall back to bitcoin_pow_engine.scan_nonce_range.
"""
from __future__ import annotations

import ctypes
import hashlib
import os
import platform
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Any

from mining.bitcoin_pow_engine import BitcoinPowError, scan_nonce_range

_LOCK = threading.RLock()
_LIB = None
_LOAD_ERROR: str | None = None
_LIB_PATH: Path | None = None


def _library_filename() -> str:
    system = platform.system().lower()
    if system == "windows":
        return "nexus_miner.dll"
    if system == "darwin":
        return "libnexus_miner.dylib"
    return "libnexus_miner.so"


def _compile_native() -> Path | None:
    source = Path(__file__).resolve().parent / "native" / "miner.c"
    if not source.is_file():
        return None
    system = platform.system().lower()
    requested_compiler = os.environ.get("NEXUS_NATIVE_COMPILER", "auto").strip().lower()
    msvc = shutil.which("cl.exe") or shutil.which("cl") if system == "windows" else None
    if requested_compiler == "msvc":
        if not msvc:
            _LOAD_ERROR = "NEXUS_NATIVE_COMPILER=msvc requested, but cl.exe is not available."
            return None
        compiler = None
    elif requested_compiler in {"gcc", "clang"}:
        compiler = shutil.which(requested_compiler)
        if not compiler:
            _LOAD_ERROR = f"NEXUS_NATIVE_COMPILER={requested_compiler} requested, but compiler is unavailable."
            return None
    else:
        compiler = shutil.which("gcc") or shutil.which("clang")
        if not compiler:
            compiler = None
    if not compiler and not msvc:
        return None
    build_dir = Path(os.environ.get("NEXUS_NATIVE_BUILD_DIR", str(Path(__file__).resolve().parent / "native" / "build")))
    build_dir.mkdir(parents=True, exist_ok=True)
    output = build_dir / _library_filename()
    if output.is_file() and output.stat().st_mtime >= source.stat().st_mtime:
        return output
    system = platform.system().lower()
    if system == "windows" and msvc:
        object_dir = str(build_dir) + os.sep
        cmd = [
            msvc, "/nologo", "/O2", "/LD", "/DNEXUS_LIBRARY",
            f"/Fe:{output}", f"/Fo:{object_dir}", str(source),
        ]
    elif system == "windows":
        cmd = [compiler, "-O3", "-pthread", "-shared", "-DNEXUS_LIBRARY", "-o", str(output), str(source)]
    elif system == "darwin":
        cmd = [compiler, "-O3", "-pthread", "-fPIC", "-dynamiclib", "-DNEXUS_LIBRARY", "-o", str(output), str(source)]
    else:
        cmd = [compiler, "-O3", "-pthread", "-fPIC", "-shared", "-DNEXUS_LIBRARY", "-o", str(output), str(source)]
    try:
        completed = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        global _LOAD_ERROR
        _LOAD_ERROR = f"native compile unavailable: {exc}"
        return None
    if completed.returncode != 0:
        _LOAD_ERROR = (completed.stderr or completed.stdout or "native compilation failed")[-2000:]
        return None
    return output


def _load_library():
    global _LIB, _LOAD_ERROR, _LIB_PATH
    with _LOCK:
        if _LIB is not None:
            return _LIB
        if _LOAD_ERROR is not None:
            return None
        explicit = os.environ.get("NEXUS_NATIVE_MINER_LIB")
        candidate = Path(explicit).expanduser() if explicit else None
        if candidate is not None and not candidate.is_file():
            _LOAD_ERROR = f"NEXUS_NATIVE_MINER_LIB does not exist: {candidate}"
            return None
        if candidate is None:
            candidate = _compile_native()
        if candidate is None:
            _LOAD_ERROR = _LOAD_ERROR or (
                "No native library or supported compiler found. Install GCC/Clang, "
                "or run from a Visual Studio x64 Developer environment for the MSVC scalar backend."
            )
            return None
        try:
            lib = ctypes.CDLL(str(candidate))
            fn = lib.nexus_scan_range
            fn.argtypes = [
                ctypes.POINTER(ctypes.c_ubyte), ctypes.POINTER(ctypes.c_ubyte),
                ctypes.c_uint32, ctypes.c_uint64, ctypes.c_int, ctypes.c_int,
                ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint64),
                ctypes.POINTER(ctypes.c_double),
            ]
            fn.restype = ctypes.c_int
            sup = lib.nexus_variant_supported
            sup.argtypes = [ctypes.c_int]
            sup.restype = ctypes.c_int
            _LIB = lib
            _LIB_PATH = candidate
            _LOAD_ERROR = None
            return _LIB
        except (OSError, AttributeError) as exc:
            _LOAD_ERROR = f"native library load failed: {exc}"
            return None


def _choose_threads() -> int:
    raw = os.environ.get("NEXUS_MINER_THREADS")
    if raw:
        try:
            return max(1, min(256, int(raw)))
        except ValueError:
            pass
    return max(1, min(4, os.cpu_count() or 1))


def _choose_variant(lib) -> int:
    raw = os.environ.get("NEXUS_NATIVE_MINER_VARIANT", "auto").strip().lower()
    if raw != "auto":
        try:
            requested = int(raw)
            if requested in range(5) and lib.nexus_variant_supported(requested):
                return requested
        except ValueError:
            pass
    for candidate in (4, 3, 1, 0):
        if lib.nexus_variant_supported(candidate):
            return candidate
    return 0


def native_status() -> dict[str, Any]:
    lib = _load_library()
    if lib is None:
        return {"available": False, "error": _LOAD_ERROR, "path": None, "variants": []}
    variants = [i for i in range(5) if lib.nexus_variant_supported(i)]
    selected = _choose_variant(lib)
    return {
        "available": True,
        "path": str(_LIB_PATH),
        "variants": variants,
        "selected_variant": selected,
        "selected_name": {0: "scalar", 1: "midstate", 2: "midstate-early", 3: "avx2-x8", 4: "avx512-x16"}[selected],
        "threads_default": _choose_threads(),
        "portable_dispatch": True,
        "error": None,
    }


def scan_nonce_range_native(
    header_template: bytes,
    start_nonce: int,
    count: int,
    share_target: int,
    block_target: int | None = None,
    *,
    variant: int | None = None,
    threads: int | None = None,
) -> dict[str, Any]:
    if not isinstance(header_template, bytes) or len(header_template) != 80:
        raise BitcoinPowError("Header-ul trebuie să aibă exact 80 bytes.")
    if isinstance(start_nonce, bool) or not isinstance(start_nonce, int) or not 0 <= start_nonce <= 0xFFFFFFFF:
        raise BitcoinPowError("start_nonce invalid.")
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 0xFFFFFFFF:
        raise BitcoinPowError("count trebuie să fie între 1 și 2^32-1.")
    if start_nonce + count > 0x100000000:
        raise BitcoinPowError("Intervalul nonce depășește uint32.")
    if isinstance(share_target, bool) or not isinstance(share_target, int) or not 0 < share_target < 1 << 256:
        raise BitcoinPowError("share_target invalid.")
    if block_target is not None and (isinstance(block_target, bool) or not isinstance(block_target, int) or not 0 < block_target < 1 << 256):
        raise BitcoinPowError("block_target invalid.")

    lib = _load_library()
    if lib is None:
        # The Python reference scanner caps one call at 1M hashes; split larger
        # ranges without losing any nonce when native compilation is unavailable.
        remaining = count
        offset = 0
        total_checked = 0
        while remaining:
            chunk = min(1_000_000, remaining)
            result = scan_nonce_range(header_template, start_nonce + offset, chunk, share_target, block_target)
            total_checked += int(result.get("checked", 0))
            if result.get("status") == "share_candidate":
                result["checked"] = total_checked
                result["engine"] = "python_exact_sha256d_chunked_fallback"
                return result
            remaining -= chunk
            offset += chunk
        return {"status": "range_exhausted", "checked": total_checked,
                "meets_share_target": False, "meets_block_target": False,
                "engine": "python_exact_sha256d_chunked_fallback",
                "reference_guard": "hashlib per nonce"}
    chosen_variant = _choose_variant(lib) if variant is None else int(variant)
    chosen_threads = _choose_threads() if threads is None else int(threads)
    if chosen_variant not in range(5) or not lib.nexus_variant_supported(chosen_variant):
        raise BitcoinPowError(f"Varianta nativă {chosen_variant} nu este suportată.")
    if not 1 <= chosen_threads <= 256:
        raise BitcoinPowError("threads trebuie să fie 1..256.")

    header_buf = (ctypes.c_ubyte * 80).from_buffer_copy(header_template)
    target_buf = (ctypes.c_ubyte * 32).from_buffer_copy(share_target.to_bytes(32, "big"))
    nonce_out = ctypes.c_uint32(0)
    checked_out = ctypes.c_uint64(0)
    rate_out = ctypes.c_double(0.0)
    rc = lib.nexus_scan_range(
        header_buf, target_buf, start_nonce, count, chosen_variant, chosen_threads,
        ctypes.byref(nonce_out), ctypes.byref(checked_out), ctypes.byref(rate_out),
    )
    if rc < 0:
        raise BitcoinPowError(f"Native scanner a returnat codul {rc}.")
    if checked_out.value != count:
        raise RuntimeError(f"Native scanner a raportat {checked_out.value}/{count} nonce-uri verificate.")

    result = {
        "status": "range_exhausted",
        "checked": int(checked_out.value),
        "meets_share_target": False,
        "meets_block_target": False,
        "engine": f"native_sha256d_variant_{chosen_variant}",
        "native_threads": chosen_threads,
        "native_hashrate_mhs": round(rate_out.value, 4),
        "reference_guard": "hash candidate independently recomputed with hashlib",
    }
    if rc == 1:
        nonce = int(nonce_out.value)
        header = bytearray(header_template)
        header[76:80] = nonce.to_bytes(4, "little")
        digest = hashlib.sha256(hashlib.sha256(header).digest()).digest()
        value = int.from_bytes(digest[::-1], "big")
        if value > share_target:
            raise RuntimeError("Native scanner false positive: candidatul nu respectă share_target conform hashlib.")
        result.update({
            "status": "share_candidate",
            "nonce": nonce,
            "hash_internal_hex": digest.hex(),
            "hash_display_hex": digest[::-1].hex(),
            "hash_value_hex": f"{value:064x}",
            "meets_share_target": True,
            "meets_block_target": bool(block_target is not None and value <= block_target),
        })
    return result


def scan_nonce_range_optimized(*args, **kwargs) -> dict[str, Any]:
    """Prefer native C; retain exact Python fallback when native build is unavailable."""
    return scan_nonce_range_native(*args, **kwargs)
