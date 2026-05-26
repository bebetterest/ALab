#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXAMPLE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$EXAMPLE_DIR/../.." && pwd)"

RUN_DIR="$EXAMPLE_DIR/.run"
ALAB_EXAMPLE_HOME="${ALAB_EXAMPLE_HOME:-$RUN_DIR/alab-home}"
UV_CACHE_DIR="${UV_CACHE_DIR:-$RUN_DIR/uv-cache}"
UV_DEFAULT_INDEX="${UV_DEFAULT_INDEX:-https://pypi.org/simple}"
PYTHONPYCACHEPREFIX="${PYTHONPYCACHEPREFIX:-$RUN_DIR/pycache}"
ALAB_BIN="${ALAB_BIN:-uv run --locked --project $REPO_ROOT alab}"
CREDENTIALS_FILE="$RUN_DIR/secrets/dashboard-showcase-credentials.txt"

if [[ ! -f "$CREDENTIALS_FILE" ]]; then
  echo "Missing generated showcase home. Creating it now..." >&2
  UV_CACHE_DIR="$UV_CACHE_DIR" UV_DEFAULT_INDEX="$UV_DEFAULT_INDEX" PYTHONPYCACHEPREFIX="$PYTHONPYCACHEPREFIX" \
    uv run --locked --project "$REPO_ROOT" python "$SCRIPT_DIR/create_demo_home.py" --home "$ALAB_EXAMPLE_HOME" --force
fi

ROOT_KEY="$(awk -F= '$1 == "root_key" { print $2; exit }' "$CREDENTIALS_FILE")"
if [[ -z "$ROOT_KEY" ]]; then
  echo "root_key not found in $CREDENTIALS_FILE" >&2
  exit 1
fi

read -r -a ALAB_CMD <<< "$ALAB_BIN"
UV_CACHE_DIR="$UV_CACHE_DIR" UV_DEFAULT_INDEX="$UV_DEFAULT_INDEX" PYTHONPYCACHEPREFIX="$PYTHONPYCACHEPREFIX" \
  "${ALAB_CMD[@]}" --home "$ALAB_EXAMPLE_HOME" --key "$ROOT_KEY" dashboard --refresh-seconds 0 "$@"
