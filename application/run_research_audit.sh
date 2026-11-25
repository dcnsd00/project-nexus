#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
RESEARCH="$ROOT/research/sha2_independent"
export PYTHONPATH="$ROOT:$RESEARCH"
(cd "$RESEARCH" && python3 research_main.py test)
(cd "$RESEARCH" && python3 research_main.py verify --out-dir "$RESEARCH/results")
echo "Independent SHA-2 research audit complete. SAT solving is skipped unless python-sat is installed."
