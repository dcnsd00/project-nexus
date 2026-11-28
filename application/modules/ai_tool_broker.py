"""NEXUS bounded AI tool broker.

The broker exposes repository inspection and bounded test execution only.
It never offers shell, miner, wallet, transaction, GitHub-write or provider-write
capabilities to a model. Tool arguments are untrusted and validated at the
execution boundary.
"""
from __future__ import annotations

import fnmatch
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any, Mapping


APP_ROOT = Path(__file__).resolve().parents[1]
MAX_READ_BYTES = 200_000
MAX_SEARCH_QUERY_CHARS = 120
MAX_SEARCH_FILES = 100
MAX_SEARCH_MATCHES = 30
MAX_LIST_RESULTS = 120
MAX_TOOL_RESULT_CHARS = 12_000
DEFAULT_TEST_TIMEOUT_SECONDS = 60
MAX_TEST_TIMEOUT_SECONDS = 120

ALLOWED_SOURCE_SUFFIXES = frozenset({
    ".py", ".md", ".json", ".toml", ".yaml", ".yml", ".txt", ".ps1",
    ".sh", ".ini", ".cfg", ".html", ".js", ".css", ".bat", ".psm1",
})
FORBIDDEN_PATH_COMPONENTS = frozenset({
    ".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "wallet_data", "secrets", "secret",
    "credentials", "private", "wallets", "keystores",
})
FORBIDDEN_SUFFIXES = frozenset({
    ".pem", ".key", ".p12", ".pfx", ".keystore", ".db", ".sqlite", ".sqlite3",
})
FORBIDDEN_NAMES = frozenset({
    ".env", "id_rsa", "id_ed25519", "wallet.dat", "seed.txt",
    "mnemonic.txt", "private_key.txt",
})


class AIToolError(RuntimeError):
    """Safe tool validation or execution error."""


def _root() -> Path:
    raw = os.environ.get("NEXUS_REPOSITORY_ROOT", "").strip()
    root = Path(raw).expanduser().resolve() if raw else APP_ROOT.resolve()
    if not root.is_dir():
        raise AIToolError("repository_root_unavailable")
    return root


def _parts_are_safe(parts: tuple[str, ...]) -> bool:
    lowered = tuple(part.casefold() for part in parts)
    if any(part in FORBIDDEN_PATH_COMPONENTS for part in lowered):
        return False
    if not parts:
        return False
    name = lowered[-1]
    if name in FORBIDDEN_NAMES or name.startswith(".env."):
        return False
    suffix = Path(name).suffix.casefold()
    if suffix in FORBIDDEN_SUFFIXES:
        return False
    if any(token in name for token in ("private_key", "seed_phrase", "mnemonic", "keystore")):
        return False
    return True


def _safe_path(value: Any, *, must_exist: bool = True) -> tuple[Path, str]:
    if not isinstance(value, str) or not value.strip() or len(value) > 300:
        raise AIToolError("invalid_repository_path")
    raw = value.strip().replace("\\", "/")
    candidate = Path(raw)
    if candidate.is_absolute() or any(part in {"", ".", ".."} for part in raw.split("/")):
        raise AIToolError("repository_path_must_be_relative")
    parts = tuple(raw.split("/"))
    if not _parts_are_safe(parts):
        raise AIToolError("repository_path_blocked_by_policy")
    root = _root()
    resolved = (root / candidate).resolve()
    try:
        relative = resolved.relative_to(root)
    except ValueError:
        raise AIToolError("repository_path_escapes_root") from None
    if not _parts_are_safe(relative.parts):
        raise AIToolError("repository_path_blocked_by_policy")
    if must_exist and not resolved.exists():
        raise AIToolError("repository_path_not_found")
    return resolved, relative.as_posix()


def _is_source_file(path: Path) -> bool:
    return path.is_file() and path.suffix.casefold() in ALLOWED_SOURCE_SUFFIXES


