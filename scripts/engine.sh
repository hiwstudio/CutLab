#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
if (( $# < 1 )); then
  echo "Usage: scripts/engine.sh <mixfix|clipinn|viral|recap|hiw> [arguments...]" >&2
  exit 2
fi
engine="$1"
shift

export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8
export PYTHONPATH="$root/engines${PYTHONPATH:+:$PYTHONPATH}"

case "$engine" in
  hiw)
    if [[ ! -d "$root/engines/hiw-studio/node_modules" ]]; then
      echo "HIW Studio dependencies are missing. Run scripts/setup.sh first." >&2
      exit 1
    fi
    cd "$root/engines/hiw-studio"
    exec npm run hiw -- "$@"
    ;;
  mixfix|clipinn|viral|recap)
    python="$root/engines/.venv/bin/python"
    if [[ ! -x "$python" ]]; then
      echo "Engine dependencies are missing. Run scripts/setup.sh first." >&2
      exit 1
    fi
    ;;
  *)
    echo "Unknown engine '$engine'. Choose mixfix, clipinn, viral, recap, or hiw." >&2
    exit 2
    ;;
esac

case "$engine" in
  mixfix)
    cd "$root/engines/mixfix"
    exec "$python" -m mixfix.cli "$@"
    ;;
  clipinn)
    export AGENT_OPERATOR=1
    cd "$root/engines/clipinn"
    exec "$python" -m clipinn "$@"
    ;;
  viral)
    export AGENT_OPERATOR=1
    cd "$root/engines/viral-clip-engine"
    exec "$python" run.py "$@"
    ;;
  recap)
    export LLM_BACKEND="${LLM_BACKEND:-manual}"
    cd "$root/engines/recap-engine"
    exec "$python" run.py "$@"
    ;;
esac
