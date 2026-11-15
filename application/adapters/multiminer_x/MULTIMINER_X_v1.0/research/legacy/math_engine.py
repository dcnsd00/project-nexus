
"""NEXUS deterministic mathematics and data-decoding engine.

Expression parsing uses a strict Python AST allow-list. No eval/exec is used.
"""
import ast, base64, binascii, hashlib, json, math, operator, re, urllib.parse, zlib
from fractions import Fraction
from typing import Any
import sympy as sp
from sympy.parsing.sympy_parser import parse_expr, standard_transformations, implicit_multiplication_application, convert_xor

TRANSFORMS = standard_transformations + (implicit_multiplication_application, convert_xor)
FUNCS = {
    "sqrt": sp.sqrt, "sin": sp.sin, "cos": sp.cos, "tan": sp.tan,
    "asin": sp.asin, "acos": sp.acos, "atan": sp.atan,
    "sinh": sp.sinh, "cosh": sp.cosh, "tanh": sp.tanh,
    "log": sp.log, "ln": sp.log, "exp": sp.exp, "abs": sp.Abs,
    "factorial": sp.factorial, "gamma": sp.gamma, "erf": sp.erf,
    "floor": sp.floor, "ceil": sp.ceiling, "Min": sp.Min, "Max": sp.Max,
}
CONSTS = {"pi": sp.pi, "e": sp.E, "I": sp.I, "oo": sp.oo}
_ALLOWED_AST=(ast.Expression,ast.BinOp,ast.UnaryOp,ast.Constant,ast.Name,ast.Load,
 ast.Add,ast.Sub,ast.Mult,ast.Div,ast.Pow,ast.Mod,ast.USub,ast.UAdd,
 ast.Call,ast.Tuple,ast.List)
def _check_ast(node):
    for n in ast.walk(node):
        if not isinstance(n,_ALLOWED_AST): raise ValueError(f"Operator/syntax not allowed: {type(n).__name__}")
        if isinstance(n,ast.Constant) and not isinstance(n.value,(int,float,complex)): raise ValueError("Only numeric constants are allowed")
        if isinstance(n,ast.Name) and n.id not in FUNCS and n.id not in CONSTS and not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,20}",n.id): raise ValueError("Invalid symbol")
        if isinstance(n,ast.Call) and (not isinstance(n.func,ast.Name) or n.func.id not in FUNCS): raise ValueError("Only approved mathematical functions may be called")
def expression(src:str):
    if not isinstance(src,str) or not src.strip() or len(src)>1000: raise ValueError("Expression must be 1–1000 characters")
    tree=ast.parse(src.replace("^","**"),mode="eval"); _check_ast(tree)
    names={n.id for n in ast.walk(tree) if isinstance(n,ast.Name)}
    local={**FUNCS,**CONSTS}
    for name in names:
        if name not in local: local[name]=sp.Symbol(name)
    # Safe after strict AST validation; SymPy parser receives only approved names and syntax.
    return parse_expr(src,local_dict=local,global_dict={"Symbol":sp.Symbol,"Integer":sp.Integer,"Float":sp.Float,"Rational":sp.Rational,"Function":sp.Function,"factorial":sp.factorial,"sqrt":sp.sqrt}, transformations=TRANSFORMS, evaluate=True)

def compute(payload:dict):
    op=payload.get("operation","simplify")
    expr=expression(payload.get("expression",""))
    var=sp.Symbol(payload.get("variable","x"))
    if op=="simplify": out=sp.simplify(expr)
    elif op=="factor": out=sp.factor(expr)
    elif op=="expand": out=sp.expand(expr)
    elif op=="differentiate": out=sp.diff(expr,var,int(payload.get("order",1)))
    elif op=="integrate": out=sp.integrate(expr,var)
    elif op=="limit": out=sp.limit(expr,var,expression(str(payload.get("point","0"))))
    elif op=="solve": out=sp.solve(sp.Eq(expr,0),var)
    elif op=="series": out=sp.series(expr,var,0,int(payload.get("order",8)))
    elif op=="numeric": out=sp.N(expr,int(payload.get("precision",30)))
    elif op=="verify_identity":
        rhs=expression(payload.get("rhs","0")); diff=sp.simplify(expr-rhs)
        return {"verified":diff==0,"difference":str(diff),"method":"symbolic simplification"}
    else: raise ValueError("Unknown symbolic operation")
    return {"result":str(out),"latex":sp.latex(out),"exact":True,"engine":"SymPy"}

