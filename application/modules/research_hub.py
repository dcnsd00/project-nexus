"""Private, bounded NEXUS research shortcuts. No external targets or network access."""
from __future__ import annotations
import hashlib, json, time, secrets
from pathlib import Path
from datetime import datetime, timezone
import os
from modules.data_paths import data_path

ROOT = Path(__file__).resolve().parents[1]
HISTORY = Path(os.environ.get("NEXUS_RESEARCH_HUB_DIR", str(data_path("research", "hub", "history")))).expanduser().resolve()

SHORTCUTS = [
 {"id":"sha256_diff","title":"SHA-256 diferențial","category":"Criptanaliză","purpose":"Caută bias-uri statistice în compresia SHA-256 cu runde configurabile.","input":"Runde 1–64; set de probe; poziția diferenței.","output":"Bias, interval de încredere, p ajustat și verdict.","application":"Cercetare și verificare; nu este scurtătură de mining pentru SHA-256 complet.","risk":"Local-only; reduced-round nu este compatibil cu consensul."},
 {"id":"toy_pow","title":"Brute-force PoW de laborator","category":"Căutare exhaustivă","purpose":"Rezolvă un puzzle SHA-256 generat local, cu prefix și dificultate mică, pentru benchmark CPU.","input":"Dificultate 8–20 biți și limită de nonce.","output":"Nonce găsit, încercări, timp și hash/s.","application":"Testează strategii de căutare, paralelizare și performanța CPU; nu atacă adrese sau rețele reale.","risk":"Limită strictă de lucru; țintă generată local."},
 {"id":"toy_collision","title":"Coliziuni hash trunchiat","category":"Căutare exhaustivă","purpose":"Găsește coliziuni într-un spațiu hash artificial de 8–20 biți.","input":"Lățimea hash-ului și bugetul de încercări.","output":"Perechea de mesaje, numărul de încercări și timpul.","application":"Demonstrează efectul birthday paradox și compară structuri de căutare.","risk":"Doar digest trunchiat sintetic; nu caută coliziuni SHA-256 complete."},
 {"id":"hash_bench","title":"Benchmark hash exact","category":"Performanță","purpose":"Compară funcții hash standard pe date locale, fără schimbarea algoritmului.","input":"Algoritm, payload și iterații.","output":"Hash/s, MiB/s și digest de control.","application":"Identifică implementări/runtime-uri mai rapide care păstrează ieșirea exactă."},
 {"id":"mining_ab","title":"Turbo A/B mining","category":"Mining","purpose":"Compară baseline cu un candidat pe măsurători reale de miner și pool.","input":"Hashrate, shares, putere, temperatură și durată.","output":"Delta hashrate, H/W, reject rate și verdict.","application":"Acceptă doar îmbunătățiri repetabile, fără share-uri invalide."},
 {"id":"compatibility","title":"Compatibilitate coin–pool–miner","category":"Mining","purpose":"Verifică algoritm, miner, device, DAG/VRAM și endpoint înainte de START.","input":"Monedă, pool, miner și hardware detectat.","output":"Compatibil / blocat, motive și recomandare.","application":"Previne pornirea configurațiilor imposibile sau incorecte."},
 {"id":"chain_local","title":"Blockchain local / regtest","category":"Blockchain","purpose":"Verifică disponibilitatea mediilor locale de test.","input":"Bitcoin Core regtest, Anvil și Docker instalate local.","output":"Readiness și dependențe lipsă.","application":"Testează tranzacții și contracte în rețele locale, fără fonduri reale."},
 {"id":"phy_challenge_structure","title":"PHY Challenge — structural analyzer","category":"Puzzle research","purpose":"Analizează local metadata publică a puzzle-ului PHY: Unicode 18.0, perechi antipodale candidate, ordini vest-est/radiale și corespondența octeților s din semnătură cu ID-urile emoji.","input":"project_file.json furnizat local; opțional octeții s.","output":"raport structural, perechi candidate, diferențe geometrice și ipoteze explicite.","application":"Cercetare reproductibilă; nu recuperează chei și nu semnează tranzacții.","risk":"Local-only; împerecherea geometrică este ipoteză până la confirmare criptografică."},\n {"id":"schedule","title":"Planificator cercetare","category":"Orchestrare","purpose":"Rulează un set limitat de experimente locale și produce un rezumat executiv.","input":"Pachet de experimente safe și limite de resurse.","output":"Rezultate, verdict, următorul pas și istoric privat.","application":"Automatizează trierea; nu activează optimizări live."}
]

