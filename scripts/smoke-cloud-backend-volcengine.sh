#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://101.126.34.232}"

retry_curl() {
  local path="$1"
  local attempts="${2:-8}"
  local delay="${3:-2}"
  local i
  for ((i=1; i<=attempts; i++)); do
    if curl -fsS "${BASE_URL%/}${path}" >/tmp/yiyu-cloud-smoke.out 2>/tmp/yiyu-cloud-smoke.err; then
      cat /tmp/yiyu-cloud-smoke.out
      return 0
    fi
    if [[ $i -lt $attempts ]]; then
      sleep "${delay}"
    fi
  done
  cat /tmp/yiyu-cloud-smoke.err >&2 || true
  return 1
}

echo "=== health ==="
retry_curl "/health"
echo

echo "=== smart-input route ==="
OPENAPI_JSON="$(retry_curl "/openapi.json")"
if grep -q '"/api/v1/mobile/smart-input/task-draft"' <<<"${OPENAPI_JSON}"; then
  echo "smart-input route present"
else
  echo "smart-input route missing" >&2
  exit 1
fi

echo "=== required env hints ==="
cat <<'EOF'
Ensure remote .env contains:
- YIYU_CLOUD_PUBLIC_BASE_URL
- DOUBAO_FILE_ASR_APP_ID
- DOUBAO_FILE_ASR_ACCESS_TOKEN
- DOUBAO_STREAM_ASR_APP_ID
- DOUBAO_STREAM_ASR_ACCESS_TOKEN
Optional:
- DASHSCOPE_API_KEY
- YIYU_SMART_INPUT_MODEL
EOF
