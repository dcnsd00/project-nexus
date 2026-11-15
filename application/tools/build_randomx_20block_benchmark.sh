#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/vendor/randomx-1.2.3"
BUILD="$ROOT/build/randomx"
OUT="$BUILD/randomx-20block-benchmark"
if [[ ! -f "$BUILD/librandomx.a" ]]; then
  "$ROOT/tools/build_randomx_benchmark.sh"
fi
g++ -O3 -std=c++11 -march=native -I"$SRC/src" \
  "$ROOT/tools/randomx_20block_benchmark.cpp" "$BUILD/librandomx.a" -pthread -o "$OUT"
printf '\\nBuilt: %s\\n' "$OUT"
