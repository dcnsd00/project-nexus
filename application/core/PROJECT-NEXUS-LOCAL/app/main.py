
import os, sqlite3
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
import httpx
from . import math_engine, banking_sandbox, plugin_registry

DB=os.getenv("NEXUS_DB","./data/nexus.db")
def conn():
    p=Path(DB); p.parent.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c
def audit(event,details=""):
    with conn() as c: c.execute("INSERT INTO audit(event,details) VALUES(?,?)",(event,details)); c.commit()
def init():
    with conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY,title TEXT,description TEXT,domain TEXT,priority TEXT,status TEXT DEFAULT 'open',created TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS notes(id INTEGER PRIMARY KEY,title TEXT,body TEXT,tags TEXT,created TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS agents(id TEXT PRIMARY KEY,name TEXT,purpose TEXT,enabled INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS approvals(id INTEGER PRIMARY KEY,action TEXT,target TEXT,details TEXT,status TEXT DEFAULT 'pending',created TEXT DEFAULT CURRENT_TIMESTAMP,decided TEXT);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,event TEXT,details TEXT,created TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS chat(id INTEGER PRIMARY KEY,role TEXT,content TEXT,domain TEXT,created TEXT DEFAULT CURRENT_TIMESTAMP);
        """)
        agents=[("core","NEXUS Core","Coordinates owner-approved workflows"),("research","Research","Evidence review"),("developer","Developer","Writes and reviews software"),("crypto","Crypto","Blockchain analysis"),("depin","DePIN","Node and reward integrations"),("mining","Mining","Benchmarks and cost analysis"),("security","Security","Threat and permission review"),("knowledge","Knowledge","Persistent project memory")]
        for a in agents:c.execute("INSERT OR IGNORE INTO agents(id,name,purpose) VALUES(?,?,?)",a)
        c.commit()
@asynccontextmanager
async def lifespan(app):
    init(); audit("system.start","NEXUS started"); yield
app=FastAPI(title="PROJECT NEXUS",version="0.5.0",lifespan=lifespan)
class Task(BaseModel):
    title:str=Field(min_length=1,max_length=180); description:str=""; domain:str="core"; priority:str="normal"
class Note(BaseModel):
    title:str=Field(min_length=1,max_length=180); body:str; tags:str=""
class Approval(BaseModel):
    action:str; target:str; details:str=""
class Chat(BaseModel):
    message:str=Field(min_length=1,max_length=12000); domain:str="core"


@app.get("/api/plugins")
def plugin_list():
    return plugin_registry.list_plugins()
@app.get("/api/banking/sandbox")
def banking_data():
    return banking_sandbox.ledger()
@app.get("/api/banking/analysis")
def banking_analysis():
    return banking_sandbox.analyze()
@app.post("/api/banking/simulate")
def banking_simulate():
    result=banking_sandbox.tests()
    audit("banking.simulation",f"passed={result['passed']};failed={result['failed']}")
    return result
@app.get("/api/math/status")
def math_status():
    return {"sympy_version":__import__("sympy").__version__,"sage":math_engine.sage_status()}
@app.post("/api/math/{kind}")
def math_api(kind:str,payload:dict):
    handlers={"sage":math_engine.sage_compute,"compute":math_engine.compute,"matrix":math_engine.matrix,"probability":math_engine.probability,"number-theory":math_engine.number_theory,"optimize":math_engine.optimize,"decode":math_engine.decode}
    if kind not in handlers: raise HTTPException(404,"Unknown math endpoint")
    try:
        result=handlers[kind](payload); audit("math."+kind,str(payload)[:180]); return result
    except Exception as e: raise HTTPException(400,"Math error: "+str(e)[:300])
@app.get("/",response_class=HTMLResponse)
def index(): return PAGE
@app.get("/api/health")
def health(): return {"status":"ok","version":"0.5.0","ai_configured":bool(os.getenv("OPENAI_API_KEY")),"mode":"local-first","execution":"manual-approval"}
@app.get("/api/summary")
def summary():
    with conn() as c:
        return {"tasks":{r["status"]:r["n"] for r in c.execute("SELECT status,count(*) n FROM tasks GROUP BY status")},"notes":c.execute("SELECT count(*) FROM notes").fetchone()[0],"pending":c.execute("SELECT count(*) FROM approvals WHERE status='pending'").fetchone()[0],"agents":c.execute("SELECT count(*) FROM agents WHERE enabled=1").fetchone()[0]}
@app.get("/api/tasks")
def tasks():
    with conn() as c:return [dict(x) for x in c.execute("SELECT * FROM tasks ORDER BY id DESC")]
@app.post("/api/tasks")
def add_task(x:Task):
    with conn() as c:cur=c.execute("INSERT INTO tasks(title,description,domain,priority) VALUES(?,?,?,?)",(x.title,x.description,x.domain,x.priority));c.commit()
    audit("task.created",str(cur.lastrowid));return {"id":cur.lastrowid}
@app.patch("/api/tasks/{i}")
def update_task(i:int,status:str):
    if status not in ["open","in_progress","blocked","done","cancelled"]:raise HTTPException(400,"Invalid status")
    with conn() as c:cur=c.execute("UPDATE tasks SET status=? WHERE id=?",(status,i));c.commit()
    if not cur.rowcount:raise HTTPException(404,"Task not found")
    audit("task.updated",f"{i}:{status}");return {"ok":True}
@app.delete("/api/tasks/{i}")
def remove_task(i:int):
    with conn() as c:cur=c.execute("DELETE FROM tasks WHERE id=?",(i,));c.commit()
    if not cur.rowcount:raise HTTPException(404,"Task not found")
    audit("task.deleted",str(i));return {"ok":True}
@app.get("/api/notes")
def notes(q:str=""):
    with conn() as c:return [dict(x) for x in c.execute("SELECT * FROM notes WHERE title LIKE ? OR body LIKE ? OR tags LIKE ? ORDER BY id DESC",(f"%{q}%",)*3)]
@app.post("/api/notes")
def add_note(x:Note):
    with conn() as c:cur=c.execute("INSERT INTO notes(title,body,tags) VALUES(?,?,?)",(x.title,x.body,x.tags));c.commit()
    audit("note.created",str(cur.lastrowid));return {"id":cur.lastrowid}
@app.get("/api/agents")
def agents():
    with conn() as c:return [dict(x) for x in c.execute("SELECT * FROM agents ORDER BY id")]
@app.patch("/api/agents/{name}")
def agent_toggle(name:str,enabled:bool):
    with conn() as c:cur=c.execute("UPDATE agents SET enabled=? WHERE id=?",(int(enabled),name));c.commit()
    if not cur.rowcount:raise HTTPException(404,"Agent not found")
    audit("agent.toggle",f"{name}:{enabled}");return {"ok":True}
@app.get("/api/approvals")
def approvals():
    with conn() as c:return [dict(x) for x in c.execute("SELECT * FROM approvals ORDER BY id DESC")]
@app.post("/api/approvals")
def add_approval(x:Approval):
    with conn() as c:cur=c.execute("INSERT INTO approvals(action,target,details) VALUES(?,?,?)",(x.action,x.target,x.details));c.commit()
    audit("approval.requested",str(cur.lastrowid));return {"id":cur.lastrowid,"status":"pending"}
@app.post("/api/approvals/{i}")
def decide(i:int,decision:str):
    if decision not in ["approved","rejected"]:raise HTTPException(400,"Invalid decision")
    with conn() as c:cur=c.execute("UPDATE approvals SET status=?,decided=CURRENT_TIMESTAMP WHERE id=? AND status='pending'",(decision,i));c.commit()
    if not cur.rowcount:raise HTTPException(404,"Pending approval not found")
    audit("approval.decided",f"{i}:{decision}");return {"ok":True,"note":"Decision recorded only; no external action executed."}
@app.get("/api/audit")
def logs():
    with conn() as c:return [dict(x) for x in c.execute("SELECT * FROM audit ORDER BY id DESC LIMIT 250")]
@app.post("/api/chat")
async def chat(x:Chat):
    key=os.getenv("OPENAI_API_KEY","").strip()
    if not key:return {"reply":"NEXUS local modules are active. Configure OPENAI_API_KEY in .env to enable model-based reasoning. Task, memory, agent, approval and audit functions work without it.","ai_configured":False}
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r=await client.post("https://api.openai.com/v1/responses",headers={"Authorization":"Bearer "+key},json={"model":os.getenv("OPENAI_MODEL","gpt-6"),"instructions":"You are NEXUS, an owner-controlled assistant. Do not claim to execute external actions. Never request private keys or seed phrases. All sensitive operations require explicit owner approval. Domain: "+x.domain,"input":x.message})
            r.raise_for_status();data=r.json()
        answer="\n".join(t.get("text","") for o in data.get("output",[]) if o.get("type")=="message" for t in o.get("content",[]) if t.get("type")=="output_text")
    except Exception as e:raise HTTPException(502,"AI provider request failed: "+type(e).__name__)
    with conn() as c:c.execute("INSERT INTO chat(role,content,domain) VALUES('user',?,?)",(x.message,x.domain));c.execute("INSERT INTO chat(role,content,domain) VALUES('assistant',?,?)",(answer,x.domain));c.commit()
    audit("ai.response",x.domain);return {"reply":answer,"ai_configured":True}
PAGE=r"""<!doctype html><html lang="ro"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>PROJECT NEXUS</title><style>
body{margin:0;background:#0b1220;color:#e9effa;font:15px Segoe UI,Arial}header{padding:18px 24px;background:#101b2e;border-bottom:1px solid #2a3a55;display:flex;justify-content:space-between}h1{font-size:19px;letter-spacing:2px;margin:0}.wrap{display:grid;grid-template-columns:210px 1fr;min-height:90vh}nav{background:#101b2e;padding:14px}nav button{display:block;width:100%;padding:12px;text-align:left;background:none;color:#dce6f6;border:0;cursor:pointer;border-radius:7px}nav button:hover{background:#263a59}main{padding:24px;max-width:1200px;width:100%;box-sizing:border-box}.view{display:none}.view.on{display:block}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.box{background:#142238;border:1px solid #2a3b57;border-radius:10px;padding:15px;margin:10px 0}.big{font-size:28px;font-weight:bold}input,textarea,select{display:block;width:100%;box-sizing:border-box;background:#0b1729;color:white;border:1px solid #3b506f;border-radius:7px;padding:10px;margin:6px 0 12px}textarea{min-height:75px}button.go{background:#426fc2;color:white;border:0;border-radius:7px;padding:10px 14px;cursor:pointer;margin:4px}small,.muted{color:#9eb0c9}.entry{padding:12px 0;border-bottom:1px solid #2b3c56;overflow-wrap:anywhere}.tag{color:#9cb8e9;font-size:12px}@media(max-width:750px){.wrap{grid-template-columns:1fr}nav{display:grid;grid-template-columns:repeat(2,1fr)}.grid{grid-template-columns:repeat(2,1fr)}main{padding:12px}}
</style><header><h1>PROJECT NEXUS <small>MASTER 0.6.1</small></h1><span id="state">CONNECTING</span></header><div class="wrap"><nav>
<button onclick="view('home')">Overview</button><button onclick="view('tasks')">Tasks</button><button onclick="view('memory')">Knowledge Vault</button><button onclick="view('agents')">AI Agents</button><button onclick="view('approvals')">Approvals</button><button onclick="view('chat')">AI Workspace</button><button onclick="view('audit')">Audit Log</button><button onclick="view('math')">Math Resources</button><button onclick="view('mathengine')">Math Engine</button><button onclick="view(&quot;plugins&quot;)">Plugin Manager</button><button onclick="view(&quot;banking&quot;)">Banking Sandbox</button><button onclick="window.location.href='/wallet'">Wallet Manager</button></nav><main>
<section id="home" class="view on"><h2>Command Center</h2><div class="grid"><div class="box">Open tasks<div class="big" id="stasks">0</div></div><div class="box">Notes<div class="big" id="snotes">0</div></div><div class="box">Approvals<div class="big" id="sapprovals">0</div></div><div class="box">Active agents<div class="big" id="sagents">0</div></div></div><div class="box"><b>System status</b><p id="status">Loading…</p><small>Local-first. Sensitive operations require owner approval. Approval records do not execute external actions.</small></div></section>
<section id="tasks" class="view"><h2>Task Manager</h2><div class="box"><input id="tt" placeholder="Task title"><textarea id="td" placeholder="Description"></textarea><select id="tcat"><option>core</option><option>research</option><option>developer</option><option>crypto</option><option>depin</option><option>mining</option><option>security</option></select><select id="tp"><option>normal</option><option>high</option><option>low</option></select><button class="go" onclick="addTask()">Create task</button></div><div class="box" id="tasklist"></div></section>
<section id="memory" class="view"><h2>Knowledge Vault</h2><div class="box"><input id="nt" placeholder="Title"><textarea id="nb" placeholder="Persistent project knowledge, decisions, documentation…"></textarea><input id="tags" placeholder="Tags"><button class="go" onclick="addNote()">Save note</button></div><div class="box"><input id="nq" placeholder="Search saved notes" oninput="loadNotes()"><div id="noteslist"></div></div></section>
<section id="agents" class="view"><h2>Agent Registry</h2><p class="muted">Enable/disable agent profiles. This does not grant system permissions.</p><div class="box" id="agentlist"></div></section>
<section id="approvals" class="view"><h2>Owner Approval Queue</h2><div class="box"><input id="aa" placeholder="Requested operation"><input id="at" placeholder="Target device/service"><textarea id="ad" placeholder="Scope, resource limits, duration, risks"></textarea><button class="go" onclick="addApproval()">Request approval</button></div><div class="box" id="applist"></div></section>
<section id="chat" class="view"><h2>AI Workspace</h2><p class="muted">Configure your API key locally in .env. Never enter wallet secrets.</p><div class="box"><select id="domain"><option>core</option><option>research</option><option>developer</option><option>crypto</option><option>depin</option><option>mining</option><option>security</option></select><div id="chatlog"></div><textarea id="msg" placeholder="Give NEXUS a task…"></textarea><button class="go" onclick="send()">Send</button></div></section>
<section id="audit" class="view"><h2>Audit Log</h2><div class="box" id="auditlist"></div></section><section id="math" class="view"><h2>Advanced Mathematics Lab</h2><p class="muted">Official specialist tools and references. These open external services; they are not represented as native NEXUS solvers.</p>
<div class="box"><h3>Symbolic and numerical computation</h3>
<div class="entry"><b>Wolfram|Alpha</b> — algebra, calculus, equations and numerical computation. <a href="https://www.wolframalpha.com/" target="_blank" rel="noopener">Open Wolfram|Alpha</a></div>
<div class="entry"><b>SageMath</b> — open-source computer algebra and advanced mathematics. <a href="https://www.sagemath.org/" target="_blank" rel="noopener">Official site</a> · <a href="https://sagecell.sagemath.org/" target="_blank" rel="noopener">Online SageMathCell</a></div>
<div class="entry"><b>SymPy</b> — Python symbolic mathematics. <a href="https://www.sympy.org/" target="_blank" rel="noopener">Official site</a> · <a href="https://docs.sympy.org/" target="_blank" rel="noopener">Documentation</a></div></div>
<div class="box"><h3>Visualization and geometry</h3>
<div class="entry"><b>GeoGebra</b> — algebra, geometry, calculus, statistics and 3D. <a href="https://www.geogebra.org/" target="_blank" rel="noopener">Open GeoGebra</a></div>
<div class="entry"><b>Desmos</b> — graphing calculator and function visualization. <a href="https://www.desmos.com/calculator" target="_blank" rel="noopener">Open Graphing Calculator</a></div></div>
<div class="box"><h3>Reference and research</h3>
<div class="entry"><b>Wolfram MathWorld</b> — mathematical encyclopedia. <a href="https://mathworld.wolfram.com/" target="_blank" rel="noopener">Open MathWorld</a></div>
<div class="entry"><b>OEIS</b> — encyclopedia of integer sequences. <a href="https://oeis.org/" target="_blank" rel="noopener">Open OEIS</a></div>
<div class="entry"><b>arXiv Mathematics</b> — mathematical research preprints. <a href="https://arxiv.org/archive/math" target="_blank" rel="noopener">Browse Mathematics</a></div></div><section id="mathengine" class="view"><h2>NEXUS Math & Decoder Engine</h2><p id="mathstatus" class="muted">Loading…</p>
<div class="box"><h3>Symbolic mathematics</h3><select id="mop"><option>simplify</option><option>factor</option><option>expand</option><option>differentiate</option><option>integrate</option><option>solve</option><option>limit</option><option>series</option><option>numeric</option><option>verify_identity</option></select><input id="mexpr" value="sin(x)^2+cos(x)^2"><input id="mvar" value="x"><input id="mrhs" placeholder="RHS for identity verification"><button class="go" onclick="mathCompute()">Calculate</button><pre id="mresult"></pre></div>
<div class="box"><h3>Matrices</h3><select id="matop"><option>determinant</option><option>rank</option><option>rref</option><option>inverse</option><option>transpose</option><option>eigenvalues</option><option>charpoly</option><option>nullspace</option></select><textarea id="matrixdata">[[1,2],[3,4]]</textarea><button class="go" onclick="matrixCalc()">Run</button><pre id="matrixresult"></pre></div>
<div class="box"><h3>Probability</h3><select id="probop"><option>binomial</option><option>combination</option><option>permutation</option><option>bayes</option></select><input id="pn" value="10" placeholder="n"><input id="pk" value="3" placeholder="k/r"><input id="pp" value="0.5" placeholder="p"><input id="prior" value="0.01"><input id="sens" value="0.99"><input id="spec" value="0.95"><button class="go" onclick="probCalc()">Calculate</button><pre id="probresult"></pre></div>
<div class="box"><h3>Number theory / cryptographic math</h3><select id="ntop"><option>factorint</option><option>isprime</option><option>nextprime</option><option>prevprime</option><option>totient</option><option>mobius</option><option>gcd</option><option>lcm</option><option>mod_inverse</option><option>discrete_log</option></select><input id="ntn" value="8051"><input id="ntb" value="13"><input id="ntmod" value="17"><button class="go" onclick="ntCalc()">Run</button><pre id="ntresult"></pre></div>
<div class="box"><h3>Optimization</h3><input id="optx" value="x^2-4*x+7"><button class="go" onclick="optCalc()">Stationary points</button><pre id="optresult"></pre></div>
<div class="box"><h3>Decoder / metadata inspector</h3><p class="muted">Base64, hex, URL, JSON, Base64-GZIP and hash fingerprint recognition. Hashes are not reversible; this is not an encryption breaker.</p><select id="decformat"><option>auto</option><option>base64</option><option>hex</option><option>url</option><option>json</option><option>gzip</option></select><textarea id="decdata" placeholder="Paste non-secret encoded text"></textarea><button class="go" onclick="decodeData()">Decode / inspect</button><pre id="decresult"></pre></div></section><section id="plugins" class="view"><h2>Plugin & Connector Manager</h2><p class="muted">26 integration definitions. Status distinguishes public endpoint availability, configured credentials and adapters still pending.</p><div class="box"><button class="go" onclick="loadPlugins()">Refresh catalogue</button><div id="pluginlist"></div></div></section>
<section id="banking" class="view"><h2>Banking Sandbox</h2><p class="muted">Synthetic test accounts only. No live bank connection or real payments.</p><div class="box"><button class="go" onclick="loadBanking()">Load demo ledger</button><button class="go" onclick="runBankTests()">Run sandbox tests</button><pre id="bankresult"></pre></div><div class="box"><h3>Cash-flow analysis</h3><pre id="bankanalysis"></pre></div></section></main></div>
<script>
const $=x=>document.getElementById(x);async function api(u,o){let r=await fetch(u,{headers:{'Content-Type':'application/json'},...o}),d=await r.json();if(!r.ok)throw Error(d.detail||'Request failed');return d}function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
async function refresh(){let [h,s]=await Promise.all([api('/api/health'),api('/api/summary')]);$('state').textContent='● '+h.status+' · '+h.version;$('status').textContent='NEXUS operational. AI '+(h.ai_configured?'configured':'not configured')+'. Local data persistent.';$('stasks').textContent=s.tasks.open||0;$('snotes').textContent=s.notes;$('sapprovals').textContent=s.pending;$('sagents').textContent=s.agents}
function view(id){document.querySelectorAll('.view').forEach(x=>x.classList.remove('on'));$(id).classList.add('on');({tasks:loadTasks,memory:loadNotes,agents:loadAgents,approvals:loadApprovals,audit:loadAudit,plugins:loadPlugins,banking:loadBanking}[id]||(()=>{}))()}
async function addTask(){await api('/api/tasks',{method:'POST',body:JSON.stringify({title:$('tt').value,description:$('td').value,domain:$('tcat').value,priority:$('tp').value})});$('tt').value='';$('td').value='';loadTasks();refresh()}
async function loadTasks(){let a=await api('/api/tasks');$('tasklist').innerHTML=a.map(t=>`<div class="entry"><b>${esc(t.title)}</b> <span class="tag">${esc(t.domain)} · ${esc(t.priority)}</span><p>${esc(t.description)}</p><select onchange="setTask(${t.id},this.value)">${['open','in_progress','blocked','done','cancelled'].map(x=>`<option ${x===t.status?'selected':''}>${x}</option>`)}</select><button class="go" onclick="delTask(${t.id})">Delete</button></div>`).join('')||'No tasks yet'}
async function setTask(i,s){await api('/api/tasks/'+i+'?status='+s,{method:'PATCH'});refresh()}async function delTask(i){if(confirm('Delete?')){await api('/api/tasks/'+i,{method:'DELETE'});loadTasks();refresh()}}
async function addNote(){await api('/api/notes',{method:'POST',body:JSON.stringify({title:$('nt').value,body:$('nb').value,tags:$('tags').value})});$('nt').value='';$('nb').value='';$('tags').value='';loadNotes();refresh()}
async function loadNotes(){let a=await api('/api/notes?q='+encodeURIComponent($('nq').value));$('noteslist').innerHTML=a.map(n=>`<div class="entry"><b>${esc(n.title)}</b><p class="tag">${esc(n.tags)} · ${esc(n.created)}</p><pre>${esc(n.body)}</pre></div>`).join('')||'No notes saved'}
async function loadAgents(){let a=await api('/api/agents');$('agentlist').innerHTML=a.map(x=>`<div class="entry"><b>${esc(x.name)}</b><p>${esc(x.purpose)}</p><label><input type="checkbox" style="width:auto;display:inline" ${x.enabled?'checked':''} onchange="toggleAgent('${x.id}',this.checked)"> Enabled</label></div>`).join('')}
async function toggleAgent(id,on){await api('/api/agents/'+id+'?enabled='+on,{method:'PATCH'});refresh()}
async function addApproval(){await api('/api/approvals',{method:'POST',body:JSON.stringify({action:$('aa').value,target:$('at').value,details:$('ad').value})});$('aa').value='';$('at').value='';$('ad').value='';loadApprovals();refresh()}
async function loadApprovals(){let a=await api('/api/approvals');$('applist').innerHTML=a.map(x=>`<div class="entry"><b>${esc(x.action)}</b> · ${esc(x.target)} <span class="tag">${esc(x.status)}</span><p>${esc(x.details)}</p>${x.status==='pending'?`<button class="go" onclick="decision(${x.id},'approved')">Approve</button><button class="go" onclick="decision(${x.id},'rejected')">Reject</button>`:''}</div>`).join('')||'No approvals'}
async function decision(i,d){await api('/api/approvals/'+i+'?decision='+d,{method:'POST'});loadApprovals();refresh()}
async function loadAudit(){let a=await api('/api/audit');$('auditlist').innerHTML=a.map(x=>`<div class="entry"><b>${esc(x.event)}</b><p class="muted">${esc(x.created)} · ${esc(x.details)}</p></div>`).join('')}
function bubble(role,t){let p=document.createElement('p');p.className='box';p.textContent=role+': '+t;$('chatlog').appendChild(p)}
async function send(){let m=$('msg').value.trim();if(!m)return;$('msg').value='';bubble('You',m);try{let d=await api('/api/chat',{method:'POST',body:JSON.stringify({message:m,domain:$('domain').value})});bubble('NEXUS',d.reply)}catch(e){bubble('Error',e.message)}}


async function loadPlugins(){let d=await api('/api/plugins');$('pluginlist').innerHTML=d.plugins.map(x=>`<div class="entry"><b>${esc(x.name)}</b> <span class="tag">${esc(x.status)}</span><p>${esc(x.scope)}</p><small>${esc(x.security_note)} · Config: ${esc(x.configuration_variable||'public')}</small></div>`).join('')}
async function loadBanking(){out('bankresult',api('/api/banking/sandbox'));out('bankanalysis',api('/api/banking/analysis'))}
async function runBankTests(){out('bankresult',api('/api/banking/simulate',{method:'POST'}))}
async function mathStatus(){let d=await api('/api/math/status');$('mathstatus').textContent='SymPy '+d.sympy_version+' active · SageMath '+(d.sage.available?'detected':'not installed/configured')}
async function out(id,p){try{$(id).textContent=JSON.stringify(await p,null,2)}catch(e){$(id).textContent=e.message}}
async function mathCompute(){out('mresult',api('/api/math/compute',{method:'POST',body:JSON.stringify({operation:$('mop').value,expression:$('mexpr').value,variable:$('mvar').value,rhs:$('mrhs').value})}))}
async function matrixCalc(){try{out('matrixresult',api('/api/math/matrix',{method:'POST',body:JSON.stringify({operation:$('matop').value,matrix:JSON.parse($('matrixdata').value)})}))}catch(e){$('matrixresult').textContent=e.message}}
async function probCalc(){out('probresult',api('/api/math/probability',{method:'POST',body:JSON.stringify({operation:$('probop').value,n:$('pn').value,k:$('pk').value,r:$('pk').value,p:$('pp').value,prior:$('prior').value,sensitivity:$('sens').value,specificity:$('spec').value})}))}
async function ntCalc(){out('ntresult',api('/api/math/number-theory',{method:'POST',body:JSON.stringify({operation:$('ntop').value,n:$('ntn').value,b:$('ntb').value,target:$('ntb').value,base:$('ntn').value,modulus:$('ntmod').value})}))}
async function optCalc(){out('optresult',api('/api/math/optimize',{method:'POST',body:JSON.stringify({expression:$('optx').value,variable:'x'})}))}
async function decodeData(){out('decresult',api('/api/math/decode',{method:'POST',body:JSON.stringify({format:$('decformat').value,data:$('decdata').value})}))}
mathStatus().catch(e=>$("mathstatus").textContent=e.message);refresh().catch(e=>$('state').textContent='API ERROR');
</script></html>"""
