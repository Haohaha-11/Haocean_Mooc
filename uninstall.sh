#!/usr/bin/env bash
set -euo pipefail

BIN_DIR="${HAOCEAN_BIN_DIR:-$HOME/.local/bin}"
STUDENT_INSTALL_DIR="${HAOCEAN_INSTALL_DIR:-$HOME/.haocean-cli}"
TEACHER_INSTALL_DIR="${HAOCEAN_TEACHER_INSTALL_DIR:-$HOME/.haocean-teacher-cli}"
STUDENT_DATA_DIR="${HAOCEAN_HOME:-$HOME/.haocean}"
TEACHER_DATA_DIR="${HAOCEAN_TEACHER_HOME:-$HOME/.haocean-teacher}"
DELETE_DATA=false

usage() {
  cat <<'EOF'
Usage:
  uninstall.sh              Remove installed Haocean CLI binaries and virtualenvs.
  uninstall.sh --with-data  Also remove local config, tokens, workspace, downloads, and logs.

Default behavior preserves:
  ~/.haocean/
  ~/.haocean-teacher/
EOF
}

for arg in "$@"; do
  case "$arg" in
    --with-data)
      DELETE_DATA=true
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $arg" >&2
      usage >&2
      exit 2
      ;;
  esac
done

remove_command() {
  local name="$1"
  local path="$BIN_DIR/$name"
  if [ -L "$path" ]; then
    rm -f "$path"
    echo "Removed command: $path"
  elif [ -e "$path" ]; then
    echo "Skipped non-symlink command: $path"
  else
    echo "Command not found: $path"
  fi
}

remove_dir() {
  local path="$1"
  if [ -d "$path" ]; then
    rm -rf "$path"
    echo "Removed directory: $path"
  else
    echo "Directory not found: $path"
  fi
}

remove_command haocean-student
remove_command haocean-teacher
remove_command haocean

remove_dir "$STUDENT_INSTALL_DIR"
remove_dir "$TEACHER_INSTALL_DIR"

if [ "$DELETE_DATA" = true ]; then
  remove_dir "$STUDENT_DATA_DIR"
  remove_dir "$TEACHER_DATA_DIR"
else
  echo "Preserved student data: $STUDENT_DATA_DIR"
  echo "Preserved teacher data: $TEACHER_DATA_DIR"
  echo "Run with --with-data to remove local config, tokens, workspace, downloads, and logs."
fi

echo "Haocean CLI uninstall finished."
