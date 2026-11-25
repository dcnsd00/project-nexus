#!/usr/bin/env bash
set -euo pipefail
SOURCE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${NEXUS_INSTALL_DIR:-$HOME/.local/share/nexus-master}"
DESKTOP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is required (3.11 or newer)." >&2
  exit 1
fi
PYTHON_VERSION="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)'; then
  echo "Python 3.11 or newer is required; found $PYTHON_VERSION." >&2
  exit 1
fi

mkdir -p "$INSTALL_DIR" "$DESKTOP_DIR"
cp -a "$SOURCE_DIR/." "$INSTALL_DIR/"
python3 -m venv "$INSTALL_DIR/.venv"
"$INSTALL_DIR/.venv/bin/python" -m pip install --upgrade pip
"$INSTALL_DIR/.venv/bin/python" -m pip install -r "$INSTALL_DIR/requirements.txt" -r "$INSTALL_DIR/requirements-edge.txt"

cat > "$INSTALL_DIR/START_NEXUS_LINUX.sh" <<'LAUNCHER'
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec "$ROOT/.venv/bin/python" "$ROOT/START_NEXUS_LINUX.py" "$@"
LAUNCHER
chmod +x "$INSTALL_DIR/START_NEXUS_LINUX.sh"

cat > "$DESKTOP_DIR/nexus-master.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=NEXUS MASTER
Comment=Local-first NEXUS Control Center
Exec="$INSTALL_DIR/START_NEXUS_LINUX.sh"
Terminal=true
Categories=Development;Utility;
DESKTOP
chmod 644 "$DESKTOP_DIR/nexus-master.desktop"

echo "NEXUS MASTER installed at: $INSTALL_DIR"
echo "Launch from the application menu or run: $INSTALL_DIR/START_NEXUS_LINUX.sh"
