"""Read-only pool account connectors. Credentials are request-scoped and never persisted."""
from __future__ import annotations
import hashlib, hmac, json, time, urllib.parse, urllib.request, re
from typing import Any


def unmineable_signature(method: str, path: str, query: str, timestamp_ms: str, body: bytes, secret: str) -> str:
    body_hash = hashlib.sha256(body or b'').hexdigest()
    payload = '\n'.join([method.upper(), path, query or '', timestamp_ms, body_hash])
    return hmac.new(secret.encode('utf-8'), payload.encode('utf-8'), hashlib.sha256).hexdigest()


def unmineable_account_stats(coin: str, api_key: str, api_secret: str, base_url: str = 'https://api.unmineable.dev/v1', timeout: float = 8.0) -> dict[str, Any]:
    if not isinstance(coin, str) or not coin.isalnum() or not 2 <= len(coin) <= 12:
        raise ValueError('Ticker unMineable invalid.')
    if not api_key or len(api_key) > 512 or not api_secret or len(api_secret) > 512:
        raise ValueError('Sunt necesare API key și API secret unMineable. Folosește numai token read-only.')
    if not base_url.startswith('https://api.unmineable.dev/v1'):
        raise ValueError('Host API nepermis; se acceptă numai api.unmineable.dev/v1.')

    def get(path: str) -> Any:
        timestamp = str(int(time.time() * 1000))
        signature = unmineable_signature('GET', path, '', timestamp, b'', api_secret)
        headers = {'Accept':'application/json','User-Agent':'NEXUS-MASTER/0.10.6',
                   'x-user-api-key':api_key,'x-user-api-timestamp':timestamp,'x-user-api-signature':signature}
        request = urllib.request.Request(base_url + path, headers=headers, method='GET')
        with urllib.request.urlopen(request, timeout=max(2.0, min(timeout, 12.0))) as response:
            return json.loads(response.read().decode('utf-8'))

    profile = get('/me')
    alias_ready = bool(profile.get('alias') or profile.get('username')) if isinstance(profile, dict) else False
    if not alias_ready:
        raise RuntimeError('unMineable raportează că aliasul implicit nu este configurat. Creează aliasul în cont, apoi repetă verificarea.')
    stats = get('/assets/' + urllib.parse.quote(coin.upper(), safe='') + '/stats')
    payments = get('/payments?coin=' + urllib.parse.quote(coin.upper(), safe='') + '&page=1')
    return {'provider':'unMineable','coin':coin.upper(),'profile':profile,'stats':stats,'payments':payments,
            'read_only':True,'credentials_persisted':False,
            'source':'https://unmineable.com/api','status':'live_api_response'}



def _safe_get_json(url: str, headers: dict[str,str] | None = None, timeout: float = 8.0) -> Any:
    if not url.startswith('https://'):
        raise ValueError('Conectorul acceptă doar HTTPS.')
    req = urllib.request.Request(url, headers={'Accept':'application/json','User-Agent':'NEXUS-MASTER/0.10.6', **(headers or {})}, method='GET')
    with urllib.request.urlopen(req, timeout=max(2.0,min(float(timeout),12.0))) as response:
        raw=response.read(2_000_000)
        return json.loads(raw.decode('utf-8'))


def kryptex_account_stats(coin: str, address: str, timeout: float = 8.0) -> dict[str,Any]:
    """Public read-only Kryptex Pool API. Only GET endpoints are called."""
    if not isinstance(coin,str) or not re.fullmatch(r'[A-Za-z0-9]{2,12}',coin):
        raise ValueError('Ticker Kryptex invalid.')
    if not isinstance(address,str) or not 3 <= len(address) <= 256 or any(c.isspace() for c in address):
        raise ValueError('Adresa/username invalidă.')
    c=coin.lower(); a=urllib.parse.quote(address,safe='')
    base='https://pool.kryptex.com'
    paths={
      'balance':f'/{c}/api/v1/miner/balance/{a}',
      'payouts':f'/{c}/api/v1/miner/payouts/{a}',
      'payout_stats':f'/{c}/api/v1/miner/payouts/{a}/stats',
      'workers':f'/{c}/api/v3/miner/workers/{a}',
    }
    result={k:_safe_get_json(base+v,timeout=timeout) for k,v in paths.items()}
    return {'provider':'Kryptex Pool','coin':coin.upper(),'address_redacted':True,'read_only':True,
            'credential_storage':'none; public GET endpoints','status':'live_api_response','data':result,
            'source':'https://pool.kryptex.com/en/api'}


def braiins_account_stats(username: str, api_token: str, timeout: float = 8.0) -> dict[str,Any]:
    """Read-only Braiins BTC pool API; token is passed as Pool-Auth-Token and never stored."""
    if not isinstance(username,str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}',username):
        raise ValueError('Username Braiins invalid.')
    if not isinstance(api_token,str) or not 8 <= len(api_token) <= 1024:
        raise ValueError('Token Braiins invalid.')
    headers={'Pool-Auth-Token':api_token}
    base='https://pool.braiins.com/accounts'
    urls={
      'profile':base+'/profile/json/btc/',
      'workers':base+'/workers/json/btc',
    }
    result={k:_safe_get_json(u,headers=headers,timeout=timeout) for k,u in urls.items()}
    # Match only requested user in returned data. Avoid disclosing other workers.
    prof=result.get('profile') or {}
    if prof.get('username') and prof.get('username') != username:
        raise RuntimeError('API Braiins a returnat alt username decât cel solicitat.')
    workers=(result.get('workers') or {}).get('btc',{}).get('workers',{})
    result['workers']={k:v for k,v in workers.items() if k == username or k.startswith(username+'.')}
    return {'provider':'Braiins Pool','coin':'BTC','username':username,'read_only':True,
            'credential_storage':'none; request-scoped API token','status':'live_api_response','data':result,
            'source':'https://academy.braiins.com/braiins-pool/monitoring'}

def connector_catalog() -> list[dict[str, Any]]:
    return [
        {'provider':'2Miners','available':True,'auth':'public wallet address','scope':'read-only account API','fields':['balance','immature','paid','24h reward','hashrate','workers','payments'],'status':'live connector'},
        {'provider':'unMineable','available':True,'auth':'API key + API secret; HMAC-SHA256, read-only scope','scope':'GET only','fields':['assets','asset stats','payments'],'status':'live read-only connector'},
        {'provider':'Kryptex Pool','available':True,'auth':'public address/username','scope':'GET only','fields':['balance','payouts','payout stats','workers'],'status':'live public GET connector'},
        {'provider':'Braiins Pool','available':True,'auth':'API token with web API access; Pool-Auth-Token header','scope':'read endpoints only','fields':['profile','balance','today reward','hashrate','shares','workers'],'status':'live read-only token connector'},
        {'provider':'F2Pool','available':False,'auth':'API token; create restricted permissions and IP whitelist','scope':'connector pending exact route/schema validation','fields':['hashrate','workers','payments'],'status':'catalogued; connector not enabled to avoid unsafe broad token permissions'},
        {'provider':'ViaBTC','available':False,'auth':'account/app','scope':'no read-only connector implemented','fields':['workers','earnings','payouts'],'status':'official dashboard only'},
    ]
