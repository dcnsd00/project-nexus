"""NEXUS Math Intelligence: exact hash benchmarks, safe modular solver and candidate triage.
All experiments are local; no wallet/key search or public-chain attack functionality.
"""
from __future__ import annotations
import hashlib, math, secrets, time
from typing import Any
from modules.crypto_engine.engine import CryptoEngine

ENGINE = CryptoEngine()

ALGORITHMS = ["sha256", "sha512", "sha3_256", "sha3_512", "blake2b_256", "blake2s_256", "sha256d"]

def hash_benchmark(algorithms: list[str] | None = None, payload_bytes: int = 1024, iterations: int = 2000) -> dict[str, Any]:
    if not 0 <= payload_bytes <= 1_048_576: raise ValueError("Payloadul trebuie să fie între 0 și 1 MiB.")
    if not 10 <= iterations <= 200_000: raise ValueError("Iterațiile trebuie să fie între 10 și 200000.")
    names = algorithms or ALGORITHMS
    if len(names) > 12: raise ValueError("Maximum 12 algoritmi per benchmark.")
    rows=[]
    for name in names:
        started=time.perf_counter()
        result=ENGINE.benchmark(name, payload_bytes, iterations)
        rows.append(result)
    rows.sort(key=lambda x:x["hashes_per_second"], reverse=True)
    return {"kind":"exact_hash_benchmark", "payload_bytes":payload_bytes,"iterations":iterations,
            "results":rows,"interpretation":"Compară throughput-ul implementărilor locale pe același payload. Nu reprezintă hashrate PoW și nu implică compatibilitate de consens.","private":True}


def solve_modular_congruence(a: int, b: int, modulus: int) -> dict[str, Any]:
    """Solve a*x = b (mod m), returning compact solution class."""
    if any(isinstance(x,bool) or not isinstance(x,int) for x in (a,b,modulus)):
        raise ValueError("Parametrii trebuie să fie întregi.")
    if not 2 <= modulus <= 10**18: raise ValueError("Modulul trebuie să fie între 2 și 10^18.")
    a%=modulus; b%=modulus; g=math.gcd(a,modulus)
    if b%g:
        return {"solvable":False,"gcd":g,"modulus":modulus,"explanation":"Nu există soluții: gcd(a,m) nu divide b."}
    reduced_m=modulus//g
    x0=(pow(a//g,-1,reduced_m)*(b//g))%reduced_m if reduced_m>1 else 0
    return {"solvable":True,"gcd":g,"one_solution":x0,"solution_count":g,
            "solution_class":f"x = {x0} (mod {reduced_m})", "modulus":modulus,
            "verification":(a*x0-b)%modulus==0,
            "explanation":f"Există {g} soluții modulo {modulus}; clasa este verificată exact."}


def triage_candidate(data: dict[str, Any]) -> dict[str, Any]:
    """Classify measured optimization; no automatic miner activation."""
    if not isinstance(data, dict):
        raise ValueError("Datele candidatului trebuie să fie un obiect.")

    baseline_raw = data.get("baseline_hashrate", 0)
    candidate_raw = data.get("candidate_hashrate", 0)
    for name, value in (("baseline_hashrate", baseline_raw), ("candidate_hashrate", candidate_raw)):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{name} trebuie să fie un număr finit.")
        try:
            finite = math.isfinite(float(value))
        except (OverflowError, ValueError):
            finite = False
        if not finite:
            raise ValueError(f"{name} trebuie să fie un număr finit.")
    baseline = float(baseline_raw)
    candidate = float(candidate_raw)
    if baseline <= 0 or candidate < 0:
        raise ValueError("Hashrate baseline trebuie >0, candidat >=0.")

    integer_fields = ("duration_seconds", "accepted_shares", "rejected_shares", "independent_runs")
    counts: dict[str, int] = {}
    for name in integer_fields:
        value = data.get(name, 0)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{name} trebuie să fie un întreg nenegativ.")
        counts[name] = value

    exact_raw = data.get("exact_equivalence_verified", False)
    if not isinstance(exact_raw, bool):
        raise ValueError("exact_equivalence_verified trebuie să fie boolean.")
    duration = counts["duration_seconds"]
    accepted = counts["accepted_shares"]
    rejected = counts["rejected_shares"]
    exact = exact_raw
    independent = counts["independent_runs"]
    delta = (candidate / baseline - 1) * 100
    if not math.isfinite(delta):
        raise ValueError("Raportul hash rate produce o variație numerică nefinita.")
    reject_rate = rejected / (accepted + rejected) if accepted + rejected else None
    valid = exact and independent >= 3 and duration >= 180 and accepted > 0 and (reject_rate is not None and reject_rate <= 0.01)
    if not exact: verdict="RESEARCH_ONLY"
    elif not valid: verdict="NEEDS_MORE_EVIDENCE"
    elif delta>1: verdict="PROMISING_MEASURED_GAIN"
    else: verdict="NO_MEANINGFUL_GAIN"
    return {"verdict":verdict,"hashrate_delta_percent":round(delta,3),"reject_rate":reject_rate,
            "exact_equivalence_verified":exact,"independent_runs":independent,"duration_seconds":duration,
            "eligible_for_manual_review":valid and delta>1,"auto_apply":False,
            "plain_language":("Candidat promițător pentru revizie manuală; nu este activat automat." if verdict=="PROMISING_MEASURED_GAIN" else
              "Nu există încă dovezi suficiente pentru aplicare." if verdict=="NEEDS_MORE_EVIDENCE" else
              "Cercetare izolată: echivalența exactă nu este demonstrată." if verdict=="RESEARCH_ONLY" else
              "Nu s-a măsurat un câștig relevant.")}


def research_catalog() -> dict[str, Any]:
    return {"private_local":True,"publication":"manual_only","shortcuts":[
      {"id":"sha256_research","title":"SHA-256 diferențial și carry","purpose":"Caută bias-uri în variante reduced-round; verifică separat SHA-256 complet.","use":"Cercetare criptanalitică; nu se injectează în miner."},
      {"id":"sha512_exact","title":"SHA-512 / SHA-3 exact","purpose":"Benchmark și teste de avalanșă asupra funcțiilor standard complete.","use":"Alege implementări/runtime-uri mai rapide cu digest identic."},
      {"id":"modular_solver","title":"Solver modular","purpose":"Rezolvă congruențe liniare și validează soluțiile exact.","use":"Prototipuri matematice și verificarea constrângerilor."},
      {"id":"candidate_triage","title":"Evaluator Turbo","purpose":"Compară baseline/candidat și cere dovezi independente.","use":"Promovează numai candidați măsurați; fără auto-activare."},
      {"id":"pool_rewards","title":"Pool & rewards","purpose":"Citește read-only statisticile contului și recompensele suportate.","use":"Evidență separată pentru sold, imature și plăți."},
      {"id":"chain_readiness","title":"Blockchain local","purpose":"Verifică Bitcoin regtest, Anvil și Docker.","use":"Teste tranzacții/contracte doar în medii locale."}
    ],"guardrails":["No secret/key brute-force","No third-party wallet or account attacks","No automatic public-chain transactions","No reduced-round digest injection into mining","No automatic application of optimization candidates"]}
