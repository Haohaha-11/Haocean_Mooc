#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${HAOCEAN_REPO_URL:-https://github.com/Haohaha-11/Haocean_Mooc.git}"
REF="${HAOCEAN_VERSION:-main}"
INSTALL_DIR="${HAOCEAN_INSTALL_DIR:-$HOME/.haocean-cli}"
BIN_DIR="${HAOCEAN_BIN_DIR:-$HOME/.local/bin}"
VENV_DIR="$INSTALL_DIR/venv"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required. Install Python 3.10+ first." >&2
  exit 1
fi

python3 - <<'PY'
import sys
if sys.version_info < (3, 10):
    raise SystemExit("Python 3.10+ is required.")
PY

mkdir -p "$INSTALL_DIR" "$BIN_DIR"

if ! python3 -m venv "$VENV_DIR" 2>/tmp/haocean_venv_error.log; then
  cat /tmp/haocean_venv_error.log >&2
  echo "Failed to create virtualenv. On Debian/Ubuntu, install python3-venv." >&2
  exit 1
fi

"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install --upgrade \
  "git+$REPO_URL@$REF#subdirectory=module_a_client"

AI_BIN="$BIN_DIR/haocean"
if [ -e "$AI_BIN" ] && [ ! -L "$AI_BIN" ]; then
  echo "Skipped helper command because $AI_BIN already exists."
elif [ -L "$AI_BIN" ] && [ "$(readlink "$AI_BIN")" != "$VENV_DIR/bin/haocean" ]; then
  echo "Skipped helper command because $AI_BIN points to another target."
else
  ln -sf "$VENV_DIR/bin/haocean" "$AI_BIN"
fi
ln -sf "$VENV_DIR/bin/haocean-student" "$BIN_DIR/haocean-student"

echo "Haocean student CLI installed."
echo "Command: $BIN_DIR/haocean-student"
echo "AI help: $BIN_DIR/haocean ai-help"
echo
echo "If 'haocean-student' is not found, add this to your shell profile:"
echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
echo
echo "Next:"
echo "  haocean-student setup"
echo "  haocean-student login"
echo "  haocean ai-help"
