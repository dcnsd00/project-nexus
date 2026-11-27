"""NEXUS bounded multi-method puzzle solver.

This module composes existing exact mathematics with bounded, explicit puzzle
strategies. It never evaluates Python expressions, contacts networks, searches
wallet secrets, or launches external workers.
"""
from __future__ import annotations

import base64
import binascii
import math
import re
from typing import Any
from urllib.parse import unquote

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from modules import hybrid_solver

MAX_TEXT_LENGTH = 4096
MAX_CSP_VARIABLES = 16
MAX_CSP_DOMAIN = 16
MAX_CSP_SEARCH_NODES = 100_000
MAX_CSP_SOLUTIONS = 10

MORSE = {
    ".-": "A", "-...": "B", "-.-.": "C", "-..": "D", ".": "E",
    "..-.": "F", "--.": "G", "....": "H", "..": "I", ".---": "J",
    "-.-": "K", ".-..": "L", "--": "M", "-.": "N", "---": "O",
    ".--.": "P", "--.-": "Q", ".-.": "R", "...": "S", "-": "T",
    "..-": "U", "...-": "V", ".--": "W", "-..-": "X", "-.--": "Y",
    "--..": "Z", "-----": "0", ".----": "1", "..---": "2",
    "...--": "3", "....-": "4", ".....": "5", "-....": "6",
    "--...": "7", "---..": "8", "----.": "9",
}


def capabilities() -> dict[str, Any]:
    return {
        "module": "NEXUS Multi-Method Puzzle Solver",
        "version": "0.1.0",
        "strategies": [
            {"id": "text_decode", "available": True,
             "methods": ["hex", "base64", "base64url", "base32", "base85",
                         "binary_ascii", "decimal_bytes", "base58", "url_percent",
                         "caesar_26", "morse", "atbash", "a1z26", "reverse"]},
            {"id": "modular_congruence", "available": True, "backend": "hybrid_solver.native_exact"},
            {"id": "linear_system", "available": True, "backend": "hybrid_solver.sympy_exact_rational",
             "dependency": "SymPy"},
            {"id": "bitvector_xor", "available": True, "backend": "hybrid_solver.native_exact_xor",
             "cross_check": "optional Z3"},
            {"id": "finite_csp", "available": True,
             "methods": ["backtracking", "MRV", "constraint_propagation", "independent_verification"]},
            {"id": "sha256_reduced_round_research", "available": False,
             "reason": "Existing research implementation is an isolated reduced-round experiment, not a generic puzzle backend."},
            {"id": "natural_language_logic_grid", "available": False,
             "reason": "No parser/model adapter is integrated yet; express a supported puzzle as finite_csp constraints."},
        ],
        "classical_cipher": ["vigenere_known_key", "rail_fence_known_rails", "affine_known_parameters"],
        "limits": {
            "text_characters": MAX_TEXT_LENGTH,
            "csp_variables": MAX_CSP_VARIABLES,
            "csp_domain_values": MAX_CSP_DOMAIN,
            "csp_search_nodes": MAX_CSP_SEARCH_NODES,
            "csp_returned_solutions": MAX_CSP_SOLUTIONS,
        },
        "policy": "Local bounded puzzle solving only. No wallet/seed/password/key search, third-party targeting, network access or automatic actions.",
    }


def _vigenere_decrypt(value: str, key: str) -> str:
    if not isinstance(value, str) or not value or len(value) > MAX_TEXT_LENGTH:
        raise ValueError("text must contain 1..4096 characters")
    if not isinstance(key, str) or not 1 <= len(key) <= 64 or not key.isascii() or not key.isalpha():
        raise ValueError("Vigenere key must contain 1..64 ASCII letters")
    shifts = [ord(char.upper()) - ord("A") for char in key]
    output = []
    offset = 0
    for char in value:
        if char.isascii() and char.isalpha():
            base = ord("A") if char.isupper() else ord("a")
            output.append(chr((ord(char) - base - shifts[offset % len(shifts)]) % 26 + base))
            offset += 1
        else:
            output.append(char)
    return "".join(output)


def _rail_fence_decrypt(value: str, rails: int) -> str:
    if not isinstance(value, str) or not value or len(value) > MAX_TEXT_LENGTH:
        raise ValueError("text must contain 1..4096 characters")
    if isinstance(rails, bool) or not isinstance(rails, int) or not 2 <= rails <= 12:
        raise ValueError("rails must be an integer from 2 to 12")
    if rails >= len(value):
        return value
    pattern = []
    rail, direction = 0, 1
    for _ in value:
        pattern.append(rail)
        if rail == 0:
            direction = 1
        elif rail == rails - 1:
            direction = -1
        rail += direction
    counts = [pattern.count(index) for index in range(rails)]
    rows = []
    cursor = 0
    for count in counts:
        rows.append(list(value[cursor:cursor + count]))
        cursor += count
    offsets = [0] * rails
    result = []
    for rail_index in pattern:
        result.append(rows[rail_index][offsets[rail_index]])
        offsets[rail_index] += 1
    return "".join(result)


