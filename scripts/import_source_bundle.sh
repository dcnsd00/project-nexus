#!/usr/bin/env bash
set -euo pipefail

ZIP_PATH="${1:-NEXUS_MASTER_0.10.25_SOURCE_IMPORT_BUNDLE.zip}"
EXPECTED_SHA256="f4774e21854387f38152ae969a84b07d8dc2fec2ef21d120923bf82738ca1f7f"
EXPECTED_FILES=514
DEST="application"

if [[ ! -f "$ZIP_PATH" ]]; then
  echo "ERROR: bundle not found: $ZIP_PATH" >&2
  exit 2
fi
ACTUAL_SHA256="$(sha256sum "$ZIP_PATH" | awk '{print $1}')"
if [[ "$ACTUAL_SHA256" != "$EXPECTED_SHA256" ]]; then
  echo "ERROR: SHA-256 mismatch. Expected $EXPECTED_SHA256, got $ACTUAL_SHA256" >&2
  exit 3
fi
if [[ -e "$DEST" ]]; then
  echo "ERROR: $DEST already exists; refusing to overwrite." >&2
  exit 4
fi

python - "$ZIP_PATH" "$EXPECTED_FILES" <<'PY'
import sys, zipfile
path, expected = sys.argv[1], int(sys.argv[2])
with zipfile.ZipFile(path) as z:
    files = [i for i in z.infolist() if not i.is_dir()]
    if len(files) != expected:
        raise SystemExit(f"ERROR: expected {expected} files, found {len(files)}")
    for item in z.infolist():
        name = item.filename.replace("\\", "/")
        if name.startswith("/") or any(part == ".." for part in name.split("/")):
            raise SystemExit(f"ERROR: unsafe archive path: {item.filename}")
        if item.is_dir():
            continue
        if name != "NEXUS_SOURCE_IMPORT_MANIFEST.json" and not name.startswith("NEXUS_MASTER_0.10.25/"):
            raise SystemExit(f"ERROR: unexpected top-level path: {name}")
print(f"Archive structure verified: {expected} files")
PY

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
unzip -q "$ZIP_PATH" 'NEXUS_MASTER_0.10.25/*' -d "$TMP_DIR"
mkdir "$DEST"
cp -a "$TMP_DIR/NEXUS_MASTER_0.10.25/." "$DEST/"
if [[ ! -f "$DEST/nexus_master.py" || ! -d "$DEST/tests" || ! -f "$DEST/VERSION.json" ]]; then
  echo "ERROR: required NEXUS source files are missing after extraction." >&2
  rm -rf "$DEST"
  exit 5
fi
echo "Source imported into $DEST/."
echo "Review docs/SOURCE_IMPORT_SECURITY_SCAN_2026-11-12.md before pushing."
echo "Next: python -m compileall -q $DEST && cd $DEST && python -m pytest -q --disable-warnings --maxfail=1"
echo "Then inspect git status, commit on integration/import-0.10.25, and open a pull request."
