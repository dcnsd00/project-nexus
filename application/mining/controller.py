from __future__ import annotations
import atexit, json, os, re, shutil, subprocess, tempfile, threading, time, urllib.request
from pathlib import Path
from mining.pool_config import pool_endpoint, pool_username
from mining.process_arbiter import MINING_PROCESS_ARBITER
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MINING_DIR = ROOT / 'mining'
RUNTIME = MINING_DIR / 'runtime'
RUNTIME.mkdir(parents=True, exist_ok=True)
LOG = RUNTIME / 'miner.log'
LOCK = threading.RLock()

MINERS = {
    'xmrig': {'name':'XMRig', 'executables':['xmrig','xmrig.exe'], 'api':'http://127.0.0.1:18080/1/summary', 'launch':True,
              'algorithms':['RandomX','CryptoNight'], 'device':['CPU']},
    'trex': {'name':'T-Rex', 'executables':['t-rex','t-rex.exe','trex.exe'], 'api':'http://127.0.0.1:4067/summary', 'launch':True, 'algorithms':['KawPoW','Etchash'], 'device':['GPU']},
    'srbminer': {'name':'SRBMiner-MULTI', 'executables':['SRBMiner-MULTI','SRBMiner-MULTI.exe'], 'api':'http://127.0.0.1:21550/', 'launch':True,
                 'algorithms':['KawPoW','KHeavyHash','Etchash','RandomX','PearlHash','PearlPow','Verthash','Autolykos2','FishHash','blake3_decred'], 'device':['CPU','GPU','BOTH']},
    'lolminer': {'name':'lolMiner', 'executables':['lolMiner','lolMiner.exe'], 'api':None, 'launch':True, 'algorithms':['KHeavyHash','Etchash','KawPoW'], 'device':['GPU']},
    'gminer': {'name':'GMiner', 'executables':['miner','miner.exe','gminer'], 'api':None, 'launch':True, 'algorithms':['KHeavyHash','Etchash','KawPoW'], 'device':['GPU']},
    'rigel': {'name':'Rigel', 'executables':['rigel','rigel.exe'], 'api':None, 'launch':True, 'algorithms':['KawPoW','Etchash','Autolykos2','NexaPow','FishHash','XelisHashv3'], 'device':['GPU']},
    'bzminer': {'name':'BzMiner', 'executables':['bzminer','bzminer.exe'], 'api':'http://127.0.0.1:4014/', 'launch':True, 'algorithms':['PearlHash','PearlPow','KawPoW','Etchash','NexaPow','Autolykos2'], 'device':['GPU']},
    'teamredminer': {'name':'TeamRedMiner', 'executables':['teamredminer','teamredminer.exe'], 'api':None, 'launch':True, 'algorithms':['KawPoW','Etchash','Verthash','Autolykos2'], 'device':['GPU']},
    'nexus-btc-cpu': {'name':'NEXUS Bitcoin SHA-256d CPU (experimental)', 'executables':[], 'api':None, 'launch':True, 'internal':True, 'algorithms':['SHA-256d'], 'device':['CPU']},
    'nerdminer': {'name':'NerdMiner (ESP32 extern)', 'executables':[], 'api':None, 'launch':False, 'external_device':True, 'algorithms':['SHA-256d'], 'device':['ESP32']},
    'asic': {'name':'ASIC extern (configurare Stratum)', 'executables':[], 'api':None, 'launch':False, 'external_device':True, 'algorithms':['SHA-256d','Scrypt','KHeavyHash','Etchash','Equihash-125-4','X11','Eaglesong','Blake3','NexaPow'], 'device':['ASIC']},
}

_state: dict[str, Any] = {'status':'stopped','pid':None,'miner_id':None,'miner_name':None,'coin':None,'algorithm':None,'device':None,'pool':None,'started_at':None,'last_error':None,'last_exit_code':None,'log_path':str(LOG),'api':None}
_proc: subprocess.Popen | None = None
_ARBITER_OWNER = "direct-mining-controller"

_runtime_config_path: Path | None = None
_SENSITIVE_ARG_FLAGS = {
    "-p", "-P", "--pass", "--password", "--token",
    "--access-token", "--api-access-token", "--rpc-password", "--userpass",
}


def _redact_command_args(arguments: list[str]) -> list[str]:
    """Return launch arguments safe for human-readable logs."""
    safe: list[str] = []
    redact_next = False
    for raw in arguments:
        value = str(raw)
        if redact_next:
            safe.append("[REDACTED]")
            redact_next = False
            continue
        flag, separator, _ = value.partition("=")
        if value.casefold() in _SENSITIVE_ARG_FLAGS:
            safe.append(value)
            redact_next = True
        elif separator and flag.casefold() in _SENSITIVE_ARG_FLAGS:
            safe.append(f"{flag}=[REDACTED]")
        else:
            safe.append(value)
    if redact_next:
        safe.append("[MISSING]")
    return safe


