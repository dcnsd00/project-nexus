from __future__ import annotations
import hashlib, json, os, re, shutil, tempfile, urllib.request, zipfile
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
INSTALL_ROOT = ROOT / 'miners'
INSTALL_ROOT.mkdir(parents=True, exist_ok=True)
UA = 'NEXUS-Miner-Pack/0.10.1 (+local installer)'

# GitHub repositories are the upstream project release repositories. Asset matching is
# deliberately conservative: only Windows x64 ZIP packages are accepted.
SOURCES: dict[str, dict[str, Any]] = {
    'xmrig': {'name':'XMRig','repo':'xmrig/xmrig','asset_patterns':[r'windows-x64\.zip$', r'windows-gcc-x64\.zip$'], 'exe':['xmrig.exe'], 'official':'https://github.com/xmrig/xmrig/releases'},
    'srbminer': {'name':'SRBMiner-MULTI','repo':'doktor83/SRBMiner-Multi','asset_patterns':[r'win64\.zip$'], 'exe':['SRBMiner-MULTI.exe'], 'official':'https://github.com/doktor83/SRBMiner-Multi/releases'},
    'trex': {'name':'T-Rex','repo':'trexminer/T-Rex','asset_patterns':[r'win.*\.zip$',r'windows.*\.zip$'], 'exe':['t-rex.exe'], 'official':'https://github.com/trexminer/T-Rex/releases'},
    'lolminer': {'name':'lolMiner','repo':'Lolliedieb/lolMiner-releases','asset_patterns':[r'win64.*\.zip$',r'win.*\.zip$'], 'exe':['lolMiner.exe'], 'official':'https://github.com/Lolliedieb/lolMiner-releases/releases'},
    'gminer': {'name':'GMiner','repo':'develsoftware/GMinerRelease','asset_patterns':[r'windows64\.zip$',r'windows.*\.zip$'], 'exe':['miner.exe'], 'official':'https://github.com/develsoftware/GMinerRelease/releases'},
    'rigel': {'name':'Rigel','repo':'rigelminer/rigel','asset_patterns':[r'win.*\.zip$',r'windows.*\.zip$'], 'exe':['rigel.exe'], 'official':'https://github.com/rigelminer/rigel/releases'},
    'bzminer': {'name':'BzMiner','repo':'bzminer/bzminer','asset_patterns':[r'bzminer_v[0-9.]+_windows\.zip$'], 'exe':['bzminer.exe'], 'official':'https://github.com/bzminer/bzminer/releases'},
    # TeamRedMiner's official distribution is not currently wired to a verified GitHub
    # release API. Keep a direct official page, never use third-party mirrors.
    'teamredminer': {'name':'TeamRedMiner','repo':None,'asset_patterns':[], 'exe':['teamredminer.exe'], 'official':'https://www.teamredminer.com/'},
}


def _request(url: str, timeout: int = 25) -> bytes:
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept':'application/vnd.github+json'})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()


def list_sources() -> list[dict]:
    rows=[]
    for mid, src in SOURCES.items():
        installed = _installed(mid)
        rows.append({'id':mid,'name':src['name'],'repo':src['repo'],'official_url':src['official'],
                     'managed_path':str(installed) if installed else None,'installed':bool(installed),
                     'automatic_download':bool(src['repo']),
                     'status':'installed' if installed else ('official_page_only' if not src['repo'] else 'not_installed')})
    return rows


def _installed(miner_id: str) -> Path | None:
    src=SOURCES.get(miner_id)
    if not src: return None
    base=INSTALL_ROOT/miner_id
    for exe in src['exe']:
        matches=list(base.rglob(exe)) if base.exists() else []
        if matches: return matches[0]
    return None


def latest_release(miner_id: str) -> dict:
    src=SOURCES.get(miner_id)
    if not src: raise ValueError('Miner necunoscut.')
    if not src['repo']:
        return {'id':miner_id,'name':src['name'],'automatic_download':False,'official_url':src['official'],
                'message':'Acest proiect nu are încă un flux automat de descărcare verificabil configurat în NEXUS. Deschide pagina oficială.'}
    url=f"https://api.github.com/repos/{src['repo']}/releases/latest"
    data=json.loads(_request(url))
    assets=data.get('assets') or []
    chosen=None
    for asset in assets:
        name=asset.get('name','')
        if any(re.search(pat,name,re.I) for pat in src['asset_patterns']):
            chosen=asset; break
    if not chosen:
        raise ValueError(f"Release-ul {data.get('tag_name')} nu conține un pachet Windows x64 recunoscut. Nu descarc un asset nepotrivit.")
    return {'id':miner_id,'name':src['name'],'version':data.get('tag_name') or data.get('name'),
            'release_url':data.get('html_url') or src['official'],'asset_name':chosen['name'],
            'download_url':chosen['browser_download_url'],'size_bytes':chosen.get('size'),
            'asset_api_url':chosen.get('url'),'automatic_download':True,
            'upstream_digest':chosen.get('digest'),'published_at':data.get('published_at'),
            'source_repo':src['repo']}


