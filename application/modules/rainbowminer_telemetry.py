"""Read-only, privacy-filtered RainbowMiner telemetry ingestion for NEXUS.

RainbowMiner's documented Report API is an HTTP POST push. NEXUS accepts only
local loopback reports, authenticates the report key, stores a strict telemetry
allowlist and never executes commands or changes mining configuration.
"""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import math
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs

from fastapi import APIRouter, HTTPException, Request
from starlette.datastructures import UploadFile as StarletteUploadFile

from modules.data_paths import data_path


MAX_REPORT_BYTES = 1_048_576
MAX_EXTRA_PAYLOAD_BYTES = 5_242_880
MAX_EXTRA_ROWS = 2048
MAX_FORM_FIELDS = 128
MAX_MINER_ROWS = 128
MAX_DEVICE_ROWS = 128
MAX_RETAINED_REPORTS = 500

TOP_LEVEL_FIELDS = {
    "status", "runmode", "interval", "uptime", "sysuptime", "memusage",
    "profit", "powerdraw", "earnings_avg", "earnings_1d", "cpu", "cpuload",
    "cputemp", "cpupower", "maxtemp", "tempalert", "maxcrashes", "crashalert",
    "version", "psversion", "shrm", "uncleanalert",
}
MINER_FIELDS = {
    "Name", "Version", "Type", "Active", "Algorithm", "Currency", "CoinName",
    "CoinSymbol", "Pool", "BLK", "CurrentSpeed", "EstimatedSpeed", "Accepted",
    "Rejected", "Stale", "PowerDraw", "BTC/day", "Profit", "Donator",
    "Benchmarking", "Devices",
}
DEVICE_FIELDS = {
    "Id", "Name", "Type", "Vendor", "Model", "Algorithm", "CurrentSpeed",
    "PowerDraw", "Watt", "Temperature", "Temp", "Fan", "CoreClock", "MemoryClock",
    "MemoryTotal", "MemoryFree", "Mem", "Core", "MemC", "MaxTemp",
    "Accepted", "Rejected", "Stale",
}
POOL_FIELDS = {
    "Pool", "Name", "Algorithm", "Currency", "CoinName", "CoinSymbol",
    "Accepted", "Rejected", "Stale", "Profit", "PowerDraw", "CurrentSpeed",
    "BLK",
}
MINER_BENCHMARK_FIELDS = {
    "Name", "Version", "Algorithm", "DeviceName", "DeviceModel", "HashRate",
    "PowerDraw",
}
POOL_BENCHMARK_FIELDS = {
    "Name", "Algorithm", "CoinSymbol", "Price", "StablePrice",
    "PenaltyFactor", "ErrorRatio",
}
router = APIRouter(prefix="/api/mining/rainbowminer", tags=["RainbowMiner telemetry"])


class RainbowMinerReportError(ValueError):
    """Invalid or unsupported RainbowMiner report."""


def _database_path():
    return data_path("mining", "rainbowminer_telemetry.sqlite3")


def _loopback_client(request: Request) -> bool:
    host = request.client.host if request.client else ""
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host.casefold().rstrip(".") == "localhost"


def _require_loopback(request: Request) -> None:
    if not _loopback_client(request):
        raise HTTPException(status_code=403, detail="rainbowminer_ingest_loopback_only")


def _json_value(raw: str, field: str) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        raise RainbowMinerReportError(f"invalid_json_field:{field}") from None


def _single_value(values: dict[str, Any], key: str) -> str:
    value = values.get(key, "")
    if isinstance(value, list):
        if len(value) > 1:
            raise RainbowMinerReportError(f"duplicate_field:{key}")
        value = value[0] if value else ""
    return str(value)


def _parse_request_body(body: bytes, content_type: str) -> dict[str, Any]:
    if len(body) > MAX_REPORT_BYTES:
        raise RainbowMinerReportError("report_too_large")
    media_type = content_type.split(";", 1)[0].strip().casefold()
    if media_type == "application/x-www-form-urlencoded":
        try:
            parsed = parse_qs(
                body.decode("utf-8"),
                keep_blank_values=True,
                strict_parsing=False,
                max_num_fields=MAX_FORM_FIELDS,
            )
        except (UnicodeDecodeError, ValueError):
            raise RainbowMinerReportError("invalid_form_payload") from None
        return {key: values for key, values in parsed.items()}
    if media_type == "application/json":
        try:
            value = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            raise RainbowMinerReportError("invalid_json_payload") from None
        if not isinstance(value, dict):
            raise RainbowMinerReportError("report_must_be_object")
        return value
    raise RainbowMinerReportError("unsupported_content_type")


