#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
command -v python3 >/dev/null || { echo 'Python 3 is required.' >&2; exit 1; }
python3 - <<'PY'
import sys
if sys.version_info < (3,11): raise SystemExit('Python 3.11+ is required.')
PY
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt -r requirements-desktop.txt
mkdir -p "$HOME/.local/share/applications"
cat > "$HOME/.local/share/applications/nexus.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=NEXUS Control Center
Comment=NEXUS local mining and research control plane
Exec="$ROOT/.venv/bin/python" "$ROOT/START_NEXUS_DESKTOP.pyw"
Path=$ROOT
Terminal=false
Categories=Development;Science;
DESKTOP
chmod +x "$HOME/.local/share/applications/nexus.desktop"
echo 'NEXUS Linux Python/pywebview environment installed.'
echo 'If GUI dependencies are unavailable, run: .venv/bin/uvicorn nexus_master:app --host 127.0.0.1 --port 8765'
