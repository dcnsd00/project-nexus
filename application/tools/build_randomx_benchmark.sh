#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/vendor/randomx-1.2.3"
BUILD="$ROOT/build/randomx"
cmake -S "$SRC" -B "$BUILD" -DARCH=native -DCMAKE_BUILD_TYPE=Release
cmake --build "$BUILD" --config Release --parallel
printf '\\nBuilt: %s\\n' "$BUILD/randomx-benchmark"
