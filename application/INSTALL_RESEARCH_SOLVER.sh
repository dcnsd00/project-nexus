#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
PY="$ROOT/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "NEXUS .venv is missing. Run INSTALL_NEXUS_LINUX.sh first." >&2
  exit 1
fi
"$PY" -m pip install -r "$ROOT/requirements-research.txt"
echo "Optional SAT + SMT solvers installed. Restart NEXUS to expose the SAT/SMT research backends."
