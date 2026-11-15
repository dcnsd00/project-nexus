#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
AUDIT_TMP="$(mktemp -d "${TMPDIR:-/tmp}/nexus-audit-XXXXXX")"
trap 'rm -rf "$AUDIT_TMP"' EXIT
export PYTHONPATH="$ROOT:$ROOT/core/PROJECT-NEXUS-LOCAL"
export NEXUS_DB="$AUDIT_TMP/nexus_master.db"
export NEXUS_INTEL_DB="$AUDIT_TMP/nexus_intelligence.db"
export NEXUS_WALLET_DB="$AUDIT_TMP/nexus_wallets.db"
export NEXUS_SHA2_RESULTS_DIR="$AUDIT_TMP/sha2_results"
python3 -m compileall -q "$ROOT"
python3 "$ROOT/tools_check_dashboard_js.py" "$ROOT"
pytest -q "$ROOT/tests"
python3 "$ROOT/tools_audit_vault.py" "$ROOT/data/nexus_wallets.db"
MM="$ROOT/adapters/multiminer_x/MULTIMINER_X_v1.0"
(cd "$MM" && PYTHONPATH="$MM" pytest -q tests)
FS="$ROOT/adapters/fieldstation/crypto_fieldstation"
(cd "$FS" && PYTHONPATH="$FS" pytest -q tests)
W="$ROOT/modules/wallet_benchmark"
(cd "$W" && pytest -q tests)
(cd "$W/v05" && pytest -q test_v05_unit.py)
if [[ "${NEXUS_RUN_NATIVE_BENCHMARK:-0}" == "1" ]]; then
  echo "Running optional native SHA-256d benchmark (resource-intensive)…"
  (cd "$MM" && python3 research/run_benchmarks.py > "$ROOT/results/sha256d_benchmark_stdout.json")
else
  echo "Native SHA-256d benchmark skipped to keep the default audit resource-bounded. Set NEXUS_RUN_NATIVE_BENCHMARK=1 to run it separately."
fi
echo "NEXUS offline audit complete. Blockchain daemons, SAT solver and GPU/pool mining tests require separate runtime checks."
