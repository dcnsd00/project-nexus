#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
python - <<'PY'
import json, urllib.request
url='http://127.0.0.1:8765/api/shutdown'
req=urllib.request.Request(url, data=b'{}', headers={'Content-Type':'application/json'}, method='POST')
try:
    with urllib.request.urlopen(req, timeout=2) as r:
        print('Oprire cerută:', r.status)
except Exception as e:
    print('Serverul nu răspunde sau este deja oprit:', e)
PY
