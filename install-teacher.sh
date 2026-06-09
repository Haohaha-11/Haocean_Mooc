#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${HAOCEAN_REPO_URL:-https://github.com/Haohaha-11/Haocean_Mooc.git}"
REF="${HAOCEAN_VERSION:-main}"
RAW_BASE="${HAOCEAN_RAW_BASE:-https://raw.githubusercontent.com/Haohaha-11/Haocean_Mooc/${REF}}"
INSTALL_DIR="${HAOCEAN_TEACHER_INSTALL_DIR:-$HOME/.haocean-teacher-cli}"
BIN_DIR="${HAOCEAN_BIN_DIR:-$HOME/.local/bin}"
DATA_DIR="${HAOCEAN_TEACHER_HOME:-$HOME/.haocean-teacher}"
DOC_DIR="$DATA_DIR/docs"
VENV_DIR="$INSTALL_DIR/venv"
SCRIPT_DIR=""
SCRIPT_SOURCE="${BASH_SOURCE-}"
if [ -n "$SCRIPT_SOURCE" ] && [ -f "$SCRIPT_SOURCE" ]; then
  SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_SOURCE")" >/dev/null 2>&1 && pwd)"
fi

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

if ! python3 -m venv "$VENV_DIR" 2>/tmp/haocean_teacher_venv_error.log; then
  cat /tmp/haocean_teacher_venv_error.log >&2
  echo "Failed to create virtualenv. On Debian/Ubuntu, install python3-venv." >&2
  exit 1
fi

"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install --upgrade --force-reinstall --no-cache-dir \
  "git+$REPO_URL@$REF#subdirectory=module_c_controller"

mkdir -p "$DOC_DIR"
if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/docs/teacher_usage_guide.md" ]; then
  cp "$SCRIPT_DIR/docs/teacher_usage_guide.md" "$DOC_DIR/teacher_usage_guide.md"
elif ! curl -fsSL "$RAW_BASE/docs/teacher_usage_guide.md" -o "$DOC_DIR/teacher_usage_guide.md"; then
  echo "Warning: failed to download teacher usage guide." >&2
fi

ln -sf "$VENV_DIR/bin/haocean-teacher" "$BIN_DIR/haocean-teacher"

echo "Haocean teacher CLI installed."
echo "Command: $BIN_DIR/haocean-teacher"
echo "Guide  : $DOC_DIR/teacher_usage_guide.md"
echo
echo "If 'haocean-teacher' is not found, add this to your shell profile:"
echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
echo
echo "Next:"
echo "  haocean-teacher setup"
echo "  haocean-teacher login"
echo "  haocean-teacher guide"
echo
echo "Uninstall old local CLI install:"
echo "  curl -fsSL https://raw.githubusercontent.com/Haohaha-11/Haocean_Mooc/${REF}/uninstall.sh | bash"