def matrix(payload):
    raw=payload.get("matrix")
    if not isinstance(raw,list) or not raw or len(raw)>30: raise ValueError("Matrix must be a non-empty 2D list (max 30 rows)")
    M=sp.Matrix(raw)
    op=payload.get("operation","determinant")
    if op=="determinant": val=M.det()
    elif op=="rank": val=M.rank()
    elif op=="rref": val=M.rref()[0]
    elif op=="inverse": val=M.inv()
    elif op=="transpose": val=M.T
    elif op=="eigenvalues": val=M.eigenvals()
    elif op=="charpoly": val=M.charpoly().as_expr()
    elif op=="nullspace": val=M.nullspace()
    elif op=="solve":
        b=sp.Matrix(payload.get("vector",[])); val=sp.linsolve((M,b))
    else: raise ValueError("Unknown matrix operation")
    return {"result":str(val),"shape":list(M.shape),"rank":M.rank(),"engine":"SymPy"}

def probability(payload):
    op=payload.get("operation","binomial")
    if op=="binomial":
        n=int(payload["n"]); k=int(payload["k"]); p=sp.Rational(str(payload["p"]))
        if n<0 or k<0 or k>n or p<0 or p>1: raise ValueError("Require n≥0, 0≤k≤n and 0≤p≤1")
        v=sp.binomial(n,k)*p**k*(1-p)**(n-k)
    elif op=="permutation": v=sp.factorial(int(payload["n"]))//sp.factorial(int(payload["n"])-int(payload["r"]))
    elif op=="combination": v=sp.binomial(int(payload["n"]),int(payload["r"]))
    elif op=="bayes":
        prior=sp.Rational(str(payload["prior"])); sens=sp.Rational(str(payload["sensitivity"])); spec=sp.Rational(str(payload["specificity"]))
        v=prior*sens/(prior*sens+(1-prior)*(1-spec))
    else: raise ValueError("Unknown probability operation")
    return {"exact":str(v),"decimal":str(sp.N(v,18)),"engine":"SymPy"}

def number_theory(payload):
    op=payload.get("operation","factorint"); n=int(payload["n"])
    if abs(n)>10**100: raise ValueError("Integer magnitude limited to 100 digits per request")
    if op=="factorint": result=sp.factorint(n)
    elif op=="isprime": result=bool(sp.isprime(n))
    elif op=="nextprime": result=sp.nextprime(n)
    elif op=="prevprime": result=sp.prevprime(n)
    elif op=="totient": result=sp.totient(n)
    elif op=="mobius": result=sp.mobius(n)
    elif op=="gcd": result=math.gcd(n,int(payload["b"]))
    elif op=="lcm": result=math.lcm(n,int(payload["b"]))
    elif op=="mod_inverse": result=sp.mod_inverse(n,int(payload["modulus"]))
    elif op=="discrete_log": result=sp.discrete_log(int(payload["modulus"]),int(payload["target"]),int(payload["base"]))
    else: raise ValueError("Unknown number theory operation")
    return {"result":str(result),"engine":"SymPy"}

def optimize(payload):
    # Deterministic symbolic derivative + stationary points; no arbitrary objective code.
    f=expression(payload.get("expression",""))
    x=sp.Symbol(payload.get("variable","x"))
    d=sp.diff(f,x)
    points=sp.solve(sp.Eq(d,0),x)
    rows=[]
    for p in points:
        try:
            second=sp.diff(f,x,2).subs(x,p)
            kind="minimum" if second.is_positive else ("maximum" if second.is_negative else "inconclusive")
            rows.append({"x":str(p),"value":str(sp.simplify(f.subs(x,p))),"second_derivative":str(second),"classification":kind})
        except Exception: rows.append({"x":str(p),"classification":"inconclusive"})
    return {"derivative":str(d),"stationary_points":rows,"note":"Local stationary-point analysis; not a proof of global optimum."}

