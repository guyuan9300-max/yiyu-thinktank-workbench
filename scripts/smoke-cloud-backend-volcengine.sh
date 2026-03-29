#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-https://api.yiyu.love}"

echo "=== health ==="
curl -fsS "${BASE_URL%/}/health"
echo
