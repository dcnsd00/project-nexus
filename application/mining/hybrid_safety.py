"""Fail-closed resource checks for mining lanes."""
from __future__ import annotations


def validate_engine_resources(engine: str, hardware: dict, limits: dict | None = None) -> dict:
    limits = limits or {}
    if engine not in {'cpu', 'gpu'}:
        return {'allowed': False, 'reasons': ['invalid_engine']}
    if engine == 'cpu':
        return {'allowed': True, 'reasons': [], 'telemetry': 'not_required'}
    reasons = []
    if not hardware.get('available') or hardware.get('memory_total_mb') is None:
        reasons.append('gpu_telemetry_missing')
    else:
        total = float(hardware['memory_total_mb'])
        required = float(limits.get('required_vram_mb', 0))
        margin = float(limits.get('vram_margin_mb', 256))
        if total < required + margin:
            reasons.append('vram_insufficient')
    temperature = hardware.get('temperature_c')
    max_temp = float(limits.get('max_temperature_c', 85))
    if temperature is None:
        reasons.append('temperature_telemetry_missing')
    elif float(temperature) >= max_temp:
        reasons.append('temperature_limit')
    return {'allowed': not reasons, 'reasons': reasons, 'telemetry': 'measured' if not reasons else 'incomplete_or_unsafe'}
