#!/usr/bin/env sh
set -eu
python -m pytest -q
python nexus_wallet_benchmark.py --iterations 100 --output results
