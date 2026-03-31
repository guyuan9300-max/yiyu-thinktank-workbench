#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://101.126.34.232}"

echo "=== health ==="
curl -fsS "${BASE_URL%/}/health"
echo

echo "=== smart-input route ==="
OPENAPI_JSON="$(curl -fsS "${BASE_URL%/}/openapi.json")"
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
