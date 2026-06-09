#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${HAOCEAN_REPO_URL:-https://github.com/Haohaha-11/Haocean_Mooc.git}"
REF="${HAOCEAN_VERSION:-main}"
RAW_BASE="${HAOCEAN_RAW_BASE:-https://raw.githubusercontent.com/Haohaha-11/Haocean_Mooc/${REF}}"
BIN_DIR="${HAOCEAN_BIN_DIR:-$HOME/.local/bin}"
STUDENT_DATA_DIR="${HAOCEAN_HOME:-$HOME/.haocean}"
TEACHER_DATA_DIR="${HAOCEAN_TEACHER_HOME:-$HOME/.haocean-teacher}"

SCRIPT_DIR=""
SCRIPT_SOURCE="$0"
if [ "$SCRIPT_SOURCE" != "bash" ] && [ "$SCRIPT_SOURCE" != "sh" ] && [ -f "$SCRIPT_SOURCE" ]; then
  SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_SOURCE")" >/dev/null 2>&1 && pwd)"
fi

run_installer() {
  local script_name="$1"
  if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/$script_name" ]; then
    HAOCEAN_REPO_URL="$REPO_URL" HAOCEAN_VERSION="$REF" HAOCEAN_BIN_DIR="$BIN_DIR" \
      bash "$SCRIPT_DIR/$script_name"
    return
  fi

  curl -fsSL "$RAW_BASE/$script_name" | \
    HAOCEAN_REPO_URL="$REPO_URL" HAOCEAN_VERSION="$REF" HAOCEAN_BIN_DIR="$BIN_DIR" bash
}

run_installer install-student.sh
run_installer install-teacher.sh

echo
echo "Haocean CLI tools installed."
echo "Student : $BIN_DIR/haocean-student"
echo "Teacher : $BIN_DIR/haocean-teacher"
echo "AI help : $BIN_DIR/haocean ai-help"
echo "Guides  : $STUDENT_DATA_DIR/docs/student_usage_guide.md"
echo "          $TEACHER_DATA_DIR/docs/teacher_usage_guide.md"
echo
echo "Add this to your shell profile if commands are not found:"
echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
echo
echo "Uninstall old local CLI install:"
echo "  curl -fsSL $RAW_BASE/uninstall.sh | bash"
