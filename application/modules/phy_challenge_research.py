"""Offline, bounded structural analysis helpers for the public PHY puzzle.

This module does not search for private keys, derive wallet secrets, sign messages,
or broadcast transactions. It only inspects user-supplied public puzzle metadata.
"""
from __future__ import annotations

import math
import re
import time
from typing import Any

UNICODE_DATA_VERSION = "18.0.0"
DEFAULT_S_HEX = "5b890b292ba1abd9b1"
PUBLIC_HX_CANDIDATE = "1dffd7ff0d400f0afcc3fdcefc0d400f0da10f3a390f77ff0d400f68fe0d080f"

# Unicode 18.0.0 emoji-data.txt, Emoji_Modifier_Base property (136 code points).
# Source: https://www.unicode.org/Public/18.0.0/ucd/emoji/emoji-data.txt
EMOJI_MODIFIER_BASE_RANGES = (
    (0x261D, 0x261D), (0x26F9, 0x26F9), (0x270A, 0x270C), (0x270D, 0x270D),
    (0x1F385, 0x1F385), (0x1F3C2, 0x1F3C4), (0x1F3C7, 0x1F3C7),
    (0x1F3CA, 0x1F3CA), (0x1F3CB, 0x1F3CC), (0x1F442, 0x1F443),
    (0x1F446, 0x1F450), (0x1F466, 0x1F46B), (0x1F46C, 0x1F46D),
    (0x1F46E, 0x1F478), (0x1F47C, 0x1F47C), (0x1F481, 0x1F483),
    (0x1F485, 0x1F487), (0x1F48F, 0x1F48F), (0x1F491, 0x1F491),
    (0x1F4AA, 0x1F4AA), (0x1F574, 0x1F575), (0x1F57A, 0x1F57A),
    (0x1F590, 0x1F590), (0x1F595, 0x1F596), (0x1F645, 0x1F647),
    (0x1F64B, 0x1F64F), (0x1F6A3, 0x1F6A3), (0x1F6B4, 0x1F6B5),
    (0x1F6B6, 0x1F6B6), (0x1F6C0, 0x1F6C0), (0x1F6CC, 0x1F6CC),
    (0x1F90C, 0x1F90C), (0x1F90F, 0x1F90F), (0x1F918, 0x1F918),
    (0x1F919, 0x1F91E), (0x1F91F, 0x1F91F), (0x1F926, 0x1F926),
    (0x1F930, 0x1F930), (0x1F931, 0x1F932), (0x1F933, 0x1F939),
    (0x1F93C, 0x1F93E), (0x1F977, 0x1F977), (0x1F9B5, 0x1F9B6),
    (0x1F9B8, 0x1F9B9), (0x1F9BB, 0x1F9BB), (0x1F9CD, 0x1F9CF),
    (0x1F9D1, 0x1F9DD), (0x1FAC3, 0x1FAC5), (0x1FAF0, 0x1FAF6),
    (0x1FAF7, 0x1FAF8), (0x1FAF9, 0x1FAFA),
)
SKIN_TONE_RANGE = (0x1F3FB, 0x1F3FF)


def _in_ranges(codepoint: int, ranges: tuple[tuple[int, int], ...]) -> bool:
    return any(start <= codepoint <= end for start, end in ranges)


def _codepoints(value: Any) -> list[int]:
    if not isinstance(value, str) or not value.strip():
        return []
    result = []
    for part in value.split("-"):
        try:
            cp = int(part, 16)
        except ValueError:
            continue
        if 0 <= cp <= 0x10FFFF:
            result.append(cp)
    return result


def _tone_levels(codepoints: list[int]) -> list[int]:
    return [cp - SKIN_TONE_RANGE[0] + 1 for cp in codepoints
            if SKIN_TONE_RANGE[0] <= cp <= SKIN_TONE_RANGE[1]]


def _rot13(text: str) -> str:
    out = []
    for char in text:
        if "a" <= char <= "z":
            out.append(chr((ord(char) - 97 + 13) % 26 + 97))
        elif "A" <= char <= "Z":
            out.append(chr((ord(char) - 65 + 13) % 26 + 65))
        else:
            out.append(char)
    return "".join(out)