def _affine_decrypt(value: str, a: int, b: int) -> str:
    if isinstance(a, bool) or not isinstance(a, int) or isinstance(b, bool) or not isinstance(b, int):
        raise ValueError("affine parameters a and b must be integers")
    if math.gcd(a, 26) != 1:
        raise ValueError("affine parameter a must be coprime with 26")
    inverse = pow(a, -1, 26)
    output = []
    for char in value:
        if char.isascii() and char.isalpha():
            base = ord("A") if char.isupper() else ord("a")
            output.append(chr(((inverse * ((ord(char) - base) - b)) % 26) + base))
        else:
            output.append(char)
    return "".join(output)


def _decode_text(value: str) -> dict[str, Any]:
    if not isinstance(value, str) or not value or len(value) > MAX_TEXT_LENGTH:
        raise ValueError(f"text must contain 1..{MAX_TEXT_LENGTH} characters")
    compact = value.strip()
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def add(method: str, text: str) -> None:
        if not text or len(text) > MAX_TEXT_LENGTH:
            return
        key = (method, text)
        if key in seen:
            return
        seen.add(key)
        printable = sum(ch.isprintable() or ch in "\n\r\t" for ch in text)
        candidates.append({
            "method": method,
            "text": text,
            "printable_ratio": round(printable / max(1, len(text)), 4),
        })

    add("identity", value)
    add("url_percent", unquote(value))
    add("reverse", value[::-1])

    atbash = "".join(
        chr((ord("Z") - (ord(ch) - ord("A")))) if ch.isupper()
        else chr(ord("z") - (ord(ch) - ord("a"))) if ch.islower()
        else ch
        for ch in value
    )
    add("atbash", atbash)

    if re.fullmatch(r"\d{1,2}(?:[\s,;/|-]+\d{1,2})+", compact):
        numbers = [int(item) for item in re.split(r"[\s,;/|-]+", compact)]
        if all(1 <= number <= 26 for number in numbers):
            add("a1z26", "".join(chr(ord("A") + number - 1) for number in numbers))

    hex_text = compact[2:] if compact.lower().startswith("0x") else compact
    if len(hex_text) % 2 == 0 and re.fullmatch(r"[0-9a-fA-F]+", hex_text or "!", flags=0):
        try:
            add("hex", bytes.fromhex(hex_text).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            pass

    for method, decoder in (
        ("base64", base64.b64decode),
        ("base64url", base64.urlsafe_b64decode),
        ("base32", base64.b32decode),
        ("base85", base64.b85decode),
    ):
        try:
            if method == "base64":
                raw = decoder(compact, validate=True)
            else:
                raw = decoder(compact + ("=" * ((-len(compact)) % 8 if method == "base32"
                                              else (-len(compact)) % 4 if method == "base64url" else 0)))
            add(method, raw.decode("utf-8"))
        except (ValueError, binascii.Error, UnicodeDecodeError):
            pass

    # Base58 is decoded locally with the Bitcoin alphabet; no wallet/key use.
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    if compact and all(ch in alphabet for ch in compact):
        try:
            number = 0
            for char in compact:
                number = number * 58 + alphabet.index(char)
            body = number.to_bytes((number.bit_length() + 7) // 8, "big") if number else b""
            body = (b"\x00" * (len(compact) - len(compact.lstrip("1")))) + body
            add("base58", body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            pass

    if re.fullmatch(r"(?:[01]{8}[ \t\r\n]*)+", compact):
        try:
            binary_text = "".join(compact.split())
            raw = bytes(int(binary_text[i:i + 8], 2) for i in range(0, len(binary_text), 8))
            add("binary_ascii", raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            pass

    if re.fullmatch(r"\d{1,3}(?:[ ,;]+\d{1,3})+", compact):
        try:
            raw = bytes(int(item) for item in re.split(r"[ ,;]+", compact))
            add("decimal_bytes", raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            pass

    morse_tokens = compact.split()
    if morse_tokens and all(token in MORSE for token in morse_tokens):
        add("morse", "".join(MORSE[token] for token in morse_tokens))

    for shift in range(1, 26):
        translated_chars = []
        for ch in value:
            if ch.isascii() and ch.isalpha():
                base = ord("A") if ch.isupper() else ord("a")
                translated_chars.append(chr((ord(ch) - base - shift) % 26 + base))
            else:
                translated_chars.append(ch)
        add(f"caesar_shift_{shift}", "".join(translated_chars))

    candidates.sort(key=lambda item: (item["printable_ratio"], item["method"] == "identity"), reverse=True)
    return {"kind": "text_decode", "candidate_count": len(candidates),
            "candidates": candidates[:32], "verified": False,
            "note": "Decodările sunt ipoteze candidate; confirmarea depinde de contextul puzzle-ului."}


def _csp_validate(problem: dict[str, Any]) -> tuple[dict[str, list[int]], list[dict[str, Any]], int, int]:
    raw_vars = problem.get("variables")
    raw_constraints = problem.get("constraints")
    if not isinstance(raw_vars, dict) or not 1 <= len(raw_vars) <= MAX_CSP_VARIABLES:
        raise ValueError(f"variables must be an object with 1..{MAX_CSP_VARIABLES} variables")
    if not isinstance(raw_constraints, list) or not 1 <= len(raw_constraints) <= 64:
        raise ValueError("constraints must be a list containing 1..64 constraints")

    variables: dict[str, list[int]] = {}
    search_space = 1
    for name, domain in raw_vars.items():
        if not isinstance(name, str) or not name.isidentifier() or len(name) > 24:
            raise ValueError("variable names must be simple identifiers")
        if (not isinstance(domain, list) or not 1 <= len(domain) <= MAX_CSP_DOMAIN
                or any(isinstance(v, bool) or not isinstance(v, int) for v in domain)):
            raise ValueError(f"domain for {name} must contain 1..{MAX_CSP_DOMAIN} integers")
        values = list(dict.fromkeys(domain))
        if len(values) != len(domain):
            raise ValueError(f"domain for {name} must not contain duplicates")
        variables[name] = values
        search_space *= len(values)
        if search_space > MAX_CSP_SEARCH_NODES:
            raise ValueError("product of domain sizes exceeds the bounded search space")

    checked: list[dict[str, Any]] = []
    allowed = {"eq", "ne", "lt", "le", "gt", "ge", "sum_eq", "product_eq", "all_different", "xor_eq"}
    for item in raw_constraints:
        if not isinstance(item, dict) or item.get("type") not in allowed:
            raise ValueError("unsupported or malformed constraint type")
        kind = item["type"]
        if kind in {"eq", "ne", "lt", "le", "gt", "ge"}:
            left, right = item.get("left"), item.get("right")
            for ref in (left, right):
                if isinstance(ref, bool) or not (isinstance(ref, int) or (isinstance(ref, str) and ref in variables)):
                    raise ValueError("relation operands must be variable names or integer constants")
            checked.append({"type": kind, "left": left, "right": right})
        else:
            names = item.get("variables")
            if (not isinstance(names, list) or len(names) < 2 or
                    any(not isinstance(n, str) or n not in variables for n in names)):
                raise ValueError(f"{kind} requires at least two declared variables")
            if len(set(names)) != len(names):
                raise ValueError(f"{kind} variable names must be unique")
            if kind == "all_different":
                checked.append({"type": kind, "variables": list(names)})
            else:
                target = item.get("target")
                if isinstance(target, bool) or not isinstance(target, int):
                    raise ValueError(f"{kind} target must be an integer")
                if kind == "product_eq" and abs(target) > 10**18:
                    raise ValueError("product_eq target exceeds safety bound")
                checked.append({"type": kind, "variables": list(names), "target": target})
    requested_nodes = problem.get("max_search_nodes", MAX_CSP_SEARCH_NODES)
    requested_solutions = problem.get("max_solutions", MAX_CSP_SOLUTIONS)
    if isinstance(requested_nodes, bool) or not isinstance(requested_nodes, int) or requested_nodes < 1:
        raise ValueError("max_search_nodes must be a positive integer")
    if isinstance(requested_solutions, bool) or not isinstance(requested_solutions, int) or not 1 <= requested_solutions <= MAX_CSP_SOLUTIONS:
        raise ValueError(f"max_solutions must be 1..{MAX_CSP_SOLUTIONS}")
    return variables, checked, min(requested_nodes, MAX_CSP_SEARCH_NODES), requested_solutions


def _constraint_ready(constraint: dict[str, Any], assignment: dict[str, int]) -> bool:
    kind = constraint["type"]
    if kind in {"eq", "ne", "lt", "le", "gt", "ge"}:
        left = assignment.get(constraint["left"]) if isinstance(constraint["left"], str) else constraint["left"]
        right = assignment.get(constraint["right"]) if isinstance(constraint["right"], str) else constraint["right"]
        if left is None or right is None:
            return True
        return {"eq": left == right, "ne": left != right, "lt": left < right,
                "le": left <= right, "gt": left > right, "ge": left >= right}[kind]
    names = constraint["variables"]
    values = [assignment.get(name) for name in names]
    assigned = [value for value in values if value is not None]
    if kind == "all_different":
        return len(assigned) == len(set(assigned))
    if kind == "sum_eq":
        if len(assigned) < len(names):
            return True
        return sum(assigned) == constraint["target"]
    if len(assigned) < len(names):
        return True
    if kind == "product_eq":
        return math.prod(assigned) == constraint["target"]
    if kind == "xor_eq":
        result = 0
        for value in assigned:
            result ^= value
        return result == constraint["target"]
    return False


def _csp_full_valid(constraints: list[dict[str, Any]], assignment: dict[str, int]) -> bool:
    for constraint in constraints:
        kind = constraint["type"]
        if kind == "sum_eq":
            if sum(assignment[name] for name in constraint["variables"]) != constraint["target"]:
                return False
        elif kind == "product_eq":
            if math.prod(assignment[name] for name in constraint["variables"]) != constraint["target"]:
                return False
        elif kind == "xor_eq":
            result = 0
            for name in constraint["variables"]:
                result ^= assignment[name]
            if result != constraint["target"]:
                return False
        elif kind == "all_different":
            values = [assignment[name] for name in constraint["variables"]]
            if len(values) != len(set(values)):
                return False
        elif not _constraint_ready(constraint, assignment):
            return False
    return True


def _solve_csp(problem: dict[str, Any]) -> dict[str, Any]:
    variables, constraints, node_limit, solution_limit = _csp_validate(problem)
    ordered = sorted(variables, key=lambda name: (len(variables[name]), name))
    assignment: dict[str, int] = {}
    solutions: list[dict[str, int]] = []
    nodes = 0
    stopped_at_limit = False

    def visit(index: int) -> None:
        nonlocal nodes, stopped_at_limit
        if len(solutions) >= solution_limit or nodes >= node_limit:
            stopped_at_limit = True
            return
        if index == len(ordered):
            if _csp_full_valid(constraints, assignment):
                solutions.append(dict(assignment))
            return
        name = ordered[index]
        for value in variables[name]:
            if nodes >= node_limit or len(solutions) >= solution_limit:
                stopped_at_limit = True
                return
            nodes += 1
            assignment[name] = value
            if all(_constraint_ready(c, assignment) for c in constraints):
                visit(index + 1)
            assignment.pop(name, None)

    visit(0)
    status = "SOLVED" if solutions else ("SEARCH_LIMIT_REACHED" if stopped_at_limit else "UNSAT")
    return {
        "kind": "finite_csp", "status": status, "solutions": solutions,
        "solution_count_returned": len(solutions), "nodes_visited": nodes,
        "search_node_limit": node_limit, "search_complete": not stopped_at_limit,
        "independent_verification": all(_csp_full_valid(constraints, s) for s in solutions),
        "verified": bool(solutions) and all(_csp_full_valid(constraints, s) for s in solutions),
        "auto_apply": False,
    }


def solve(problem: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(problem, dict):
        raise ValueError("problem must be an object")
    kind = problem.get("kind")
    if kind in {"text_decode", "auto_text"}:
        return _decode_text(problem.get("text"))
    if kind == "modular_congruence":
        return {"kind": kind, **hybrid_solver.solve_modular(
            problem.get("a"), problem.get("b"), problem.get("modulus"))}
    if kind == "linear_system":
        return {"kind": kind, **hybrid_solver.solve_linear_system(
            problem.get("matrix"), problem.get("rhs"))}
    if kind == "bitvector_xor":
        return {"kind": kind, **hybrid_solver.solve_bitvector_xor(
            problem.get("variables"), problem.get("target"), problem.get("width", 32))}
    if kind == "vigenere":
        return {"kind": kind, "plaintext": _vigenere_decrypt(problem.get("text"), problem.get("key")),
                "verified": False, "method": "vigenere_known_key"}
    if kind == "rail_fence":
        return {"kind": kind, "plaintext": _rail_fence_decrypt(problem.get("text"), problem.get("rails")),
                "verified": False, "method": "rail_fence_known_rails"}
    if kind == "affine_substitution":
        return {"kind": kind, "plaintext": _affine_decrypt(
            problem.get("text"), problem.get("a"), problem.get("b")),
            "verified": False, "method": "affine_known_parameters"}
    if kind == "finite_csp":
        return _solve_csp(problem)
    raise ValueError("unsupported kind; use text_decode, modular_congruence, linear_system, bitvector_xor or finite_csp")


router = APIRouter(prefix="/api/puzzles", tags=["NEXUS Puzzle Solver"])


class PuzzleSolveRequest(BaseModel):
    problem: dict[str, Any] = Field(...)


@router.get("/capabilities")
def puzzle_capabilities() -> dict[str, Any]:
    return capabilities()


@router.post("/solve")
def puzzle_solve(request: PuzzleSolveRequest) -> dict[str, Any]:
    try:
        return solve(request.problem)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
