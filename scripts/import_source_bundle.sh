#!/usr/bin/env bash
set -euo pipefail

ZIP_PATH="${1:-NEXUS_MASTER_0.10.25_SOURCE_IMPORT_BUNDLE_WALLET_MINING.zip}"
EXPECTED_SHA256="642c882557993a86db21583e8efaef359dd01f8f9b28440462ba8a723c924d50"
EXPECTED_ENTRIES=520
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

python - "$ZIP_PATH" "$EXPECTED_ENTRIES" <<'PY'
import hashlib, json, sys, zipfile
path, expected = sys.argv[1], int(sys.argv[2])
forbidden_dirs = {"__pycache__", ".git", ".mypy_cache", ".pytest_cache",
                  ".ruff_cache", "build", "data", "results", "runtime"}
forbidden_suffixes = {".pyc", ".pyo", ".sqlite", ".sqlite3", ".db",
                      ".log", ".so", ".dll", ".exe", ".bin"}
with zipfile.ZipFile(path) as z:
    infos = [i for i in z.infolist() if not i.is_dir()]
    if len(infos) != expected:
        raise SystemExit(f"ERROR: expected {expected} ZIP entries, found {len(infos)}")
    names = set()
    for item in infos:
        name = item.filename.replace("\\\\", "/")
        parts = name.split("/")
        if name.startswith("/") or any(p in {"", ".", ".."} for p in parts):
            raise SystemExit(f"ERROR: unsafe archive path: {item.filename}")
        if name != "NEXUS_SOURCE_IMPORT_MANIFEST.json":
            if not name.startswith("NEXUS_MASTER_0.10.25/"):
                raise SystemExit(f"ERROR: unexpected top-level path: {name}")
            rel = "/".join(parts[1:])
            if forbidden_dirs.intersection(parts) or any(rel.lower().endswith(s) for s in forbidden_suffixes):
                raise SystemExit(f"ERROR: generated/runtime artifact in source bundle: {name}")
        names.add(name)
    manifest = json.loads(z.read("NEXUS_SOURCE_IMPORT_MANIFEST.json"))
    listed = {f["path"]: f for f in manifest["files"]}
    actual = {n[len("NEXUS_MASTER_0.10.25/"):] for n in names
              if n.startswith("NEXUS_MASTER_0.10.25/")}
    if actual != set(listed) or len(listed) != expected - 1:
        raise SystemExit("ERROR: manifest inventory does not match ZIP contents")
    for rel, item in listed.items():
        data = z.read("NEXUS_MASTER_0.10.25/" + rel)
        if len(data) != item["size"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
            raise SystemExit(f"ERROR: file integrity mismatch: {rel}")
print(f"Archive, safe paths and {expected - 1} source-file hashes verified")
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
echo "Source imported into $DEST/; repository files outside that directory were not changed."
echo "Next: apply reviewed patches, compile, install development dependencies and run the complete test suite."