def _walk_source_files(start: Path, *, max_files: int) -> list[Path]:
    root = _root()
    try:
        relative = start.relative_to(root)
    except ValueError:
        raise AIToolError("repository_path_escapes_root") from None
    if not _parts_are_safe(relative.parts) and relative.parts:
        raise AIToolError("repository_path_blocked_by_policy")
    if start.is_file():
        return [start] if _is_source_file(start) else []
    if not start.is_dir():
        raise AIToolError("repository_directory_not_found")

    results: list[Path] = []
    for current, dirs, files in os.walk(start, topdown=True, followlinks=False):
        dirs[:] = sorted(
            name for name in dirs
            if name.casefold() not in FORBIDDEN_PATH_COMPONENTS
            and not name.startswith(".")
        )
        for name in sorted(files):
            item = Path(current) / name
            try:
                real = item.resolve()
                real.relative_to(root)
            except (OSError, ValueError):
                continue
            if not _parts_are_safe(real.relative_to(root).parts):
                continue
            if _is_source_file(real):
                results.append(real)
                if len(results) >= max_files:
                    return results
    return results


def list_source_files(directory: str = "", limit: int = 60) -> dict[str, Any]:
    if not isinstance(limit, int) or not 1 <= limit <= MAX_LIST_RESULTS:
        raise AIToolError("file_list_limit_out_of_range")
    root = _root()
    if directory:
        start, _ = _safe_path(directory)
    else:
        start = root
    files = _walk_source_files(start, max_files=limit + 1)
    truncated = len(files) > limit
    selected = files[:limit]
    return {
        "root": ".",
        "directory": directory or ".",
        "files": [path.relative_to(root).as_posix() for path in selected],
        "count": len(selected),
        "truncated": truncated,
    }


def read_source_file(path: str) -> dict[str, Any]:
    resolved, relative = _safe_path(path)
    if not _is_source_file(resolved):
        raise AIToolError("file_type_not_allowed")
    try:
        size = resolved.stat().st_size
    except OSError:
        raise AIToolError("file_stat_failed") from None
    if size > MAX_READ_BYTES:
        raise AIToolError("file_exceeds_read_limit")
    try:
        text = resolved.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise AIToolError("file_is_not_utf8_text") from None
    except OSError:
        raise AIToolError("file_read_failed") from None
    if len(text) > MAX_TOOL_RESULT_CHARS:
        text = text[:MAX_TOOL_RESULT_CHARS]
        truncated = True
    else:
        truncated = False
    return {
        "path": relative,
        "size_bytes": size,
        "content": text,
        "truncated": truncated,
    }


def search_source(
    query: str,
    directory: str = "",
    limit: int = 20,
) -> dict[str, Any]:
    if not isinstance(query, str) or not query.strip() or len(query) > MAX_SEARCH_QUERY_CHARS:
        raise AIToolError("search_query_invalid")
    if not isinstance(limit, int) or not 1 <= limit <= MAX_SEARCH_MATCHES:
        raise AIToolError("search_limit_out_of_range")
    root = _root()
    start = _safe_path(directory)[0] if directory else root
    files = _walk_source_files(start, max_files=MAX_SEARCH_FILES + 1)
    truncated_files = len(files) > MAX_SEARCH_FILES
    matches: list[dict[str, Any]] = []
    for path in files[:MAX_SEARCH_FILES]:
        try:
            if path.stat().st_size > MAX_READ_BYTES:
                continue
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for number, line in enumerate(lines, 1):
            if query.casefold() in line.casefold():
                matches.append({
                    "path": path.relative_to(root).as_posix(),
                    "line": number,
                    "text": line[:500],
                })
                if len(matches) >= limit:
                    return {
                        "query": query,
                        "matches": matches,
                        "count": len(matches),
                        "truncated": True,
                        "files_scanned": min(len(files), MAX_SEARCH_FILES),
                    }
    return {
        "query": query,
        "matches": matches,
        "count": len(matches),
        "truncated": truncated_files,
        "files_scanned": min(len(files), MAX_SEARCH_FILES),
    }