def _write_private_xmrig_config(config: dict[str, Any]) -> Path:
    """Create a per-user temporary config; POSIX mode is owner read/write only."""
    fd, filename = tempfile.mkstemp(prefix="nexus-xmrig-", suffix=".json")
    path = Path(filename)
    try:
        if os.name != "nt" and hasattr(os, "fchmod"):
            os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(config, handle, indent=2)
            handle.flush()
        return path
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise


def _cleanup_runtime_config() -> None:
    global _runtime_config_path
    path = _runtime_config_path
    _runtime_config_path = None
    if path is not None:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            # Keep shutdown reliable; a later operator cleanup can inspect the path.
            pass


atexit.register(_cleanup_runtime_config)


def _pool_catalog():
    return json.loads((MINING_DIR/'pools.json').read_text(encoding='utf-8'))['pools']


def _resolve_binary(miner_id: str, explicit_path: str | None = None) -> str | None:
    if explicit_path:
        p = Path(explicit_path).expanduser().resolve()
        if p.is_file(): return str(p)
        return None
    # Prefer NEXUS-managed installations, then PATH and explicit environment paths.
    managed = ROOT / 'miners' / miner_id
    if managed.exists():
        for name in MINERS[miner_id]['executables']:
            hits = list(managed.rglob(name))
            if hits: return str(hits[0].resolve())
    for name in MINERS[miner_id]['executables']:
        found = shutil.which(name)
        if found: return found
    env_key = 'NEXUS_' + miner_id.upper() + '_PATH'
    configured = os.environ.get(env_key)
    if configured and Path(configured).is_file(): return str(Path(configured).resolve())
    return None


def inventory() -> dict:
    items=[]
    for mid, spec in MINERS.items():
        path=_resolve_binary(mid)
        internal=bool(spec.get('internal'))
        items.append({'id':mid,'name':spec['name'],'available':bool(path) or internal,'path':path or ('NEXUS internal engine' if internal else None),
                      'internal':internal,'external_device':bool(spec.get('external_device')),
                      'launch_supported':spec['launch'],'api':spec['api'],'algorithms':spec['algorithms'],
                      'device_support':spec['device'], 'note':('Motor intern NEXUS; nu necesită executabil extern.' if internal else ('Detectat local; lansarea este disponibilă.' if path and spec['launch'] else ('Executabil detectat, dar adaptorul de lansare nu este încă activ.' if path else 'Nu este instalat/detectat.')))})
    return {'miners':items,'processes':active_processes(),'controller':status()}


def active_processes() -> list[dict]:
    found=[]
    try:
        import psutil
        for p in psutil.process_iter(['pid','name','exe','cmdline','cpu_percent','memory_info']):
            try:
                name=(p.info.get('name') or '').lower()
                if any(any(token in name for token in [Path(x).stem.lower() for x in spec['executables']]) for spec in MINERS.values()):
                    mi=p.info.get('memory_info')
                    found.append({'pid':p.info['pid'],'name':p.info.get('name'),'exe':p.info.get('exe'),
                                  'cpu_percent':p.info.get('cpu_percent'),'memory_mb':round(mi.rss/1048576,1) if mi else None,
                                  'managed_by_nexus': bool(_state.get('pid')==p.info.get('pid'))})
            except (psutil.NoSuchProcess,psutil.AccessDenied): pass
    except Exception:
        if os.name == 'nt':
            try:
                out=subprocess.run(['tasklist','/FO','CSV','/NH'],capture_output=True,text=True,timeout=5).stdout
                for line in out.splitlines():
                    if any(Path(x).name.lower() in line.lower() for s in MINERS.values() for x in s['executables']):
                        found.append({'tasklist_line':line,'managed_by_nexus':False})
            except Exception: pass
    if _proc is not None and _state.get('miner_id')=='nexus-btc-cpu' and _proc.poll() is None:
        found.append({'pid':None,'name':'NEXUS Bitcoin SHA-256d CPU (internal thread)','exe':None,
                      'cpu_percent':None,'memory_mb':None,'managed_by_nexus':True,'internal':True})
    return found


def _http_json(url: str, timeout: float=1.2) -> dict | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            data=json.loads(r.read().decode('utf-8',errors='replace'))
            return data if isinstance(data,dict) else None
    except Exception: return None


def _parse_rate(value: Any) -> tuple[float | None,str | None]:
    if isinstance(value,(int,float)): return float(value), 'H/s'
    if isinstance(value,str):
        m=re.search(r'([\d.]+)\s*([kKmMgGtT]?)\s*(H/s|h/s|hash/s)?',value)
        if m:
            mult={'':1,'k':1e3,'m':1e6,'g':1e9,'t':1e12}[m.group(2).lower()]
            return float(m.group(1))*mult,'H/s'
    return None,None


