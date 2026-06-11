#!/usr/bin/env bash

set -euo pipefail

CLOUD_BACKEND_DIR="${1:?cloud backend dir is required}"
DATA_DIR="${2:?cloud data dir is required}"
PORT="${3:-47830}"
LOG_FILE="${4:-/tmp/yiyu-android-cloud-backend.log}"
ADMIN_EMAIL="${5:-}"

mkdir -p "$DATA_DIR" "$(dirname "$LOG_FILE")"
cd "$CLOUD_BACKEND_DIR"

export YIYU_CLOUD_DATA_DIR="$DATA_DIR"
if [[ -n "$ADMIN_EMAIL" ]]; then
  export YIYU_CLOUD_BOOTSTRAP_ADMIN_EMAIL="$ADMIN_EMAIL"
fi

exec .venv/bin/python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port "$PORT" >>"$LOG_FILE" 2>&1
