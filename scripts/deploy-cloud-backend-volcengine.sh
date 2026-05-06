#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-${YIYU_CLOUD_DEPLOY_TARGET:-}}"
REMOTE_DIR="${2:-/opt/yiyu/cloud-backend}"
SERVICE_NAME="${3:-yiyu-cloud-backend.service}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SSH_OPTS=(-o StrictHostKeyChecking=no)

if [[ -z "${TARGET}" ]]; then
  echo "Usage: $0 <ssh-target> [remote-dir] [service-name]" >&2
  echo "Or set YIYU_CLOUD_DEPLOY_TARGET." >&2
  exit 2
fi

if [[ -n "${YIYU_VOLCENGINE_SSH_KEY:-}" ]]; then
  SSH_OPTS+=(-i "${YIYU_VOLCENGINE_SSH_KEY}")
fi

echo "==> Syncing cloud backend code to ${TARGET}:${REMOTE_DIR}"
ssh "${SSH_OPTS[@]}" "${TARGET}" "install -d -m 0755 ${REMOTE_DIR} ${REMOTE_DIR}/app"
rsync -az --delete \
  -e "ssh ${SSH_OPTS[*]}" \
  "${REPO_ROOT}/cloud_backend/app/" \
  "${TARGET}:${REMOTE_DIR}/app/"
rsync -az \
  -e "ssh ${SSH_OPTS[*]}" \
  "${REPO_ROOT}/cloud_backend/pyproject.toml" \
  "${REPO_ROOT}/cloud_backend/uv.lock" \
  "${REPO_ROOT}/cloud_backend/requirements.deploy.txt" \
  "${TARGET}:${REMOTE_DIR}/"

echo "==> Refreshing venv and restarting ${SERVICE_NAME}"
ssh "${SSH_OPTS[@]}" "${TARGET}" bash -s -- "${REMOTE_DIR}" "${SERVICE_NAME}" <<'REMOTE'
set -euo pipefail

REMOTE_DIR="$1"
SERVICE_NAME="$2"

if ! id -u yiyu >/dev/null 2>&1; then
  echo "Missing system user yiyu" >&2
  exit 1
fi
if [[ ! -f "${REMOTE_DIR}/.env" ]]; then
  echo "Missing ${REMOTE_DIR}/.env" >&2
  exit 1
fi
for key in YIYU_CLOUD_PUBLIC_BASE_URL DOUBAO_FILE_ASR_APP_ID DOUBAO_FILE_ASR_ACCESS_TOKEN DOUBAO_STREAM_ASR_APP_ID DOUBAO_STREAM_ASR_ACCESS_TOKEN; do
  if ! grep -q "^${key}=" "${REMOTE_DIR}/.env"; then
    echo "WARN missing ${key} in ${REMOTE_DIR}/.env" >&2
  fi
done
if [[ ! -x "${REMOTE_DIR}/.venv/bin/python" ]]; then
  python3 -m venv "${REMOTE_DIR}/.venv"
fi
"${REMOTE_DIR}/.venv/bin/python" -m pip install --upgrade pip >/dev/null
"${REMOTE_DIR}/.venv/bin/python" -m pip install -r "${REMOTE_DIR}/requirements.deploy.txt" >/dev/null
chown -R yiyu:yiyu "${REMOTE_DIR}"
systemctl restart "${SERVICE_NAME}"
systemctl --no-pager --full status "${SERVICE_NAME}" | sed -n '1,20p'
REMOTE

echo "==> Smoke check"
"${REPO_ROOT}/scripts/smoke-cloud-backend-volcengine.sh" "${YIYU_CLOUD_API_URL:-}"
