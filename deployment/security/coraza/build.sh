#!/usr/bin/env bash
set -euo pipefail

CADDY_VERSION="v2.11.9"
CORAZA_CADDY_VERSION="v2.6.2"
XCADDY_VERSION="v0.4.7"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TOOLS_BIN="$SCRIPT_DIR/.tools/bin"
OUTPUT="$SCRIPT_DIR/caddy"

if ! command -v go >/dev/null 2>&1; then
  echo "Go 1.26.0 or newer is required." >&2
  exit 1
fi

GO_VERSION="$(go env GOVERSION | sed 's/^go//')"
if [[ "$(printf '%s\n' "1.26.0" "$GO_VERSION" | sort -V | head -n1)" != "1.26.0" ]]; then
  echo "Go 1.26.0 or newer is required; found $GO_VERSION." >&2
  exit 1
fi

mkdir -p "$TOOLS_BIN"
mkdir -p "$SCRIPT_DIR/logs"
GOBIN="$TOOLS_BIN" go install "github.com/caddyserver/xcaddy/cmd/xcaddy@$XCADDY_VERSION"
"$TOOLS_BIN/xcaddy" build "$CADDY_VERSION" \
  --with "github.com/corazawaf/coraza-caddy/v2@$CORAZA_CADDY_VERSION" \
  --output "$OUTPUT"

"$OUTPUT" list-modules | grep -qx "http.handlers.waf"
"$OUTPUT" validate --config "$SCRIPT_DIR/Caddyfile" --adapter caddyfile

echo "Build and Caddyfile validation succeeded: $OUTPUT"
echo "WAF remains in DetectionOnly mode and binds only to 127.0.0.1:8780."
