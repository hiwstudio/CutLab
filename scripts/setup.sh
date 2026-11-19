#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
core_only=0
if [[ "${1:-}" == "--core-only" ]]; then core_only=1; fi

python_cmd="$(command -v python3 || command -v python || true)"
if [[ -z "$python_cmd" ]]; then
  echo "Python 3.11+ was not found. Install Python and retry." >&2
  exit 1
fi
"$python_cmd" - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit(f"CutLab needs Python 3.11 or newer; found {sys.version.split()[0]}")
PY

node_version="$(node --version 2>/dev/null || true)"
npm_cmd="$(command -v npm || true)"
if [[ -z "$node_version" || -z "$npm_cmd" ]]; then
  echo "Node.js 20+ and npm were not found. Install Node.js and retry." >&2
  exit 1
fi
node_major="${node_version#v}"
node_major="${node_major%%.*}"
if (( node_major < 20 )); then
  echo "CutLab Studio needs Node.js 20 or newer; found $node_version." >&2
  exit 1
fi
if ! command -v ffmpeg >/dev/null || ! command -v ffprobe >/dev/null; then
  echo "FFmpeg and ffprobe must be on PATH before setup." >&2
  exit 1
fi

echo "Setting up the CutLab server..."
server_venv="$root/apps/server/.venv"
if [[ ! -x "$server_venv/bin/python" ]]; then
  "$python_cmd" -m venv "$server_venv"
fi
"$server_venv/bin/python" -m pip install -e "$root/apps/server"

echo "Installing CutLab Studio dependencies..."
(cd "$root/apps/studio" && npm ci)

if (( ! core_only )); then
  echo "Setting up the bundled production engines..."
  engine_venv="$root/engines/.venv"
  if [[ ! -x "$engine_venv/bin/python" ]]; then
    "$python_cmd" -m venv "$engine_venv"
  fi
  for requirements in \
    "$root/engines/mixfix/requirements.txt" \
    "$root/engines/clipinn/requirements.txt" \
    "$root/engines/viral-clip-engine/requirements.txt" \
    "$root/engines/recap-engine/requirements.txt"; do
    "$engine_venv/bin/python" -m pip install -r "$requirements"
  done
  echo "Installing HIW Studio dependencies..."
  (cd "$root/engines/hiw-studio" && npm ci)
else
  echo "Core-only setup complete. Rerun scripts/setup.sh later to install the bundled engines."
fi

echo "Setup complete. Start CutLab with bash scripts/dev.sh."