def _safe_scalar(value: Any, field: str, *, max_length: int = 160) -> Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        number = float(value)
        if not math.isfinite(number):
            raise RainbowMinerReportError(f"invalid_numeric_value:{field}")
        return value
    if isinstance(value, str):
        text = value.strip()
        if len(text) > max_length or any(ord(char) < 32 and char not in "\t" for char in text):
            raise RainbowMinerReportError(f"invalid_text_value:{field}")
        return text
    if isinstance(value, list):
        if len(value) > 32:
            raise RainbowMinerReportError(f"list_too_long:{field}")
        return [_safe_scalar(item, field, max_length=max_length) for item in value]
    raise RainbowMinerReportError(f"unsupported_value_type:{field}")


def _filtered_rows(value: Any, allowed_fields: set[str], field: str,
                   maximum: int) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, dict):
        if set(value).intersection(allowed_fields):
            value = [value]
        else:
            rows = []
            for key, row in value.items():
                if not isinstance(row, dict):
                    raise RainbowMinerReportError(f"invalid_row:{field}:{key}")
                enriched = dict(row)
                inferred_key = "Pool" if field == "pool_totals" else "Id"
                enriched.setdefault(inferred_key, key)
                rows.append(enriched)
            value = rows
    if not isinstance(value, list) or len(value) > maximum:
        raise RainbowMinerReportError(f"invalid_array:{field}")
    output: list[dict[str, Any]] = []
    for index, row in enumerate(value):
        if not isinstance(row, dict):
            raise RainbowMinerReportError(f"invalid_row:{field}:{index}")
        selected = {}
        for key in allowed_fields:
            if key not in row:
                continue
            if key == "Devices" and field == "data":
                selected[key] = _filtered_rows(
                    row[key], DEVICE_FIELDS, "data.Devices", MAX_DEVICE_ROWS
                )
            else:
                selected[key] = _safe_scalar(row[key], f"{field}.{key}")
        output.append(selected)
    return output


def _filtered_rates(value: Any) -> dict[str, float]:
    if value is None:
        return {}
    if not isinstance(value, dict) or len(value) > 128:
        raise RainbowMinerReportError("invalid_rates_object")
    result: dict[str, float] = {}
    for key, raw in value.items():
        symbol = str(key).strip().upper()
        if not symbol or len(symbol) > 16 or not symbol.replace("-", "").isalnum():
            continue
        if isinstance(raw, bool):
            continue
        try:
            rate = float(raw)
        except (TypeError, ValueError):
            continue
        if math.isfinite(rate) and rate >= 0:
            result[symbol] = rate
    return result


