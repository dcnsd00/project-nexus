"""NEXUS hybrid mathematics router: exact native arithmetic + SymPy + optional Z3.

Only solves bounded user-supplied mathematical constraints. No key/wallet search.
"""
from __future__ import annotations
import math
from typing import Any

MAX_MATRIX = 20
MAX_COEFFICIENT = 10**12


def capabilities() -> dict[str, Any]:
    try:
        import sympy  # noqa: F401
        sympy_available = True
    except Exception:
        sympy_available = False
    try:
        import z3  # noqa: F401
        z3_available = True
    except Exception:
        z3_available = False
    try:
        from pysat.solvers import Glucose4  # noqa: F401
        pysat_available = True
    except Exception:
        pysat_available = False
    return {
        "router": "NEXUS Hybrid Solver Router",
        "backends": {
            "native_exact": {"available": True, "tasks": ["modular_congruence", "integer_checks"]},
            "sympy": {"available": sympy_available, "tasks": ["linear_system_exact_rational"]},
            "z3_smt": {"available": z3_available, "tasks": ["bounded_bitvector_xor"]},
            "pysat": {"available": pysat_available, "tasks": ["reduced_round_sha256_sat_existing_module"]},
        },
        "policy": "Backend selected by problem type; every returned model is independently verified where possible; no auto-application to miners.",
    }


