#!/usr/bin/env bash
# Start the CutLab server (port 8787) and studio (port 3000) together.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"

python="$root/apps/server/.venv/bin/python"
[ -x "$python" ] || python="$root/apps/server/.venv/Scripts/python.exe"
if [ ! -x "$python" ]; then
    echo "Server venv missing. Run: python -m venv apps/server/.venv && apps/server/.venv/bin/pip install -e apps/server" >&2
    exit 1
fi

echo "Starting CutLab server on http://127.0.0.1:8787 ..."
(cd "$root/apps/server" && "$python" -m cutlab.main) &
server_pid=$!

echo "Starting studio on http://localhost:3000 ..."
(cd "$root/apps/studio" && npm run dev) &
studio_pid=$!

trap 'kill $server_pid $studio_pid 2>/dev/null || true' INT TERM EXIT
wait