def normalize_report(raw: dict[str, Any]) -> dict[str, Any]:
    """Remove credentials/PII/raw logs and return only bounded mining telemetry."""
    if not isinstance(raw, dict):
        raise RainbowMinerReportError("report_must_be_object")

    def value(key: str) -> Any:
        current = raw.get(key)
        if isinstance(current, list):
            if len(current) > 1:
                raise RainbowMinerReportError(f"duplicate_field:{key}")
            return current[0] if current else ""
        return current

    worker = str(value("worker") or "unnamed-worker").strip()
    if not worker or len(worker) > 128 or any(ord(char) < 32 for char in worker):
        raise RainbowMinerReportError("invalid_worker_name")

    payload: dict[str, Any] = {
        "worker": worker,
        "received_at": datetime.now(timezone.utc).isoformat(),
        "source": "RainbowMiner",
    }
    numeric_fields = {
        "interval", "uptime", "sysuptime", "memusage", "profit", "powerdraw",
        "earnings_avg", "earnings_1d", "cpuload", "cputemp", "cpupower",
        "maxtemp", "tempalert", "maxcrashes", "crashalert",
    }
    for field in TOP_LEVEL_FIELDS:
        raw_value = value(field)
        if raw_value in (None, ""):
            continue
        if field in numeric_fields:
            try:
                number = float(raw_value)
            except (TypeError, ValueError):
                raise RainbowMinerReportError(f"invalid_numeric_field:{field}") from None
            if not math.isfinite(number) or number < 0:
                raise RainbowMinerReportError(f"invalid_numeric_field:{field}")
            payload[field] = number
        elif field == "uncleanalert":
            normalized = str(raw_value).strip().casefold()
            if normalized not in {"true", "false", "1", "0", "yes", "no"}:
                raise RainbowMinerReportError("invalid_boolean_field:uncleanalert")
            payload[field] = normalized in {"true", "1", "yes"}
        else:
            payload[field] = _safe_scalar(raw_value, field)

    def nested(name: str) -> Any:
        raw_value = value(name)
        if raw_value in (None, ""):
            return None
        if isinstance(raw_value, str):
            return _json_value(raw_value, name)
        return raw_value

    payload["data"] = _filtered_rows(
        nested("data"), MINER_FIELDS, "data", MAX_MINER_ROWS
    )
    payload["devices"] = _filtered_rows(
        nested("devices"), DEVICE_FIELDS, "devices", MAX_DEVICE_ROWS
    )
    pool_totals = nested("pool_totals")
    payload["pool_totals"] = _filtered_rows(
        pool_totals, POOL_FIELDS, "pool_totals", 128
    ) if pool_totals is not None else []
    payload["rates"] = _filtered_rates(nested("rates"))

    # Crash records, disk paths, machine IP, email, Pushover key, console logs,
    # MinerStatusKey and raw filesystem paths are intentionally not persisted.
    crash_data = nested("crashdata")
    disk_alerts = nested("diskmingbalert")
    payload["crash_record_count"] = len(crash_data) if isinstance(crash_data, list) else 0
    payload["disk_alert_count"] = len(disk_alerts) if isinstance(disk_alerts, list) else 0
    return payload


def normalize_extra_payload(kind: str, raw_bytes: bytes, *,
                            worker: str, version: str | None = None) -> dict[str, Any]:
    """Normalize RainbowMiner's six-hour benchmark/pool file uploads."""
    if kind not in {"minerdata", "poolsdata"}:
        raise RainbowMinerReportError("unsupported_extra_payload_type")
    if len(raw_bytes) > MAX_EXTRA_PAYLOAD_BYTES:
        raise RainbowMinerReportError("extra_payload_too_large")
    try:
        decoded = json.loads(raw_bytes.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError):
        raise RainbowMinerReportError("invalid_extra_payload_json") from None
    if not isinstance(decoded, dict):
        raise RainbowMinerReportError("extra_payload_must_be_object")

    worker = str(worker).strip()
    if not worker or len(worker) > 128 or any(ord(char) < 32 for char in worker):
        raise RainbowMinerReportError("invalid_worker_name")
    payload: dict[str, Any] = {
        "worker": worker,
        "version": _safe_scalar(version, "version") if version else None,
        "received_at": datetime.now(timezone.utc).isoformat(),
        "source": "RainbowMiner",
        "payload_type": kind,
    }
    if kind == "minerdata":
        miners = decoded.get("Miners", [])
        payload["miners"] = _filtered_rows(
            miners, MINER_BENCHMARK_FIELDS, "minerdata.Miners", MAX_EXTRA_ROWS
        )
        cpu = decoded.get("CPU")
        payload["cpu_model"] = _safe_scalar(cpu, "minerdata.CPU") if cpu is not None else None
        # OCprofiles are deliberately excluded: they are configuration data,
        # not required for pool scoring or benchmark comparison.
    else:
        rows = decoded.get("Pools", decoded.get("pools", decoded))
        payload["pools"] = _filtered_rows(
            rows, POOL_BENCHMARK_FIELDS, "poolsdata", MAX_EXTRA_ROWS
        )
    return payload


