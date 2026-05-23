#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATES_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

for template in \
  tsp_local \
  tsp_docker \
  tsp_harbor \
  tsp_skydiscover_python \
  tsp_skydiscover_docker
do
  echo "== $template =="
  "$TEMPLATES_DIR/$template/scripts/setup_project.sh" --dry-run
  "$TEMPLATES_DIR/$template/scripts/run_demo.sh" --dry-run
done