def decode(payload):
    data=str(payload.get("data",""))
    if len(data)>200000: raise ValueError("Input exceeds 200 KB")
    kind=payload.get("format","auto")
    out={}
    if kind in ("auto","base64"):
        try:
            raw=base64.b64decode(data,validate=True); out["base64_utf8"]=raw.decode("utf-8")
        except Exception:
            if kind=="base64": raise ValueError("Invalid Base64 or decoded data is not UTF-8")
    if kind in ("auto","hex"):
        try:
            raw=bytes.fromhex(data); out["hex_utf8"]=raw.decode("utf-8")
        except Exception:
            if kind=="hex": raise ValueError("Invalid hex or decoded data is not UTF-8")
    if kind in ("auto","url"): out["url_decoded"]=urllib.parse.unquote(data)
    if kind in ("auto","json"):
        try: out["json_pretty"]=json.dumps(json.loads(data),ensure_ascii=False,indent=2)
        except Exception:
            if kind=="json": raise ValueError("Invalid JSON")
    if kind in ("auto","gzip"):
        try: out["gzip_utf8"]=zlib.decompress(base64.b64decode(data),wbits=31).decode("utf-8")
        except Exception:
            if kind=="gzip": raise ValueError("Invalid Base64-GZIP input")
    # Fingerprints identify formats; hashes are one-way and are not decrypted.
    if re.fullmatch(r"[0-9a-fA-F]{32}",data): out["hash_hint"]="32 hex characters: possible MD5 digest; not reversible"
    elif re.fullmatch(r"[0-9a-fA-F]{40}",data): out["hash_hint"]="40 hex characters: possible SHA-1 digest; not reversible"
    elif re.fullmatch(r"[0-9a-fA-F]{64}",data): out["hash_hint"]="64 hex characters: possible SHA-256 digest; not reversible"
    elif re.fullmatch(r"[0-9a-fA-F]{128}",data): out["hash_hint"]="128 hex characters: possible SHA-512 digest; not reversible"
    if not out: out["notice"]="No supported encoding detected. This tool does not break encryption."
    return out

def sage_status():
    import os, shutil
    exe=os.getenv("SAGE_EXECUTABLE") or shutil.which("sage")
    return {"available":bool(exe),"executable":exe or None,"mode":"structured local adapter only","note":"SageMath is optional and must be installed separately. Arbitrary Sage/Python code execution is disabled."}


def sage_compute(payload:dict):
    """Optional SageMath CLI adapter for narrowly scoped, structured operations."""
    import os, shutil, subprocess
    exe=os.getenv("SAGE_EXECUTABLE") or shutil.which("sage")
    if not exe: raise RuntimeError("SageMath executable not found. Install SageMath and set SAGE_EXECUTABLE.")
    op=payload.get("operation")
    if op=="factor_integer":
        n=int(payload["n"])
        if abs(n)>10**100: raise ValueError("Integer magnitude limited to 100 digits")
        script=f"print(factor({n}))"
    elif op=="matrix_determinant":
        raw=payload.get("matrix")
        if not isinstance(raw,list) or not raw or len(raw)>20: raise ValueError("Matrix size must be 1–20")
        M=sp.Matrix(raw)
        if not all(v.is_Integer for v in M): raise ValueError("Sage adapter currently accepts integer matrices only")
        rows=[[int(v) for v in row] for row in M.tolist()]
        script=f"print(matrix(ZZ,{rows!r}).det())"
    else: raise ValueError("Supported Sage operations: factor_integer, matrix_determinant")
    try:
        cp=subprocess.run([exe,"-c",script],capture_output=True,text=True,timeout=20,check=True)
        return {"result":cp.stdout.strip(),"engine":"SageMath","stderr":cp.stderr[:500]}
    except subprocess.TimeoutExpired: raise RuntimeError("SageMath operation exceeded 20-second limit")
