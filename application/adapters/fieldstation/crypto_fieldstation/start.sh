#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if ! command -v python >/dev/null 2>&1; then
  echo "Python nu este instalat. În Termux rulează: pkg update && pkg install python"
  exit 1
fi
if [ -f .fieldstation.pid ] && kill -0 "$(cat .fieldstation.pid)" 2>/dev/null; then
  echo "Crypto Fieldstation pare deja pornit (PID $(cat .fieldstation.pid))."
  echo "Deschide în browser: http://127.0.0.1:8765"
  exit 0
fi
python app.py --open-browser &
PID=$!
echo "$PID" > .fieldstation.pid
cleanup() {
  rm -f .fieldstation.pid
}
trap cleanup EXIT
wait "$PID"