def _find_hashrate(node):
    if isinstance(node,dict):
        for k,v in node.items():
            key=str(k).lower().replace('_','')
            if 'hashrate' in key or key in ('hashspeed','hashratehs'):
                if isinstance(v,(int,float)): return float(v)
                if isinstance(v,list) and v:
                    nums=[x for x in v if isinstance(x,(int,float))]
                    if nums: return float(nums[0])
                if isinstance(v,dict):
                    nums=[x for x in v.values() if isinstance(x,(int,float))]
                    if nums: return float(sum(nums))
            got=_find_hashrate(v)
            if got is not None:return got
    elif isinstance(node,list):
        for v in node:
            got=_find_hashrate(v)
            if got is not None:return got
    return None


def _metrics() -> dict:
    api_url=_state.get('api')
    raw=_http_json(api_url) if api_url else None
    rate=None; accepted=None; rejected=None; api_ok=bool(raw)
    if raw:
        # XMRig /1/summary: hashrate.total is [10s,60s,15m]
        h=raw.get('hashrate') or {}
        total=h.get('total') if isinstance(h,dict) else None
        if isinstance(total,list) and total: rate=total[0]
        elif isinstance(total,(int,float)): rate=total
        results=raw.get('results') or {}
        accepted=results.get('shares_good',results.get('accepted',raw.get('accepted_count')))
        total=results.get('shares_total')
        rejected=results.get('shares_failed',raw.get('rejected_count'))
        if rejected is None and isinstance(total,(int,float)) and isinstance(accepted,(int,float)): rejected=max(0,total-accepted)
        # SRBMiner API formats vary; try common names.
        if rate is None:
            rate=_find_hashrate(raw)
        if rate is None:
            for key in ('hashrate','hashRate','total_hashrate','totalHashrate'):
                val=raw.get(key)
                if isinstance(val,(int,float)): rate=val; break
                if isinstance(val,dict):
                    rate=val.get('total') or val.get('gpu') or val.get('cpu')
                    if isinstance(rate,list) and rate: rate=rate[0]
                    if rate is not None: break
        accepted=accepted if accepted is not None else raw.get('accepted_shares',raw.get('accepted'))
        rejected=rejected if rejected is not None else raw.get('rejected_shares',raw.get('rejected'))
    gpu={'available':False,'utilization_percent':None,'memory_used_mb':None,'memory_total_mb':None,'temperature_c':None,'power_w':None}
    exe=shutil.which('nvidia-smi') or (str(Path(os.environ.get('WINDIR', r'C:\\Windows'))/'System32'/'nvidia-smi.exe') if os.name=='nt' and (Path(os.environ.get('WINDIR', r'C:\\Windows'))/'System32'/'nvidia-smi.exe').is_file() else None) or (str(Path(os.environ.get('WINDIR', r'C:\\Windows'))/'System32'/'nvidia-smi.exe') if os.name=='nt' and (Path(os.environ.get('WINDIR', r'C:\\Windows'))/'System32'/'nvidia-smi.exe').is_file() else None)
    if exe:
        try:
            out=subprocess.run([exe,'--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=2,check=True).stdout.splitlines()
            if out:
                v=[x.strip() for x in out[0].split(',')]
                if len(v)>=5:
                    gpu={'available':True,'utilization_percent':_num(v[0]),'memory_used_mb':_num(v[1]),'memory_total_mb':_num(v[2]),'temperature_c':_num(v[3]),'power_w':_num(v[4])}
        except Exception: pass
    cpu={'utilization_percent':None,'memory_used_mb':None,'memory_total_mb':None}
    proc_stats={'cpu_percent':None,'memory_mb':None}
    try:
        import psutil
        vm=psutil.virtual_memory(); cpu={'utilization_percent':psutil.cpu_percent(interval=0),'memory_used_mb':round(vm.used/1048576,1),'memory_total_mb':round(vm.total/1048576,1)}
        pid=_state.get('pid')
        if pid:
            try:
                proc=psutil.Process(pid); mi=proc.memory_info(); proc_stats={'cpu_percent':proc.cpu_percent(interval=0),'memory_mb':round(mi.rss/1048576,1)}
            except (psutil.NoSuchProcess,psutil.AccessDenied): pass
    except Exception: pass
    hashrate_source='miner_api' if rate is not None else None
    if rate is None and _state.get('status') in ('running','starting'):
        for line in reversed(read_log(100)):
            m=re.search(r'(?:speed|hashrate|hash rate)[^0-9]{0,30}([0-9]+(?:\\.[0-9]+)?)\\s*([kKmMgGtT]?)\\s*(?:H/s|h/s|hash/s)',line,re.I)
            if m:
                rate=float(m.group(1))*{'':1,'k':1e3,'m':1e6,'g':1e9,'t':1e12}[m.group(2).lower()]
                hashrate_source='miner_log'
                break
    sampled_at=time.time()
    api_state=('not_supported' if not api_url else ('connected' if api_ok else 'unreachable_or_invalid'))
    return {
        'schema_version':1,
        'sampled_at':sampled_at,
        'miner_id':_state.get('miner_id'),
        'miner_name':_state.get('miner_name'),
        'miner_api':{'url':api_url,'status':api_state,'connected':api_ok,'checked_at':sampled_at if api_url else None},
        # A local miner API response does not prove the upstream pool session is healthy.
        'pool_connection':{'status':'unknown','evidence':None,'checked_at':None},
        'api_connected':api_ok,
        'hashrate_hs':rate,
        'hashrate_display':_format_rate(rate),
        'hashrate_source':hashrate_source,
        'accepted_shares':accepted,
        'rejected_shares':rejected,
        'shares_source':'miner_api' if raw and (accepted is not None or rejected is not None) else None,
        'gpu':gpu,'system':cpu,'miner_process':proc_stats,'raw_api':raw,
        'pool_reported_coin_mined':None,'pool_reported_payout':None,'earnings_source':'not_connected'
    }


def _num(v):
    try:return float(v)
    except Exception:return None


def _format_rate(v):
    if not isinstance(v,(int,float)): return None
    units=['H/s','kH/s','MH/s','GH/s','TH/s','PH/s']; n=float(v); i=0
    while n>=1000 and i<len(units)-1: n/=1000; i+=1
    return f'{n:.3f} {units[i]}'


def _diagnose(message: str) -> dict:
    s=(message or '').lower()
    rules=[
      (('not found','no such file','cannot find','file not found'),('MINER_BINARY_MISSING','Executabilul minerului nu a fost găsit. Verifică instalarea sau calea completă.')),
      (('connection refused','connection timed out','no route','failed to connect','network unreachable'),('POOL_CONNECTION','Nu se poate stabili conexiunea cu pool-ul. Verifică hostul, portul, DNS-ul și firewall-ul.')),
      (('unauthorized','invalid wallet','invalid address','login failed','not authorized'),('POOL_AUTH','Pool-ul a respins autentificarea/adresa. Verifică moneda și formatul adresei.')),
      (('unsupported algorithm','unknown algorithm','algorithm not supported'),('ALGORITHM_UNSUPPORTED','Minerul selectat nu suportă algoritmul cerut. Alege alt miner sau alt pool.')),
      (('out of memory','allocation failed','not enough memory','dag'),('GPU_MEMORY','Memorie GPU insuficientă sau alocarea DAG a eșuat. Redu intensitatea ori folosește alt algoritm/GPU.')),
      (('cuda error','cuda driver','no cuda','opencl error','no device'),('GPU_DRIVER','Problemă de driver/backend GPU. Verifică driverul și compatibilitatea CUDA/OpenCL.')),
      (('rejected','invalid share','low difficulty'),('SHARE_REJECTED','Pool-ul a respins share-uri. Verifică algoritmul, dificultatea și endpoint-ul.')),
      (('certificate','ssl','tls handshake'),('TLS_ERROR','Negocierea TLS a eșuat. Verifică portul SSL/TLS și certificatul.')),
    ]
    for needles,(code,advice) in rules:
        if any(x in s for x in needles): return {'code':code,'message':message[-700:],'advice':advice,'severity':'warning'}
    return {'code':'UNCLASSIFIED','message':message[-700:],'advice':'Consultă ultimele linii din jurnal și verifică versiunea minerului, configurația și driverele.','severity':'error'}


def start(req: dict) -> dict:
    global _proc, _runtime_config_path
    with LOCK:
        if _proc is not None and _proc.poll() is None:
            raise ValueError('Există deja un miner pornit de NEXUS. Oprește-l înainte de a porni altul.')
        if _proc is not None:
            _proc = None
            _cleanup_runtime_config()
            MINING_PROCESS_ARBITER.release(_ARBITER_OWNER)
        mid=req['miner_id']; spec=MINERS.get(mid)
        if not spec or not spec['launch']: raise ValueError('Adaptorul de lansare pentru acest miner nu este activ în această versiune.')
        pool=next((p for p in _pool_catalog() if p['id']==req['pool_id']),None)
        if not pool: raise ValueError('Pool-ul selectat nu există în catalog.')
        if pool.get('selectable') is False: raise ValueError('Profilul este informativ/neconfigurabil în acest moment.')
        if str(pool.get('payout_status','')).lower() in ('paused','suspended','disabled'):
            raise ValueError(f'Payout-ul {pool.get("payout_asset",pool.get("coin"))} este suspendat de operator; NEXUS blochează pornirea pentru a evita mining fără destinație de recompensă.')
        if pool['id']=='custom':
            host=req.get('custom_host'); port=req.get('custom_port')
        else:
            host,port=pool_endpoint(pool,bool(req.get('use_ssl')))
        if not host or not port: raise ValueError('Host/port pool lipsă.')
        if not re.fullmatch(r'[A-Za-z0-9.-]{1,253}',host): raise ValueError('Host invalid.')
        wallet=req['wallet'].strip(); worker=req.get('worker','nexus-worker').strip()
        login=pool_username(pool,wallet,worker)
        if not wallet or any(c.isspace() for c in wallet): raise ValueError('Adresa wallet este goală sau conține spații.')
        if not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}',worker): raise ValueError('Numele workerului conține caractere nepermise.')
        algo=req.get('algorithm') or pool['algorithm']; device=req.get('device','GPU').upper()
        if algo != pool.get('algorithm'):
            raise ValueError(f'Algoritm incompatibil: pool-ul {pool["name"]} cere {pool.get("algorithm")}; nu se permite suprascrierea manuală.')
        if algo not in spec['algorithms']: raise ValueError(f'{spec["name"]} nu are algoritmul {algo} în lista compatibilă NEXUS.')
        if device not in spec['device']:
            raise ValueError(f'{spec["name"]} nu suportă dispozitivul selectat: {device}.')
        if algo == 'RandomX' and device not in ('CPU','BOTH'):
            raise ValueError('RandomX este disponibil aici numai pe CPU; GTX 1650 Ti GPU nu este acceptat pentru RandomX.')
        if algo == 'SHA-256d' and device in ('GPU','BOTH'):
            raise ValueError('Bitcoin SHA-256d nu este oferit ca mining GPU pe GTX 1650 Ti. Selectează ASIC/NerdMiner extern.')
        if mid == 'nerdminer':
            raise ValueError('NerdMiner este un dispozitiv ESP32 extern. Folosește generatorul de configurație; NEXUS nu poate porni firmware-ul ESP32 din Windows.')
        if mid == 'nexus-btc-cpu':
            if device != 'CPU' or algo != 'SHA-256d' or pool.get('coin') != 'BTC':
                raise ValueError('Motorul NEXUS Bitcoin CPU acceptă numai BTC / SHA-256d / CPU.')
            if str(pool.get('stratum_protocol','')).upper() != 'V1':
                raise ValueError('Motorul intern necesită un endpoint Stratum V1 documentat.')
            if pool.get('id') == 'custom' and not req.get('custom_host'):
                raise ValueError('Pentru pool custom trebuie configurat host-ul.')
            from mining.stratum_miner import StratumBitcoinWorker
            worker_engine=StratumBitcoinWorker(str(host),int(port),login,req.get('password','x'),bool(req.get('use_ssl')),
                                              timeout=8.0,scan_chunk=50000,prefer_native=True)
            LOG.write_text(f'NEXUS internal Bitcoin SHA-256d CPU\nPool: {pool["name"]} | {host}:{int(port)} | TLS={bool(req.get("use_ssl"))}\nWallet/login: {login}\n',encoding='utf-8')
            if not MINING_PROCESS_ARBITER.acquire(_ARBITER_OWNER):
                raise ValueError('O altă sesiune de minare NEXUS este deja activă prin controllerul direct sau HybridSupervisor.')
            try:
                worker_engine.start()
            except Exception:
                MINING_PROCESS_ARBITER.release(_ARBITER_OWNER)
                raise
            worker_pid = getattr(worker_engine, 'pid', None)
            MINING_PROCESS_ARBITER.update_processes(_ARBITER_OWNER, [worker_pid] if isinstance(worker_pid, int) else [])
            _proc=worker_engine
            _state.update(status='starting',pid=None,miner_id=mid,miner_name=spec['name'],coin='BTC',algorithm=algo,device='CPU',
                          pool={'name':pool['name'],'host':host,'port':int(port),'tls':bool(req.get('use_ssl'))},
                          started_at=time.time(),last_error=None,last_exit_code=None,api=None)
            return status()
        if device in ('GPU','BOTH'):
            dag_path=MINING_DIR/'dag_requirements.json'
            try: dag_catalog=json.loads(dag_path.read_text(encoding='utf-8')).get('requirements_mib', {})
            except Exception: dag_catalog={}
            requirement=dag_catalog.get(algo)
            if requirement:
                try:
                    query=subprocess.run(['nvidia-smi','--query-gpu=memory.total','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=3)
                    total_mib=int(float(query.stdout.splitlines()[0].strip())) if query.returncode==0 and query.stdout.strip() else 0
                except Exception: total_mib=0
                if total_mib and total_mib < int(requirement['dag_mib'])+256:
                    raise ValueError(f'VRAM insuficient: {total_mib} MiB disponibili, {requirement["coin"]}/{algo} necesită aproximativ {requirement["dag_mib"]} MiB + 256 MiB rezervă.')
        pool_miners=str(pool.get('miner','')).casefold()
        miner_alias={'srbminer':'srbminer','xmrig':'xmrig','trex':'t-rex','lolminer':'lolminer','gminer':'gminer','rigel':'rigel','teamredminer':'teamredminer','bzminer':'bzminer'}[mid]
        generic_unmineable = ('compatible miner' in pool_miners and mid in ('bzminer','srbminer'))
        if pool.get('id') != 'custom' and miner_alias not in pool_miners and not (mid=='srbminer' and 'srbminer' in pool_miners) and not generic_unmineable:
            raise ValueError(f'Pool-ul nu listează {spec["name"]} ca miner compatibil. Selectează un pool/miner confirmat.')
        binary=_resolve_binary(mid,req.get('binary_path'))
        if not binary: raise ValueError(f'{spec["name"]} nu a fost găsit. Instalează-l din sursa oficială și configurează calea.')
        if Path(binary).name.lower() not in {Path(x).name.lower() for x in spec['executables']}:
            raise ValueError('Executabilul selectat nu corespunde minerului ales; lansare blocată.')
        if req.get('use_ssl') and not (req.get('custom_port') or pool.get('ssl_port')):
            raise ValueError('Pool-ul nu are port TLS confirmat în catalog. Nu presupunem portul SSL.')
        if mid=='xmrig':
            if device != 'CPU':
                raise ValueError('În acest build, XMRig este configurat numai pentru CPU. GPU prin XMRig necesită plugin CUDA/OpenCL separat, care nu este instalat automat.')
            if algo != 'RandomX' and algo not in ('KawPoW','CryptoNight'):
                raise ValueError(f'Algoritmul {algo} nu este activat în profilul XMRig NEXUS.')
            api_port=18080
            cfg={'autosave':False,'background':False,'colors':False,'donate-level':1,'log-file':str(LOG),
                 'pools':[{'url':f'{host}:{int(port)}','user':login,'pass':req.get('password','x'),'keepalive':True,'tls':bool(req.get('use_ssl')),'daemon':False,'algo':'rx/0' if algo=='RandomX' else algo}],
                 'http':{'enabled':True,'host':'127.0.0.1','port':api_port,'access-token':None,'restricted':True}}
            _runtime_config_path=_write_private_xmrig_config(cfg)
            cmd=[binary,'-c',str(_runtime_config_path)]
            _state['api']=f'http://127.0.0.1:{api_port}/1/summary'
        elif mid=='trex':
            if device != 'GPU': raise ValueError('T-Rex este configurat pentru GPU NVIDIA; selectează GPU.')
            api_port=4067
            algo_cli={'KawPoW':'kawpow','Etchash':'etchash'}[algo]
            url=f"stratum+{'ssl' if req.get('use_ssl') else 'tcp'}://{host}:{int(port)}"
            cmd=[binary,'-a',algo_cli,'-o',url,'-u',login,'-p',req.get('password','x'),'--api-bind-http',f'127.0.0.1:{api_port}','--temperature-limit','82','--temperature-start','72']
            _state['api']=f'http://127.0.0.1:{api_port}/summary'
        elif mid=='bzminer':
            if device != 'GPU':
                raise ValueError('Adaptorul BzMiner NEXUS este configurat momentan pentru GPU. RandomX CPU se rulează prin XMRig.')
            algo_cli={'PearlHash':'pearl','PearlPow':'pearl','KawPoW':'kawpow','Etchash':'etchash','NexaPow':'nexa','Autolykos2':'autolykos2'}.get(algo)
            if not algo_cli:
                raise ValueError(f'Algoritmul {algo} nu are încă mapare BzMiner validată în NEXUS.')
            url=f'stratum+{"ssl" if req.get("use_ssl") else "tcp"}://{host}:{int(port)}'
            cmd=[binary,'-a',algo_cli,'-p',url,'-w',login,'--worker',worker,'--pass',req.get('password','x'),'--nvidia','1','--cpu','0']
            # BzMiner provides a local web dashboard on 127.0.0.1:4014 by default; do not expose it externally.
            _state['api']='http://127.0.0.1:4014/'
        elif mid=='lolminer':
            if device != 'GPU':
                raise ValueError('lolMiner este configurat aici pentru GPU.')
            algo_cli={'KawPoW':'KAWPOW','Etchash':'ETCHASH','KHeavyHash':'KHEAVYHASH'}.get(algo)
            if not algo_cli:
                raise ValueError(f'Algoritmul {algo} nu are mapare lolMiner verificată.')
            cmd=[binary,'--algo',algo_cli,'--pool',f'{host}:{int(port)}','--user',login,
                 '--pass',req.get('password','x'),'--tls','on' if req.get('use_ssl') else 'off',
                 '--devices','NVIDIA','--log','on','--templimit','82','--tstart','72']
            _state['api']=None
        elif mid=='gminer':
            if device != 'GPU':
                raise ValueError('GMiner este configurat aici pentru GPU.')
            algo_cli={'KawPoW':'kawpow','Etchash':'etchash','KHeavyHash':'kheavyhash'}.get(algo)
            if not algo_cli:
                raise ValueError(f'Algoritmul {algo} nu are mapare GMiner verificată.')
            cmd=[binary,'--algo',algo_cli,'--server',host,'--port',str(int(port)),
                 '--user',login,'--pass',req.get('password','x'),'--ssl','1' if req.get('use_ssl') else '0',
                 '--watchdog','1','--templimit_mem','82']
            _state['api']=None
        elif mid=='rigel':
            if device != 'GPU':
                raise ValueError('Rigel este configurat aici pentru GPU NVIDIA.')
            algo_cli={'KawPoW':'kawpow','Etchash':'etchash','Autolykos2':'autolykos2',
                      'NexaPow':'nexapow','FishHash':'fishhash','XelisHashv3':'xelishashv3'}.get(algo)
            if not algo_cli:
                raise ValueError(f'Algoritmul {algo} nu are mapare Rigel verificată.')
            url=f'stratum+{"ssl" if req.get("use_ssl") else "tcp"}://{host}:{int(port)}'
            cmd=[binary,'--algorithm',algo_cli,'--url',url,'--user',login,
                 '--pass',req.get('password','x')]
            _state['api']=None
        elif mid=='teamredminer':
            if device != 'GPU':
                raise ValueError('TeamRedMiner este configurat aici pentru GPU AMD; nu îl selecta pentru NVIDIA.')
            algo_cli={'KawPoW':'kawpow','Etchash':'etchash','Verthash':'verthash','Autolykos2':'autolykos2'}.get(algo)
            if not algo_cli:
                raise ValueError(f'Algoritmul {algo} nu are mapare TeamRedMiner verificată.')
            url=f'stratum+{"ssl" if req.get("use_ssl") else "tcp"}://{host}:{int(port)}'
            cmd=[binary,'-a',algo_cli,'-o',url,'-u',login,'-p',req.get('password','x'),
                 '--api_listen=127.0.0.1:4028','--disable_colors']
            _state['api']=None
        else:
            api_port=21550
            url=f'stratum+{"ssl" if req.get("use_ssl") else "tcp"}://{host}:{int(port)}'
            cmd=[binary,'--algorithm',algo.casefold(),'--pool',url,'--wallet',login,
                 '--password',req.get('password','x'),'--tls','true' if req.get('use_ssl') else 'false',
                 '--api-enable','--api-port',str(api_port),'--api-rig-name','NEXUS',
                 '--log-file',str(LOG),'--log-file-mode','0','--extended-log','--enable-workers-ramp-up']
            if device=='CPU': cmd.append('--disable-gpu')
            elif device=='GPU': cmd.append('--disable-cpu')
            if algo=='Verthash': cmd.extend(['--gpu-table-slow-build','--send-stales','false'])
            _state['api']=f'http://127.0.0.1:{api_port}/'
        try:
            LOG.write_text(f'NEXUS launch: {time.strftime("%Y-%m-%d %H:%M:%S")}\nExecutable: {binary}\nMiner: {spec["name"]} | Coin: {pool["coin"]} | Algorithm: {algo} | Pool: {host}:{int(port)}\nArguments: {" ".join(_redact_command_args(cmd[1:]))}\n',encoding='utf-8')
            log_handle=open(LOG,'a',encoding='utf-8',errors='replace')
        except Exception:
            _cleanup_runtime_config()
            raise
        kwargs={'stdout':log_handle,'stderr':subprocess.STDOUT,'cwd':str(RUNTIME)}
        if os.name=='nt': kwargs['creationflags']=getattr(subprocess,'CREATE_NO_WINDOW',0)
        else: kwargs['start_new_session']=True
        if not MINING_PROCESS_ARBITER.acquire(_ARBITER_OWNER):
            log_handle.close()
            _cleanup_runtime_config()
            raise ValueError('O altă sesiune de minare NEXUS este deja activă prin controllerul direct sau HybridSupervisor.')
        try:
            _proc=subprocess.Popen(cmd,**kwargs)
        except Exception as exc:
            log_handle.close()
            _cleanup_runtime_config()
            MINING_PROCESS_ARBITER.release(_ARBITER_OWNER)
            _state.update(status='error',last_error={'code':'MINER_LAUNCH_FAILED','message':type(exc).__name__,'severity':'error','advice':'Verifică executabilul și permisiunile; detaliile sensibile nu sunt incluse în diagnostic.'})
            raise ValueError(f'Nu am putut lansa minerul: {type(exc).__name__}. Detaliile comenzii au fost redactate.')
        MINING_PROCESS_ARBITER.update_processes(_ARBITER_OWNER, [_proc.pid])
        _state.update(status='starting',pid=_proc.pid,miner_id=mid,miner_name=spec['name'],coin=pool['coin'],algorithm=algo,device=device,
                      pool={'name':pool['name'],'host':host,'port':int(port),'tls':bool(req.get('use_ssl'))},started_at=time.time(),last_error=None,last_exit_code=None)
        return status()


def stop() -> dict:
    global _proc
    with LOCK:
        if _proc is None or _proc.poll() is not None:
            _cleanup_runtime_config()
            MINING_PROCESS_ARBITER.release(_ARBITER_OWNER)
            _state.update(status='stopped',pid=None)
            return status()
        try:
            _proc.terminate()
            try: _proc.wait(timeout=8)
            except subprocess.TimeoutExpired: _proc.kill(); _proc.wait(timeout=4)
            if _state.get('miner_id')=='nexus-btc-cpu':
                try:
                    es=_proc.status()
                    if es.get('error'):
                        _state['last_error']={'code':'STRATUM_CPU_ERROR','message':es['error'],'severity':'error','advice':'Verifică endpoint-ul și autentificarea.'}
                except Exception: pass
            _state.update(status='stopped',last_exit_code=_proc.returncode,pid=None)
            MINING_PROCESS_ARBITER.release(_ARBITER_OWNER)
            _cleanup_runtime_config()
        except Exception as exc:
            _state.update(status='error',last_error={'code':'MINER_STOP_FAILED','message':type(exc).__name__,'severity':'error','advice':'Verifică starea procesului; detaliile sensibile nu sunt incluse în diagnostic.'})
            raise ValueError(f'Eroare la oprire: {type(exc).__name__}. Detaliile procesului au fost redactate.')
        return status()


def status() -> dict:
    global _proc
    with LOCK:
        if _proc is not None:
            code=_proc.poll()
            if code is None:
                _state['status']='running'
            else:
                native_error=None
                if _state.get('miner_id')=='nexus-btc-cpu':
                    try: native_error=_proc.status().get('error')
                    except Exception: native_error=None
                _state.update(status='stopped' if code==0 else 'error',pid=None,last_exit_code=code)
                MINING_PROCESS_ARBITER.release(_ARBITER_OWNER)
                _cleanup_runtime_config()
                if code!=0 and not _state.get('last_error'):
                    _state['last_error']={'code':'STRATUM_CPU_ERROR','message':native_error or 'Motorul intern s-a oprit cu eroare.','severity':'error','advice':'Verifică endpoint-ul Stratum V1, TLS și autentificarea.'} if native_error else _diagnose('\n'.join(read_log(40)))
                _proc=None
        if _state.get('status') in ('running','starting') and _state.get('miner_id') == 'nexus-btc-cpu' and _proc is not None:
            engine_state=_proc.status()
            metrics=engine_state.get('metrics',{})
            tail=[f'{e["time"]} {e["message"]}' for e in engine_state.get('events',[])]
            if engine_state.get('error'):
                _state['last_error']={'code':'STRATUM_CPU_ERROR','message':engine_state['error'],'severity':'error','advice':'Verifică host/port/TLS, worker-ul și dacă endpoint-ul acceptă Stratum V1.'}
            _state['status']='running' if engine_state.get('connected') and engine_state.get('authorized') else 'starting'
        else:
            metrics=_metrics() if _state.get('status') in ('running','starting') else {'api_connected':False,'hashrate_hs':None,'hashrate_display':None,'accepted_shares':None,'rejected_shares':None,'gpu':{},'system':{},'raw_api':None}
            tail=read_log(30)
        return {**_state,'uptime_seconds':round(time.time()-_state['started_at'],1) if _state.get('started_at') and _state['status'] in ('running','starting') else 0,
                'metrics':metrics,'log_tail':tail,'diagnosis':_state.get('last_error')}


def read_log(lines: int=80) -> list[str]:
    try:return LOG.read_text(encoding='utf-8',errors='replace').splitlines()[-max(1,min(lines,300)):]
    except Exception:return []


def diagnose() -> dict:
    inv=inventory(); st=status(); log='\n'.join(st['log_tail'])
    errs=[]
    if st.get('last_error'): errs.append(st['last_error'])
    elif log:
        for line in log.splitlines():
            low=line.lower()
            if any(k in low for k in ('error','failed','rejected','not found','unsupported')): errs.append(_diagnose(line))
    return {'timestamp':time.time(),'miner_inventory':inv['miners'],'active_miner_processes':inv['processes'],
            'managed_miner':st,'errors':errs[-20:],'system':st.get('metrics',{}).get('system'),
            'recommendations':['Verifică întotdeauna adresa și rețeaua wallet înainte de mining.','Nu folosi intensitate maximă fără monitorizarea temperaturii și consumului.','Hashrate-ul pool poate avea întârziere și poate diferi de cel local.']}