def solve_modular(a: int, b: int, modulus: int) -> dict[str, Any]:
    if any(isinstance(v, bool) or not isinstance(v, int) for v in (a, b, modulus)):
        raise ValueError("a, b și modulus trebuie să fie întregi.")
    if not 2 <= modulus <= 10**18:
        raise ValueError("Modulul trebuie să fie între 2 și 10^18.")
    aa, bb = a % modulus, b % modulus
    g = math.gcd(aa, modulus)
    if bb % g:
        return {"solvable": False, "backend": "native_exact", "gcd": g, "modulus": modulus,
                "verified": True, "explanation": "Nu există soluții: gcd(a,m) nu divide b."}
    reduced = modulus // g
    x0 = (pow(aa // g, -1, reduced) * (bb // g)) % reduced if reduced > 1 else 0
    verified = (aa * x0 - bb) % modulus == 0
    result = {"solvable": verified, "backend": "native_exact", "gcd": g,
              "one_solution": x0, "solution_count": g,
              "solution_class": f"x = {x0} (mod {reduced})", "modulus": modulus,
              "verified": verified}
    try:
        import sympy as sp
        check = sp.gcd(aa, modulus) == g
        result["sympy_cross_check"] = bool(check)
        result["backends_used"] = ["native_exact", "sympy"]
    except Exception:
        result["sympy_cross_check"] = None
        result["backends_used"] = ["native_exact"]
    result["explanation"] = f"Există {g} soluții modulo {modulus}; reprezentantul minim a fost verificat prin substituție."
    return result


def solve_linear_system(matrix: list[list[int | float | str]], rhs: list[int | float | str]) -> dict[str, Any]:
    if not isinstance(matrix, list) or not matrix or len(matrix) > MAX_MATRIX:
        raise ValueError(f"Matricea trebuie să aibă între 1 și {MAX_MATRIX} rânduri.")
    if not isinstance(rhs, list) or len(rhs) != len(matrix):
        raise ValueError("Vectorul rhs trebuie să aibă același număr de elemente ca matricea.")
    cols = len(matrix[0]) if isinstance(matrix[0], list) else 0
    if not 1 <= cols <= MAX_MATRIX or any(not isinstance(row, list) or len(row) != cols for row in matrix):
        raise ValueError(f"Matricea trebuie să fie rectangulară, cu maximum {MAX_MATRIX} coloane.")
    try:
        import sympy as sp
    except Exception as exc:
        raise RuntimeError("SymPy nu este instalat. Instalează dependențele de bază NEXUS.") from exc
    try:
        A = sp.Matrix([[sp.Rational(v) for v in row] for row in matrix])
        b = sp.Matrix([sp.Rational(v) for v in rhs])
    except Exception as exc:
        raise ValueError(f"Coeficient invalid: {exc}") from exc
    for val in list(A) + list(b):
        if abs(int(val.p)) > MAX_COEFFICIENT or abs(int(val.q)) > MAX_COEFFICIENT:
            raise ValueError("Coeficient prea mare pentru acest solver (limită 10^12 pentru numărător și numitor).")
    if A.rows != A.cols:
        raise ValueError("Această operație acceptă doar sisteme pătrate pentru soluție unică.")
    if A.det() == 0:
        return {"solvable": False, "backend": "sympy", "rank": int(A.rank()),
                "verified": True, "explanation": "Sistem singular; nu există o soluție unică. Folosește o parametrizare separată pentru sisteme subdeterminate."}
    sol = A.inv() * b
    check = A * sol == b
    return {"solvable": True, "backend": "sympy_exact_rational", "solution": [str(v) for v in sol],
            "rank": int(A.rank()), "determinant": str(A.det()), "verified": bool(check),
            "explanation": "Sistem rezolvat exact în numere raționale și verificat prin substituție."}


def solve_bitvector_xor(variable_names: list[str], target: int, width: int = 32) -> dict[str, Any]:
    if not isinstance(variable_names, list) or not 2 <= len(variable_names) <= 8:
        raise ValueError("Sunt necesare între 2 și 8 variabile.")
    if len(set(variable_names)) != len(variable_names) or any(not isinstance(n, str) or not n.isidentifier() or len(n) > 24 for n in variable_names):
        raise ValueError("Numele variabilelor trebuie să fie identificatori unici simpli.")
    if isinstance(width, bool) or not isinstance(width, int) or not 1 <= width <= 64:
        raise ValueError("Lățimea bitvector trebuie să fie între 1 și 64.")
    if isinstance(target, bool) or not isinstance(target, int) or not 0 <= target < (1 << width):
        raise ValueError("Ținta XOR nu încape în lățimea aleasă.")
    # Exact native constructive solver: for an unconstrained XOR equation,
    # any assignment is valid as long as the XOR equals target. Set all but
    # the final variable to zero and the final variable to target. This avoids
    # making a simple, fully-solvable problem depend on optional Z3.
    mask = (1 << width) - 1
    values = {name: 0 for name in variable_names}
    values[variable_names[-1]] = target & mask
    check = 0
    for val in values.values():
        check ^= val
    verified = check == target
    result = {"solvable": verified, "backend": "native_exact_xor", "status": "SAT" if verified else "ERROR",
              "width": width, "target": target, "solution": values, "verified": verified,
              "explanation": "Soluție constructivă exactă: variabilele libere sunt zero, ultima variabilă primește ținta; XOR verificat independent."}
    # If Z3 happens to be installed, use it as an independent cross-check,
    # never as a runtime requirement for this unconstrained equation.
    try:
        import z3
        zvars = {name: z3.BitVec(name, width) for name in variable_names}
        expr = zvars[variable_names[0]]
        for name in variable_names[1:]:
            expr = expr ^ zvars[name]
        solver = z3.Solver()
        solver.set(timeout=5000)
        solver.add(expr == z3.BitVecVal(target, width))
        status = solver.check()
        result["z3_cross_check"] = str(status)
        result["backends_used"] = ["native_exact_xor", "z3_smt"]
    except Exception:
        result["z3_cross_check"] = None
        result["backends_used"] = ["native_exact_xor"]
    return result


def solve(problem: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(problem, dict):
        raise ValueError("Problema trebuie să fie un obiect.")
    kind = problem.get("kind")
    started = __import__("time").perf_counter()
    if kind == "modular_congruence":
        result = solve_modular(problem.get("a"), problem.get("b"), problem.get("modulus"))
    elif kind == "linear_system":
        result = solve_linear_system(problem.get("matrix"), problem.get("rhs"))
    elif kind == "bitvector_xor":
        result = solve_bitvector_xor(problem.get("variables"), problem.get("target"), problem.get("width", 32))
    else:
        raise ValueError("Tip necunoscut. Tipuri acceptate: modular_congruence, linear_system, bitvector_xor.")
    result["elapsed_ms"] = round((__import__("time").perf_counter() - started) * 1000, 3)
    result["private_local"] = True
    result["auto_apply"] = False
    return result
