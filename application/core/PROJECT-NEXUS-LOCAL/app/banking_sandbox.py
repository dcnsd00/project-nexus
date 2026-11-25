
from decimal import Decimal
import hashlib, json
ACCOUNTS=[{"id":"SIM-CHECKING-001","opening":"2500.00"},{"id":"SIM-SAVINGS-001","opening":"8500.00"},{"id":"SIM-CARD-001","opening":"0.00"}]
TX=[("SIM-CHECKING-001","credit","3200.00"),("SIM-CHECKING-001","debit","780.00"),("SIM-CHECKING-001","debit","145.50"),("SIM-CARD-001","debit","89.90"),("SIM-CHECKING-001","credit","250.00")]
def dec(x): return Decimal(str(x)).quantize(Decimal("0.01"))
def ledger():
 b={a["id"]:dec(a["opening"]) for a in ACCOUNTS}; rows=[]
 for i,(acc,direction,amount) in enumerate(TX,1):
  v=dec(amount); b[acc]+=v if direction=="credit" else -v
  rows.append({"id":f"SIM-TX-{i:04}","account":acc,"direction":direction,"amount":str(v),"counterparty":"Synthetic Demo"})
 return {"environment":"SYNTHETIC_BANK_SANDBOX","live_bank_connected":False,"accounts":[{**a,"balance":str(b[a["id"]])} for a in ACCOUNTS],"transactions":rows,"warning":"Fictitious data only."}
def analyze():
 d=ledger(); inc=sum((dec(t["amount"]) for t in d["transactions"] if t["direction"]=="credit"),Decimal(0)); out=sum((dec(t["amount"]) for t in d["transactions"] if t["direction"]=="debit"),Decimal(0))
 return {"inflows":str(inc),"outflows":str(out),"net_cashflow":str(inc-out),"transaction_count":len(d["transactions"])}
def tests():
 d=ledger(); a=analyze(); cases=[]
 def ck(n,ok,e,g): cases.append({"test":n,"passed":bool(ok),"expected":str(e),"actual":str(g)})
 ck("synthetic isolation",d["live_bank_connected"] is False,False,d["live_bank_connected"])
 ck("three demo accounts",len(d["accounts"])==3,3,len(d["accounts"]))
 ck("cashflow arithmetic",a["net_cashflow"]=="2434.60","2434.60",a["net_cashflow"])
 ids={x["id"] for x in d["accounts"]}
 ck("valid transaction account references",all(t["account"] in ids for t in d["transactions"]),True,True)
 ck("positive amounts",all(dec(t["amount"])>0 for t in d["transactions"]),True,True)
 digest=lambda x:hashlib.sha256(json.dumps(x,sort_keys=True).encode()).hexdigest()
 ck("deterministic replay",digest(analyze())==digest(analyze()),True,True)
 return {"suite":"NEXUS synthetic banking sandbox","total":len(cases),"passed":sum(x["passed"] for x in cases),"failed":sum(not x["passed"] for x in cases),"cases":cases,"live_bank_access":False}