def run_pytest(
    test_path: str,
    test_name: str | None = None,
    timeout_seconds: int = DEFAULT_TEST_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    resolved, relative = _safe_path(test_path)
    parts = Path(relative).parts
    if (
        len(parts) < 2
        or parts[0] != "tests"
        or not parts[-1].startswith("test_")
        or resolved.suffix != ".py"
        or not _is_source_file(resolved)
    ):
        raise AIToolError("pytest_path_must_be_application_tests_test_file")
    if test_name is not None and (
        not isinstance(test_name, str)
        or not re.fullmatch(r"test_[A-Za-z0-9_]{1,120}", test_name)
    ):
        raise AIToolError("pytest_test_name_invalid")
    if not isinstance(timeout_seconds, int) or not 1 <= timeout_seconds <= MAX_TEST_TIMEOUT_SECONDS:
        raise AIToolError("pytest_timeout_out_of_range")

    node_id = relative + (f"::{test_name}" if test_name else "")
    command = [sys.executable, "-m", "pytest", node_id, "-q"]
    env_allowlist = {
        "PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "TMPDIR",
        "HOME", "USERPROFILE", "VIRTUAL_ENV", "PYTHONPATH",
    }
    env = {key: value for key, value in os.environ.items() if key.upper() in env_allowlist}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    started = time.monotonic()
    try:
        result = subprocess.run(
            command,
            cwd=str(_root()),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
            shell=False,
        )
        output = result.stdout or ""
        return_code = result.returncode
        status = "passed" if return_code == 0 else "failed"
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        return_code = None
        status = "timeout"
    except OSError as exc:
        raise AIToolError(f"pytest_launch_failed_{type(exc).__name__}") from None

    if len(output) > MAX_TOOL_RESULT_CHARS:
        output = output[-MAX_TOOL_RESULT_CHARS:]
    return {
        "test_path": relative,
        "test_name": test_name,
        "status": status,
        "return_code": return_code,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "output": output,
        "timeout_seconds": timeout_seconds,
        "shell_used": False,
    }


TOOL_SCHEMAS: tuple[dict[str, Any], ...] = (
    {
        "type": "function",
        "function": {
            "name": "nexus_list_source_files",
            "description": "List source and documentation files in the local NEXUS application repository. Does not read secret or wallet data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "Optional path relative to the NEXUS application root."},
                    "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIST_RESULTS},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "nexus_read_source_file",
            "description": "Read one UTF-8 source or documentation file from the local NEXUS application repository. Secret, wallet and credential files are blocked.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Repository-relative path to a source/documentation file."},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "nexus_search_source",
            "description": "Search literal text in bounded local NEXUS source files. This is not regex or shell access.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "minLength": 1, "maxLength": MAX_SEARCH_QUERY_CHARS},
                    "directory": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": MAX_SEARCH_MATCHES},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "nexus_run_pytest",
            "description": "Run one bounded pytest file or a single test function under application/tests using the current Python interpreter. No arbitrary shell commands are permitted.",
            "parameters": {
                "type": "object",
                "properties": {
                    "test_path": {"type": "string", "description": "Path like tests/test_ai_worker_provider.py."},
                    "test_name": {"type": "string", "description": "Optional test function name beginning test_."},
                    "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": MAX_TEST_TIMEOUT_SECONDS},
                },
                "required": ["test_path"],
                "additionalProperties": False,
            },
        },
    },
)

TOOL_NAMES = frozenset(item["function"]["name"] for item in TOOL_SCHEMAS)


def tool_schemas() -> list[dict[str, Any]]:
    """Return a fresh copy of the static, read-only/test-only model tool schemas."""
    return json.loads(json.dumps(TOOL_SCHEMAS))


def execute_tool(name: str, arguments: Mapping[str, Any] | str) -> dict[str, Any]:
    """Execute one allowlisted local tool call; never dispatch arbitrary names."""
    if name not in TOOL_NAMES:
        raise AIToolError("tool_not_allowlisted")
    if isinstance(arguments, str):
        if len(arguments) > 8_000:
            raise AIToolError("tool_arguments_too_large")
        try:
            payload = json.loads(arguments)
        except json.JSONDecodeError:
            raise AIToolError("tool_arguments_invalid_json") from None
    elif isinstance(arguments, Mapping):
        payload = dict(arguments)
    else:
        raise AIToolError("tool_arguments_invalid")
    if not isinstance(payload, dict):
        raise AIToolError("tool_arguments_must_be_object")

    functions = {
        "nexus_list_source_files": list_source_files,
        "nexus_read_source_file": read_source_file,
        "nexus_search_source": search_source,
        "nexus_run_pytest": run_pytest,
    }
    try:
        result = functions[name](**payload)
    except TypeError:
        raise AIToolError("tool_arguments_do_not_match_schema") from None
    encoded = json.dumps(result, ensure_ascii=False)
    if len(encoded) > MAX_TOOL_RESULT_CHARS + 2_000:
        raise AIToolError("tool_result_too_large")
    return result
