#!/usr/bin/env bash
set -euo pipefail

BACKEND_URL="${YIYU_BACKEND_URL:-http://127.0.0.1:47829}"
CLIENT_ID="${1:-${CLIENT_ID:-}}"
PROMPT="${2:-${PROMPT:-请用三句话介绍这个客户}}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "== source integrity =="
curl -fsS "${BACKEND_URL}/api/v1/system/source-integrity" | python3 -m json.tool

echo "== enforce retrieval settings =="
CURRENT_SETTINGS="$(curl -fsS "${BACKEND_URL}/api/v1/retrieval/settings")"
UPDATED_SETTINGS="$(python3 - <<'PY' "$CURRENT_SETTINGS"
import json, sys
payload = json.loads(sys.argv[1])
payload["qualityGateMode"] = "observe"
payload["dataCenterKernelEnabled"] = True
payload["answerLayerEnabled"] = True
payload["chatKernelPrimaryEnabled"] = True
print(json.dumps(payload, ensure_ascii=False))
PY
)"
curl -fsS -X POST "${BACKEND_URL}/api/v1/retrieval/settings" \
  -H 'Content-Type: application/json' \
  -d "${UPDATED_SETTINGS}" >/dev/null

echo "== set workspace switches =="
if [[ -n "${CLIENT_ID}" ]]; then
  curl -fsS -X POST "${BACKEND_URL}/api/v1/runtime/generation-state/reset" \
    -H 'Content-Type: application/json' \
    -d "{\"clientId\":\"${CLIENT_ID}\",\"answerIntent\":\"general\",\"resetScope\":\"client\"}" | python3 -m json.tool
else
  echo "CLIENT_ID not provided; skipping runtime reset and smoke chat."
fi

echo "== llm healthcheck =="
curl -fsS -X POST "${BACKEND_URL}/api/v1/runtime/llm-healthcheck" \
  -H 'Content-Type: application/json' \
  -d '{}' | python3 -m json.tool

echo "== banned copy scan =="
if rg -n "已基于命中的资料生成简版可用回答|完整长文扩写未完成|根据当前已入库资料|可以先这样介绍|正式长回答未完成" \
  "${REPO_ROOT}/src" \
  --glob '!**/*.test.*'; then
  echo "banned workspace chat copy still present in source" >&2
  exit 1
fi
echo "copy scan ok"

if [[ -n "${CLIENT_ID}" ]]; then
  echo "== smoke workspace chat =="
  python3 "${REPO_ROOT}/scripts/smoke_workspace_chat_generation.py" \
    --backend-url "${BACKEND_URL}" \
    --client-id "${CLIENT_ID}" \
    --prompt "${PROMPT}"
fi