def decode_meta_clue(value: str = "gvonys fhelucrM kbZ") -> str:
    """Reverse each whitespace-delimited word, then apply ROT13."""
    if not isinstance(value, str) or len(value) > 256:
        raise ValueError("Meta-clue must be a string of at most 256 characters.")
    reversed_words = " ".join(word[::-1] for word in value.split())
    return _rot13(reversed_words)


def _normalise_boxes(project_file: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    if not isinstance(project_file, dict) or not isinstance(project_file.get("boxes"), list):
        raise ValueError("project_file must be a JSON object containing a boxes array.")
    centre = None
    points = []
    for box in project_file["boxes"]:
        if not isinstance(box, dict):
            continue
        try:
            box_id = int(box["id"])
            x, y = float(box["x"]), float(box["y"])
            w, h = float(box["w"]), float(box["h"])
        except (KeyError, TypeError, ValueError):
            continue
        if not all(math.isfinite(v) for v in (x, y, w, h)) or w < 0 or h < 0:
            continue
        item = {
            "id": box_id,
            "cx": x + w / 2.0,
            "cy": y + h / 2.0,
            "char": str(box.get("char", "")),
            "name": str(box.get("name", "")),
            "unified": str(box.get("unified", "")),
        }
        if box_id == 258 or "BITCOIN LOGO CENTER" in item["name"].upper():
            centre = item
        else:
            cps = _codepoints(item["unified"])
            item["modifier_base"] = any(_in_ranges(cp, EMOJI_MODIFIER_BASE_RANGES) for cp in cps)
            item["tone_levels"] = _tone_levels(cps)
            points.append(item)
    ids = [p["id"] for p in points]
    if len(points) != 256:
        raise ValueError(f"Expected 256 emoji boxes after centre exclusion; received {len(points)}.")
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate emoji box IDs are not allowed.")
    return points, centre


def _pair_antipodes(points: list[dict[str, Any]], centre_x: float, centre_y: float) -> list[dict[str, Any]]:
    """Greedy minimum-reflection-distance matching; reported as a geometric hypothesis."""
    edges = []
    for i, first in enumerate(points):
        for j in range(i + 1, len(points)):
            second = points[j]
            distance = math.hypot(
                first["cx"] + second["cx"] - 2.0 * centre_x,
                first["cy"] + second["cy"] - 2.0 * centre_y,
            )
            edges.append((distance, i, j))
    edges.sort(key=lambda edge: edge[0])
    used: set[int] = set()
    pairs = []
    for distance, i, j in edges:
        if i in used or j in used:
            continue
        used.update((i, j))
        first, second = points[i], points[j]
        west, east = sorted((first, second), key=lambda p: (p["cx"], p["cy"], p["id"]))
        pairs.append({
            "west_id": west["id"],
            "east_id": east["id"],
            "west_modifier_base": west["modifier_base"],
            "east_modifier_base": east["modifier_base"],
            "west_tone_levels": west["tone_levels"],
            "east_tone_levels": east["tone_levels"],
            "west_codepoints": west["unified"],
            "east_codepoints": east["unified"],
            "reflection_error_px": round(distance, 3),
            "mid_x": (west["cx"] + east["cx"]) / 2.0,
            "mean_radius_px": (
                math.hypot(west["cx"] - centre_x, west["cy"] - centre_y)
                + math.hypot(east["cx"] - centre_x, east["cy"] - centre_y)
            ) / 2.0,
            "west_cx": west["cx"],
            "west_cy": west["cy"],
            "east_cx": east["cx"],
            "east_cy": east["cy"],
            "axis_angle_deg": _pair_axis_angle(west, east, centre_x, centre_y),
        })
    if len(pairs) != 128 or len(used) != 256:
        raise ValueError("Could not form 128 disjoint antipodal pairs from the supplied boxes.")
    return pairs



def _pair_axis_angle(
    west: dict[str, Any], east: dict[str, Any], centre_x: float, centre_y: float
) -> float:
    """Return the pair's undirected orientation in degrees [0, 180)."""
    angles = []
    for point in (west, east):
        angle = math.atan2(point["cx"] - centre_x, centre_y - point["cy"])
        angles.append(angle)
    sin_sum = math.sin(2.0 * angles[0]) + math.sin(2.0 * angles[1])
    cos_sum = math.cos(2.0 * angles[0]) + math.cos(2.0 * angles[1])
    if abs(sin_sum) + abs(cos_sum) < 1e-12:
        return (math.degrees(angles[0]) % 180.0)
    return (math.degrees(math.atan2(sin_sum, cos_sum)) / 2.0) % 180.0


def _fit_radial_phase(pairs: list[dict[str, Any]], step_resolution: float = 0.1) -> dict[str, Any]:
    """Fit a constant undirected angular increment to pairs ordered inside-out."""
    if not 0.001 <= step_resolution <= 5.0:
        raise ValueError("step_resolution must be between 0.001 and 5 degrees.")
    ordered = sorted(pairs, key=lambda item: (item["mean_radius_px"], item["mid_x"]))
    if len(ordered) < 3:
        raise ValueError("At least three pairs are required for radial phase fitting.")
    angles = [float(item["axis_angle_deg"]) % 180.0 for item in ordered]
    anchor = angles[0]
    count = max(1, int(math.ceil(180.0 / step_resolution)))
    best_step = 0.0
    best_loss = float("inf")
    best_residuals: list[float] = []
    for index in range(count):
        step = (index * step_resolution) % 180.0
        residuals = [
            ((angle - (anchor + position * step) + 90.0) % 180.0) - 90.0
            for position, angle in enumerate(angles)
        ]
        loss = sum(abs(value) for value in residuals) / len(residuals)
        if loss < best_loss:
            best_loss = loss
            best_step = step
            best_residuals = residuals
    absolute = sorted(abs(value) for value in best_residuals)
    p90_index = min(len(absolute) - 1, math.ceil(0.90 * len(absolute)) - 1)
    return {
        "classification": "geometric heuristic; not an author-confirmed spiral index",
        "order": "pairs sorted by mean radius, inside-out",
        "sample_count": len(ordered),
        "step_resolution_degrees": step_resolution,
        "candidate_angular_increment_degrees": round(best_step, 3),
        "mean_absolute_residual_degrees": round(best_loss, 3),
        "median_absolute_residual_degrees": round(absolute[len(absolute) // 2], 3),
        "p90_absolute_residual_degrees": round(absolute[p90_index], 3),
        "rms_residual_degrees": round(
            math.sqrt(sum(value * value for value in best_residuals) / len(best_residuals)), 3
        ),
        "max_absolute_residual_degrees": round(max(absolute), 3),
        "ordered_pair_ids": [[item["west_id"], item["east_id"]] for item in ordered],
    }


def _position_candidate(
    ordered_points: list[dict[str, Any]],
    positions: list[int],
    index_base: int,
    order_name: str,
    reference_hx_hex: str = PUBLIC_HX_CANDIDATE,
) -> dict[str, Any]:
    selected = []
    for position in positions:
        index = position - index_base
        if index < 0 or index >= len(ordered_points):
            continue
        point = ordered_points[index]
        cps = _codepoints(point["unified"])
        low_bytes = [cp & 0xFF for cp in cps]
        selected.append({
            "position": position,
            "ordinal_index_zero_based": index,
            "canvas_id": point["id"],
            "char": point["char"],
            "unicode": point["unified"],
            "codepoint_low_bytes_hex": bytes(low_bytes).hex(),
        })
    stream = bytes(
        byte
        for item in selected
        for byte in bytes.fromhex(item["codepoint_low_bytes_hex"])
    ).hex()
    return {
        "order": order_name,
        "index_base": index_base,
        "selection_complete": len(selected) == len(positions),
        "selected": selected,
        "raw_codepoint_low_byte_stream_hex": stream,
        "raw_codepoint_low_byte_stream_length": len(stream) // 2,
        "matches_public_hx_candidate": stream == reference_hx_hex.lower(),
        "interpretation": (
            "candidate indexing only; neither angle nor radius order is established as the true spiral order"
        ),
    }


def _bit_window_report(bits: str, s_bytes: bytes, order_name: str) -> dict[str, Any]:
    if len(bits) != 256 or any(bit not in "01" for bit in bits):
        raise ValueError("A candidate emoji bitstream must contain exactly 256 binary digits.")
    if len(s_bytes) != 9:
        raise ValueError("s_hex must encode exactly 9 bytes (72 bits) for PHY prefix/suffix verification.")
    expected_options = {
        "s_big_endian": "".join(f"{value:08b}" for value in s_bytes),
        "s_bytes_reversed": "".join(f"{value:08b}" for value in reversed(s_bytes)),
        "s_bits_reversed": "".join(f"{value:08b}" for value in s_bytes)[::-1],
    }
    candidates = []
    for stream_name, candidate_stream in (("forward", bits), ("reverse", bits[::-1])):
        for complement in (False, True):
            candidate = candidate_stream.translate(str.maketrans("01", "10")) if complement else candidate_stream
            for expected_name, expected in expected_options.items():
                for window_name, window in (("first_72", candidate[:72]), ("last_72", candidate[-72:])):
                    distance = sum(left != right for left, right in zip(window, expected))
                    candidates.append({
                        "stream_direction": stream_name,
                        "complemented": complement,
                        "expected_s_orientation": expected_name,
                        "window": window_name,
                        "hamming_distance": distance,
                        "exact_match": distance == 0,
                    })
    candidates.sort(key=lambda item: (item["hamming_distance"], item["stream_direction"] != "forward", item["complemented"]))
    return {
        "order": order_name,
        "bit_count": 256,
        "s_bit_count": 72,
        "exact_matches": [item for item in candidates if item["exact_match"]],
        "best_candidates": candidates[:6],
        "interpretation": "A zero Hamming distance confirms only the 72-bit window check, not the full puzzle solution.",
    }


def verify_bit_values_by_id(
    points: list[dict[str, Any]],
    bit_values_by_id: dict[Any, Any],
    s_bytes: bytes,
    centre_x: float,
    centre_y: float,
) -> dict[str, Any]:
    """Compare caller-provided one-bit-per-emoji values against s prefix/suffix windows."""
    if not isinstance(bit_values_by_id, dict):
        raise ValueError("bit_values_by_id must be an object mapping each emoji box ID to 0 or 1.")
    expected_ids = {point["id"] for point in points}
    normalized: dict[int, int] = {}
    for key, value in bit_values_by_id.items():
        try:
            box_id = int(key)
        except (TypeError, ValueError):
            raise ValueError("bit_values_by_id keys must be integer emoji box IDs.") from None
        if isinstance(value, bool):
            bit = int(value)
        elif isinstance(value, int) and value in (0, 1):
            bit = value
        else:
            raise ValueError("Every value in bit_values_by_id must be 0 or 1.")
        if box_id in normalized:
            raise ValueError("Duplicate emoji box IDs in bit_values_by_id.")
        normalized[box_id] = bit
    if set(normalized) != expected_ids:
        missing = sorted(expected_ids - set(normalized))
        extra = sorted(set(normalized) - expected_ids)
        raise ValueError(
            f"bit_values_by_id must cover all 256 emoji IDs exactly; missing={missing[:8]}, extra={extra[:8]}."
        )
    angle_order = sorted(
        points,
        key=lambda item: (
            (math.degrees(math.atan2(item["cx"] - centre_x, centre_y - item["cy"])) + 360.0) % 360.0,
            item["id"],
        ),
    )
    radius_order = sorted(
        points,
        key=lambda item: (math.hypot(item["cx"] - centre_x, item["cy"] - centre_y), item["id"]),
    )
    orders = {
        "canvas_id_ascending": sorted(points, key=lambda item: item["id"]),
        "canvas_id_descending": sorted(points, key=lambda item: item["id"], reverse=True),
        "angle_ascending_top_clockwise": angle_order,
        "angle_descending": list(reversed(angle_order)),
        "radius_ascending_center_out": radius_order,
        "radius_descending_outside_in": list(reversed(radius_order)),
    }
    reports = []
    for order_name, ordered in orders.items():
        bitstream = "".join(str(normalized[point["id"]]) for point in ordered)
        reports.append(_bit_window_report(bitstream, s_bytes, order_name))
    exact = [
        {"order": report["order"], **match}
        for report in reports
        for match in report["exact_matches"]
    ]
    best = sorted(
        ({"order": report["order"], **candidate} for report in reports for candidate in report["best_candidates"]),
        key=lambda item: item["hamming_distance"],
    )[:12]
    return {
        "status": "verified_bit_window" if exact else "no_exact_72_bit_window_match",
        "source": "caller_supplied_bit_values_by_canvas_id",
        "orders_tested": list(orders),
        "exact_match_count": len(exact),
        "exact_matches": exact,
        "best_candidates": best,
        "per_order": reports,
        "interpretation": "Bit assignments are external input; this check validates the 72-bit s window and does not infer the visual bit-mapping rule.",
    }



def automatic_bit_feature_tests(
    points: list[dict[str, Any]],
    s_bytes: bytes,
    centre_x: float,
    centre_y: float,
) -> dict[str, Any]:
    """Test simple Unicode-derived one-bit-per-emoji hypotheses against s windows."""
    feature_specs = {
        "emoji_modifier_base": lambda item: item["modifier_base"],
        "skin_tone_present": lambda item: bool(item["tone_levels"]),
        "skin_tone_odd_level": lambda item: any(level % 2 for level in item["tone_levels"]),
        "skin_tone_even_level": lambda item: any(level % 2 == 0 for level in item["tone_levels"]),
        "skin_tone_dark_4_or_5": lambda item: any(level >= 4 for level in item["tone_levels"]),
        "gender_marker_present": lambda item: any(cp in (0x2640, 0x2642) for cp in _codepoints(item["unified"])),
        "zero_width_joiner_present": lambda item: 0x200D in _codepoints(item["unified"]),
        "multiple_codepoints": lambda item: len(_codepoints(item["unified"])) > 1,
    }
    if len(s_bytes) != 9:
        return {
            "status": "not_run",
            "reason": "Automatic bit-feature checks require a 9-byte (72-bit) ECDSA s value.",
            "features_tested": [],
        }
    reports = []
    for name, feature in feature_specs.items():
        values = {item["id"]: int(bool(feature(item))) for item in points}
        report = verify_bit_values_by_id(points, values, s_bytes, centre_x, centre_y)
        hamming = min(candidate["hamming_distance"] for candidate in report["best_candidates"])
        reports.append({
            "feature": name,
            "one_count": sum(values.values()),
            "exact_match_count": report["exact_match_count"],
            "best_hamming_distance": hamming,
            "best_candidates": report["best_candidates"][:3],
        })
    reports.sort(key=lambda item: (item["exact_match_count"] == 0, item["best_hamming_distance"]))
    return {
        "status": "exact_candidate_found" if any(item["exact_match_count"] for item in reports) else "no_exact_unicode_feature_candidate",
        "features_tested": list(feature_specs),
        "exact_match_count": sum(item["exact_match_count"] for item in reports),
        "results": reports,
        "interpretation": "These are simple Unicode-only hypotheses; a pixel-derived skin-tone or grayscale rule is not tested here.",
    }


def analyze_project_file(
    project_file: dict[str, Any],
    s_hex: str = DEFAULT_S_HEX,
    bit_values_by_id: dict[Any, Any] | None = None,
) -> dict[str, Any]:
    """Analyze supplied PHY emoji metadata without key search or external I/O."""
    started = time.perf_counter()
    if not isinstance(s_hex, str) or not re.fullmatch(r"(?:[0-9a-fA-F]{2}){1,32}", s_hex):
        raise ValueError("s_hex must be an even-length hexadecimal string (1–32 bytes).")
    s_bytes = bytes.fromhex(s_hex)
    points, centre = _normalise_boxes(project_file)
    if centre:
        centre_x, centre_y = centre["cx"], centre["cy"]
        centre_source = f"box_id_{centre['id']}"
    else:
        try:
            centre_x = float(project_file.get("natW", 2048)) / 2.0
            centre_y = float(project_file.get("natH", 2048)) / 2.0
        except (TypeError, ValueError):
            raise ValueError("Invalid canvas dimensions.") from None
        centre_source = "canvas_midpoint_fallback"

    pairs = _pair_antipodes(points, centre_x, centre_y)
    bit_window_validation = (
        verify_bit_values_by_id(points, bit_values_by_id, s_bytes, centre_x, centre_y)
        if bit_values_by_id is not None else {
            "status": "not_run",
            "reason": "Provide bit_values_by_id with one explicit 0/1 value for every emoji to test the author's 72-bit s-window hint.",
        }
    )
    automatic_bit_features = automatic_bit_feature_tests(points, s_bytes, centre_x, centre_y)
    west_east = sorted(pairs, key=lambda p: (p["mid_x"], p["mean_radius_px"]))
    east_west = list(reversed(west_east))
    inside_out = sorted(pairs, key=lambda p: (p["mean_radius_px"], p["mid_x"]))
    outside_in = list(reversed(inside_out))

    by_id = {point["id"]: point for point in points}
    canvas_id_selected = []
    for value in s_bytes:
        point = by_id.get(value)
        if point:
            canvas_id_selected.append({
                "id": value,
                "char": point["char"],
                "name": point["name"],
                "unicode": point["unified"],
                "modifier_base": point["modifier_base"],
                "tone_levels": point["tone_levels"],
            })

    for point in points:
        point["angle_deg"] = (math.degrees(math.atan2(point["cx"] - centre_x, centre_y - point["cy"])) + 360.0) % 360.0
        point["radius_px"] = math.hypot(point["cx"] - centre_x, point["cy"] - centre_y)
    angle_order = sorted(points, key=lambda item: (item["angle_deg"], item["radius_px"], item["id"]))
    radius_order = sorted(points, key=lambda item: (item["radius_px"], item["angle_deg"], item["id"]))
    angle_index_86_id = angle_order[86]["id"] if len(angle_order) > 86 else None
    position_candidates = {
        "angle_zero_based": _position_candidate(angle_order, list(s_bytes), 0, "angle ascending, top=0 clockwise"),
        "angle_one_based": _position_candidate(angle_order, list(s_bytes), 1, "angle ascending, top=0 clockwise"),
        "radius_zero_based": _position_candidate(radius_order, list(s_bytes), 0, "radius ascending, centre-out"),
        "radius_one_based": _position_candidate(radius_order, list(s_bytes), 1, "radius ascending, centre-out"),
    }
    canvas_id_low_bytes = [cp & 0xFF for item in canvas_id_selected for cp in _codepoints(item["unicode"])]
    radial_phase_fit = _fit_radial_phase(pairs)

    expected_ids = set(range(1, 258))
    observed_ids = set(by_id)
    missing_ids = sorted(expected_ids - observed_ids)
    pairs_with_base = sum(p["west_modifier_base"] or p["east_modifier_base"] for p in pairs)
    pairs_with_two_bases = sum(p["west_modifier_base"] and p["east_modifier_base"] for p in pairs)
    pairs_with_tones = sum(bool(p["west_tone_levels"] or p["east_tone_levels"]) for p in pairs)
    errors = [p["reflection_error_px"] for p in pairs]

    return {
        "status": "structural_analysis_only",
        "unicode_data_version": UNICODE_DATA_VERSION,
        "centre": {"x": centre_x, "y": centre_y, "source": centre_source},
        "emoji_boxes": len(points),
        "pair_count": len(pairs),
        "missing_box_ids_1_to_257": missing_ids,
        "pairing": {
            "method": "greedy_minimum_reflection_distance",
            "classification": "geometric hypothesis; not author-confirmed decoding",
            "mean_reflection_error_px": round(sum(errors) / len(errors), 3),
            "max_reflection_error_px": max(errors),
            "pairs_with_emoji_modifier_base": pairs_with_base,
            "pairs_with_two_modifier_bases": pairs_with_two_bases,
            "pairs_with_literal_skin_tone_codepoints": pairs_with_tones,
            "community_claim_2026_11_25": "124/124 pair-tone recovery (unverified forum participant claim)",
            "community_claim_reconciled": pairs_with_base == 124,
        },
        "reference_observations": {
            "angle_order_zero_based_index_86_canvas_id": angle_index_86_id,
            "forum_reported_canvas_id_at_index_86": 217,
            "matches_forum_angle_order_observation": angle_index_86_id == 217,
            "interpretation": "single coordinate-order sanity check only; does not establish the complete true spiral order",
        },
        "s_byte_position_candidates": {
            "s_hex": s_bytes.hex(),
            "position_values": list(s_bytes),
            "reference_hx_hex": PUBLIC_HX_CANDIDATE,
            "reference_hx_source": "public forum analysis; candidate only, not author-confirmed final key data",
            "candidate_orders": position_candidates,
        },
        "signature_s_byte_canvas_id_diagnostic": {
            "s_hex": s_bytes.hex(),
            "byte_values": list(s_bytes),
            "direct_canvas_id_lookup_complete": len(canvas_id_selected) == len(s_bytes),
            "selected_emoji": canvas_id_selected,
            "raw_codepoint_low_byte_stream_length": len(canvas_id_low_bytes),
            "raw_codepoint_low_byte_stream_hex": bytes(canvas_id_low_bytes).hex(),
            "interpretation": "diagnostic only; canvas object IDs are not established as spiral positions",
        },
        "radial_phase_fit": radial_phase_fit,
        "bit_window_validation": bit_window_validation,
        "automatic_bit_feature_tests": automatic_bit_features,
        "meta_clue": {
            "input": "gvonys fhelucrM kbZ",
            "decoded": decode_meta_clue(),
            "reading": "reverse each word, then ROT13",
            "interpretation": "Latin phrase; Zephyrus is the west wind. Directional hint, not a confirmed emoji bit order.",
        },
        "pair_orders": {
            "west_to_east": [[p["west_id"], p["east_id"]] for p in west_east],
            "east_to_west": [[p["east_id"], p["west_id"]] for p in east_west],
            "inside_out": [[p["west_id"], p["east_id"]] for p in inside_out],
            "outside_in": [[p["west_id"], p["east_id"]] for p in outside_in],
        },
        "pairs": pairs,
        "limits": [
            "No private-key or nonce search is performed.",
            "No private key, seed phrase, WIF, or signing operation is produced.",
            "No network requests, wallet access, or transaction broadcast.",
            "Pair matching and direction orders remain hypotheses until checked against the puzzle's cryptographic evidence.",
        ],
        "elapsed_ms": round((time.perf_counter() - started) * 1000.0, 3),
    }


def catalog() -> dict[str, Any]:
    return {
        "module": "phy_challenge_research",
        "state": "implemented_local_analysis",
        "unicode_data_version": UNICODE_DATA_VERSION,
        "input": "caller-supplied public emoji-mapping project JSON",
        "operations": [
            "Unicode 18.0 Emoji_Modifier_Base and skin-tone classification",
            "geometric antipodal pairing hypotheses",
            "radial constant-angular-step fit with residual statistics",
            "raw low-byte stream extraction for the nine s-selected emoji",
            "explicit 256-bit stream verification against first/last 72 bits of s",
            "automatic Unicode-derived one-bit feature hypotheses against s windows",
            "west/east and radial candidate ordering exports",
            "nine s-byte values tested as positional selectors across candidate spatial orders",
            "direct canvas-ID lookup retained only as a diagnostic",
            "reverse-word plus ROT13 meta-clue transform",
            "compressed secp256k1 public-point validation (no scalar derivation)",
        ],
        "not_implemented": [
            "confirmed tone-to-bit encoding",
            "confirmed final scalar derivation",
            "private-key recovery or signing",
        ],
        "network_access": False,
        "wallet_access": False,
        "auto_execution": False,
    }


SECP256K1_P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F


def validate_compressed_public_key(point_hex: str) -> dict[str, Any]:
    """Validate a supplied 33-byte compressed secp256k1 point; never derives a scalar."""
    if not isinstance(point_hex, str) or not re.fullmatch(r"(?:02|03)[0-9a-fA-F]{64}", point_hex):
        raise ValueError("Compressed secp256k1 point must be 33 bytes with prefix 02 or 03.")
    raw = bytes.fromhex(point_hex)
    x = int.from_bytes(raw[1:], "big")
    if x >= SECP256K1_P:
        raise ValueError("Compressed point x-coordinate is outside the secp256k1 field.")
    rhs = (pow(x, 3, SECP256K1_P) + 7) % SECP256K1_P
    y = pow(rhs, (SECP256K1_P + 1) // 4, SECP256K1_P)
    if pow(y, 2, SECP256K1_P) != rhs:
        raise ValueError("Compressed point does not lie on secp256k1.")
    if (y & 1) != (raw[0] & 1):
        y = SECP256K1_P - y
    return {
        "valid_curve_point": True,
        "curve": "secp256k1",
        "compressed_hex": raw.hex(),
        "x_hex": format(x, "064x"),
        "y_parity": y & 1,
        "classification": "public-point-format-and-curve-check_only",
        "private_scalar_derived": False,
        "signature_verified": False,
    }