def catalog():
    return {"privacy":"local_only","external_uploads":False,"publication":"manual_only","shortcuts":SHORTCUTS,
            "guardrails":["No wallet/private-key/password brute force.","No third-party targets or public-chain attack automation.","Exhaustive search limited to locally generated toy puzzles.","Reduced-round SHA research is isolated from consensus mining.","No candidate is auto-applied to a miner.","PHY puzzle analysis uses public metadata only; no key, nonce or signature secret search."]}

def _save(kind, result):
    rid=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'_'+secrets.token_hex(5)
    payload={"id":rid,"created_utc":datetime.now(timezone.utc).isoformat(),"kind":kind,"result":result,"privacy":"local_only"}
    HISTORY.mkdir(parents=True, exist_ok=True)
    (HISTORY/f'{rid}.json').write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding='utf-8')
    return payload

def run_toy_pow(bits:int=12,max_attempts:int=2_000_000,prefix:str='NEXUS-LOCAL-LAB'):
    if not 8 <= bits <= 20: raise ValueError('Dificultatea permisă este 8–20 biți.')
    if not 1 <= max_attempts <= 2_000_000: raise ValueError('Bugetul este 1–2.000.000 încercări.')
    if not isinstance(prefix,str) or not 1 <= len(prefix) <= 64: raise ValueError('Prefix local invalid.')
    target='0'*(bits//4) + ('0' if bits%4 else '')
    mask=(1<<bits)-1; start=time.perf_counter(); found=None
    for nonce in range(max_attempts):
        digest=hashlib.sha256(f'{prefix}:{nonce}'.encode()).digest()
        if int.from_bytes(digest[:4],'big') >> (32-bits) == 0:
            found={"nonce":nonce,"digest":digest.hex()}; break
    elapsed=max(time.perf_counter()-start,1e-9)
    return _save('toy_pow',{"difficulty_bits":bits,"prefix":prefix,"target_prefix_hex":target,"attempts":(found['nonce']+1 if found else max_attempts),"elapsed_seconds":elapsed,"hashes_per_second":(found['nonce']+1 if found else max_attempts)/elapsed,"found":found,"scope":"locally generated toy proof-of-work; not a real coin or network"})

def run_toy_collision(bits:int=16,max_attempts:int=200_000):
    if not 8 <= bits <= 20: raise ValueError('Lățimea permisă este 8–20 biți.')
    if not 1 <= max_attempts <= 500_000: raise ValueError('Bugetul este 1–500.000 încercări.')
    seen={}; start=time.perf_counter(); collision=None; mask=(1<<bits)-1
    for i in range(max_attempts):
        msg=f'NEXUS-COLLISION-LAB:{i}'.encode(); value=int.from_bytes(hashlib.sha256(msg).digest()[:4],'big') & mask
        if value in seen:
            collision={"message_a":seen[value],"message_b":i,"truncated_digest_hex":format(value,f'0{(bits+3)//4}x')}; break
        seen[value]=i
    elapsed=max(time.perf_counter()-start,1e-9)
    return _save('toy_collision',{"digest_bits":bits,"attempts":(i+1),"elapsed_seconds":elapsed,"messages_per_second":(i+1)/elapsed,"collision":collision,"scope":"synthetic truncated digest; not a full SHA-256 collision"})

def history(limit=30):
    rows=[]
    if not HISTORY.is_dir():
        return {"count": 0, "items": [], "privacy": "local_only"}
    for p in sorted(HISTORY.glob('*.json'),key=lambda x:x.stat().st_mtime,reverse=True)[:max(1,min(int(limit),100))]:
        try: rows.append(json.loads(p.read_text(encoding='utf-8')))
        except Exception: pass
    return {"count":len(rows),"items":rows,"privacy":"local_only"}

def executive_summary():
    h=history(100)['items']; counts={}
    for x in h: counts[x['kind']]=counts.get(x['kind'],0)+1
    return {"experiments_saved":len(h),"by_type":counts,"latest":h[0] if h else None,
            "recommendation":"Rulează întâi puzzle PoW local și coliziuni trunchiate pentru a verifica pipeline-ul de căutare; apoi SHA diferențial și benchmark exact. Nicio optimizare nu se aplică automat la mining.",
            "private":True}
