#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")"
if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required. Install Docker Desktop/Engine with Compose v2." >&2
  exit 2
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose v2 is required." >&2
  exit 2
fi
python3 --version >/dev/null
# Recreate only this disposable local lab. No public network or funds are used.
docker compose down --remove-orphans >/dev/null 2>&1 || true
docker compose up -d
python3 nexus_v05_integration.py