def _persist_extra_report(payload: dict[str, Any]) -> dict[str, Any]:
    path = data_path("mining", "rainbowminer_telemetry.sqlite3", create_parent=True)
    report_id = str(uuid.uuid4())
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    with sqlite3.connect(str(path), timeout=5.0) as connection:
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute(
            """CREATE TABLE IF NOT EXISTS rainbowminer_extra_reports (
                report_id TEXT PRIMARY KEY,
                received_at TEXT NOT NULL,
                worker TEXT NOT NULL,
                payload_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                payload_sha256 TEXT NOT NULL
            )"""
        )
        connection.execute(
            """INSERT INTO rainbowminer_extra_reports
               (report_id, received_at, worker, payload_type, payload_json, payload_sha256)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (report_id, payload["received_at"], payload["worker"],
             payload["payload_type"], serialized, digest),
        )
        connection.execute(
            """DELETE FROM rainbowminer_extra_reports
               WHERE report_id NOT IN (
                   SELECT report_id FROM rainbowminer_extra_reports
                   ORDER BY received_at DESC, report_id DESC LIMIT ?
               )""",
            (MAX_RETAINED_REPORTS,),
        )
        connection.commit()
    return {"report_id": report_id, "payload_sha256": digest, "database": str(path)}


def _latest_extra_payload(payload_type: str, worker: str | None = None) -> dict[str, Any] | None:
    path = _database_path()
    if not path.is_file():
        return None
    with sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=2.0) as connection:
        table_exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='rainbowminer_extra_reports'"
        ).fetchone()
        if not table_exists:
            return None
        if worker:
            row = connection.execute(
                """SELECT payload_json FROM rainbowminer_extra_reports
                   WHERE payload_type=? AND worker=? ORDER BY received_at DESC LIMIT 1""",
                (payload_type, worker),
            ).fetchone()
        else:
            row = connection.execute(
                """SELECT payload_json FROM rainbowminer_extra_reports
                   WHERE payload_type=? ORDER BY received_at DESC LIMIT 1""",
                (payload_type,),
            ).fetchone()
    return json.loads(row[0]) if row else None


def _persist_report(payload: dict[str, Any]) -> dict[str, Any]:
    path = data_path("mining", "rainbowminer_telemetry.sqlite3", create_parent=True)
    report_id = str(uuid.uuid4())
    received_at = str(payload["received_at"])
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    with sqlite3.connect(str(path), timeout=5.0) as connection:
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute(
            """CREATE TABLE IF NOT EXISTS rainbowminer_reports (
                report_id TEXT PRIMARY KEY,
                received_at TEXT NOT NULL,
                worker TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                payload_sha256 TEXT NOT NULL
            )"""
        )
        connection.execute(
            """INSERT INTO rainbowminer_reports
               (report_id, received_at, worker, payload_json, payload_sha256)
               VALUES (?, ?, ?, ?, ?)""",
            (report_id, received_at, payload["worker"], serialized, digest),
        )
        connection.execute(
            """DELETE FROM rainbowminer_reports
               WHERE report_id NOT IN (
                   SELECT report_id FROM rainbowminer_reports
                   ORDER BY received_at DESC, report_id DESC LIMIT ?
               )""",
            (MAX_RETAINED_REPORTS,),
        )
        connection.commit()
    return {"report_id": report_id, "payload_sha256": digest, "database": str(path)}


def telemetry_status() -> dict[str, Any]:
    path = _database_path()
    exists = path.is_file()
    count = 0
    latest = None
    extra_counts = {"minerdata": 0, "poolsdata": 0}
    if exists:
        with sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=2.0) as connection:
            row = connection.execute(
                "SELECT COUNT(*), MAX(received_at) FROM rainbowminer_reports"
            ).fetchone() if connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='rainbowminer_reports'"
            ).fetchone() else (0, None)
            count, latest = int(row[0] or 0), row[1]
            has_extra = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='rainbowminer_extra_reports'"
            ).fetchone()
            if has_extra:
                rows = connection.execute(
                    "SELECT payload_type, COUNT(*) FROM rainbowminer_extra_reports GROUP BY payload_type"
                ).fetchall()
                extra_counts.update({str(kind): int(total) for kind, total in rows})
    return {
        "source": "RainbowMiner",
        "enabled": bool(os.environ.get("NEXUS_RAINBOWMINER_REPORT_KEY")),
        "ingest_mode": "loopback_only",
        "reports_stored": count,
        "extra_reports_stored": extra_counts,
        "latest_report_at": latest,
        "storage_present": exists,
        "commands_executed": 0,
        "miners_started": 0,
        "pool_configuration_changed": False,
        "sensitive_fields_persisted": False,
    }


@router.post("/report")
async def ingest_report(request: Request) -> dict[str, Any]:
    _require_loopback(request)
    expected = os.environ.get("NEXUS_RAINBOWMINER_REPORT_KEY", "")
    if not expected:
        raise HTTPException(status_code=503, detail="rainbowminer_ingest_not_configured")

    form = None
    try:
        content_type = request.headers.get("content-type", "")
        if content_type.split(";", 1)[0].strip().casefold() == "multipart/form-data":
            form = await request.form(max_files=2, max_fields=16, max_part_size=MAX_EXTRA_PAYLOAD_BYTES)
            raw: dict[str, Any] = {}
            for key, value in form.multi_items():
                raw.setdefault(key, []).append(value)
            file_fields = [key for key in ("minerdata", "poolsdata") if key in raw]
            if len(file_fields) > 1:
                raise RainbowMinerReportError("multiple_extra_payloads_not_supported")
            supplied = request.headers.get("x-nexus-rainbowminer-key") or _single_value(raw, "user")
            if not supplied or not hmac.compare_digest(str(supplied), expected):
                raise HTTPException(status_code=401, detail="invalid_rainbowminer_report_key")
            if file_fields:
                kind = file_fields[0]
                file_value = raw[kind][0]
                if not isinstance(file_value, StarletteUploadFile):
                    raise RainbowMinerReportError("extra_payload_must_be_uploaded_file")
                file_content = await file_value.read(MAX_EXTRA_PAYLOAD_BYTES + 1)
                payload = normalize_extra_payload(
                    kind, file_content,
                    worker=_single_value(raw, "worker"),
                    version=_single_value(raw, "version"),
                )
                persisted = _persist_extra_report(payload)
                return {
                    "Status": "OK",
                    "accepted": True,
                    "payload_type": kind,
                    "report_id": persisted["report_id"],
                    "payload_sha256": persisted["payload_sha256"],
                    "worker": payload["worker"],
                    "records": len(payload.get("miners", payload.get("pools", []))),
                    "sensitive_fields_persisted": False,
                    "commands_executed": 0,
                    "Actions": [],
                }
        else:
            body = await request.body()
            raw = _parse_request_body(body, content_type)
            supplied = request.headers.get("x-nexus-rainbowminer-key") or _single_value(raw, "user")
            if not supplied or not hmac.compare_digest(str(supplied), expected):
                raise HTTPException(status_code=401, detail="invalid_rainbowminer_report_key")

        payload = normalize_report(raw)
        persisted = _persist_report(payload)
    except RainbowMinerReportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except sqlite3.Error:
        raise HTTPException(status_code=503, detail="rainbowminer_telemetry_storage_unavailable") from None
    finally:
        if form is not None:
            await form.close()

    return {
        "Status": "OK",
        "accepted": True,
        "report_id": persisted["report_id"],
        "payload_sha256": persisted["payload_sha256"],
        "worker": payload["worker"],
        "miner_records": len(payload["data"]),
        "device_records": len(payload["devices"]),
        "credentials_persisted": False,
        "raw_console_persisted": False,
        "commands_executed": 0,
        "Actions": [],
    }


@router.get("/pools/latest")
def latest_pools(request: Request, worker: str | None = None) -> dict[str, Any]:
    _require_loopback(request)
    try:
        payload = _latest_extra_payload("poolsdata", worker)
        return {"available": payload is not None, "payload": payload}
    except sqlite3.Error:
        raise HTTPException(status_code=503, detail="rainbowminer_telemetry_storage_unavailable") from None


@router.get("/miners/latest")
def latest_miners(request: Request, worker: str | None = None) -> dict[str, Any]:
    _require_loopback(request)
    try:
        payload = _latest_extra_payload("minerdata", worker)
        return {"available": payload is not None, "payload": payload}
    except sqlite3.Error:
        raise HTTPException(status_code=503, detail="rainbowminer_telemetry_storage_unavailable") from None


@router.get("/status")
def report_status(request: Request) -> dict[str, Any]:
    _require_loopback(request)
    try:
        return telemetry_status()
    except sqlite3.Error:
        raise HTTPException(status_code=503, detail="rainbowminer_telemetry_storage_unavailable") from None