def _safe_extract_zip(zip_path: Path, destination: Path, max_files: int=5000, max_unpacked: int=2_000_000_000) -> list[str]:
    extracted=[]; total=0
    with zipfile.ZipFile(zip_path) as zf:
        infos=zf.infolist()
        if len(infos)>max_files: raise ValueError('Arhiva conține prea multe fișiere.')
        for info in infos:
            raw=info.filename.replace('\\','/')
            p=PurePosixPath(raw)
            if p.is_absolute() or '..' in p.parts or (p.parts and ':' in p.parts[0]):
                raise ValueError('Arhiva conține o cale nesigură; extracția a fost anulată.')
            total += info.file_size
            if total>max_unpacked: raise ValueError('Arhiva depășește limita de extracție de 2 GB.')
        for info in infos:
            if info.is_dir(): continue
            rel=PurePosixPath(info.filename.replace('\\','/'))
            target=destination.joinpath(*rel.parts)
            target.parent.mkdir(parents=True,exist_ok=True)
            with zf.open(info) as src, open(target,'wb') as dst:
                shutil.copyfileobj(src,dst)
            extracted.append(str(target.relative_to(destination)))
    return extracted


def install(miner_id: str) -> dict:
    src=SOURCES.get(miner_id)
    if not src: raise ValueError('Miner necunoscut.')
    release=latest_release(miner_id)
    if not release.get('automatic_download'):
        return release
    max_size=1_000_000_000
    size=release.get('size_bytes')
    if size and size>max_size: raise ValueError('Pachetul depășește limita de 1 GB.')
    with tempfile.TemporaryDirectory(prefix='nexus-miner-') as td:
        archive=Path(td)/'miner.zip'
        digest=hashlib.sha256(); downloaded=0
        req=urllib.request.Request(release['download_url'],headers={'User-Agent':UA})
        with urllib.request.urlopen(req,timeout=60) as response, open(archive,'wb') as out:
            while True:
                chunk=response.read(1024*1024)
                if not chunk: break
                downloaded+=len(chunk)
                if downloaded>max_size: raise ValueError('Descărcarea a depășit limita de 1 GB.')
                digest.update(chunk); out.write(chunk)
        sha=digest.hexdigest()
        upstream=release.get('upstream_digest')
        integrity='sha256_verified_against_upstream' if upstream and upstream.lower() in ('sha256:'+sha).lower() else ('local_sha256_only' if not upstream else 'upstream_digest_mismatch')
        if integrity=='upstream_digest_mismatch': raise ValueError('SHA-256 diferă de digest-ul publicat de upstream. Instalarea a fost blocată.')
        staging=Path(td)/'extracted'; staging.mkdir()
        extracted=_safe_extract_zip(archive,staging)
        exe_found=[x for x in extracted if Path(x).name.lower() in {e.lower() for e in src['exe']}]
        if not exe_found: raise ValueError('Arhiva nu conține executabilul așteptat. Nu instalez un pachet cu structură neașteptată.')
        version=re.sub(r'[^A-Za-z0-9._-]+','_',str(release.get('version') or 'latest')).strip('._') or 'latest'
        if version in {'.','..'}: raise ValueError('Versiune release invalidă.')
        final=INSTALL_ROOT/miner_id/version
        final.parent.mkdir(parents=True,exist_ok=True)
        if final.exists(): shutil.rmtree(final)
        shutil.copytree(staging,final)
        exe_path=next(final/x for x in exe_found)
        manifest={'miner_id':miner_id,'name':src['name'],'version':release.get('version'),
                  'source_repo':src['repo'],'release_url':release.get('release_url'),
                  'asset_name':release.get('asset_name'),'archive_sha256':sha,'integrity':integrity,
                  'downloaded_bytes':downloaded,'installed_executable':str(exe_path),
                  'installed_at':__import__('datetime').datetime.now().astimezone().isoformat(),
                  'note':'NEXUS a extras executabilul; nu l-a rulat. Verifică semnătura și antivirusul înainte de START.'}
        (final/'nexus-install-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        return {'ok':True,**manifest}
