#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-root@101.126.34.232}"
REMOTE_DIR="${2:-/opt/yiyu/cloud-backend}"
SERVICE_NAME="${3:-yiyu-cloud-backend.service}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SSH_OPTS=(-o StrictHostKeyChecking=no)

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
ssh "${SSH_OPTS[@]}" "${TARGET}" "
  set -euo pipefail
  if ! id -u yiyu >/dev/null 2>&1; then
    echo 'Missing system user yiyu' >&2
    exit 1
  fi
  if [[ ! -f '${REMOTE_DIR}/.env' ]]; then
    echo 'Missing ${REMOTE_DIR}/.env' >&2
    exit 1
  fi
  if [[ ! -x '${REMOTE_DIR}/.venv/bin/python' ]]; then
    python3 -m venv '${REMOTE_DIR}/.venv'
  fi
  '${REMOTE_DIR}/.venv/bin/python' -m pip install --upgrade pip >/dev/null
  '${REMOTE_DIR}/.venv/bin/python' -m pip install -r '${REMOTE_DIR}/requirements.deploy.txt' >/dev/null
  chown -R yiyu:yiyu '${REMOTE_DIR}'
  systemctl restart '${SERVICE_NAME}'
  systemctl --no-pager --full status '${SERVICE_NAME}' | sed -n '1,20p'
"

echo "==> Smoke check"
"${REPO_ROOT}/scripts/smoke-cloud-backend-volcengine.sh"
