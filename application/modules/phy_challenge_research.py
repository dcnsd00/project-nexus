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
        })
    if len(pairs) != 128 or len(used) != 256:
        raise ValueError("Could not form 128 disjoint antipodal pairs from the supplied boxes.")
    return pairs


def analyze_project_file(
    project_file: dict[str, Any],
    s_hex: str = DEFAULT_S_HEX,
) -> dict[str, Any]:
    """Analyze supplied PHY emoji metadata without key search or external I/O."""
    started = time.perf_counter()
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
    west_east = sorted(pairs, key=lambda p: (p["mid_x"], p["mean_radius_px"]))
    east_west = list(reversed(west_east))
    inside_out = sorted(pairs, key=lambda p: (p["mean_radius_px"], p["mid_x"]))
    outside_in = list(reversed(inside_out))

    if not isinstance(s_hex, str) or not re.fullmatch(r"(?:[0-9a-fA-F]{2}){1,32}", s_hex):
        raise ValueError("s_hex must be an even-length hexadecimal string (1–32 bytes).")
    s_bytes = bytes.fromhex(s_hex)
    by_id = {point["id"]: point for point in points}
    selected = []
    for value in s_bytes:
        point = by_id.get(value)
        if point:
            selected.append({
                "id": value,
                "char": point["char"],
                "name": point["name"],
                "unicode": point["unified"],
                "modifier_base": point["modifier_base"],
                "tone_levels": point["tone_levels"],
            })

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
        "signature_s_byte_id_check": {
            "s_hex": s_bytes.hex(),
            "byte_ids_in_order": list(s_bytes),
            "all_ids_present": len(selected) == len(s_bytes),
            "selected_emoji": selected,
            "interpretation": "set/ID correspondence only; does not validate a key or signature solution",
        },
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
            "west/east and radial candidate ordering exports",
            "nine-byte ECDSA-s-to-emoji-ID correspondence check",
            "reverse-word plus ROT13 meta-clue transform",
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
