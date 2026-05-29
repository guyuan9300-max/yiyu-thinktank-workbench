#!/usr/bin/env bash
set -euo pipefail

APP_DIR=${APP_DIR:-/opt/yiyu/cloud-backend}
PUBLIC_HOST=${PUBLIC_HOST:-}

docker_compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
    return
  fi
  if command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
    return
  fi
  echo "Docker Compose is not available." >&2
  exit 1
}

if ! command -v docker >/dev/null 2>&1; then
  apt-get update
  apt-get install -y ca-certificates curl gnupg
  install -m 0755 -d /etc/apt/keyrings
  if curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg; then
    chmod a+r /etc/apt/keyrings/docker.gpg
    . /etc/os-release
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
      | tee /etc/apt/sources.list.d/docker.list >/dev/null
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  else
    echo "Docker upstream repository unreachable, falling back to Ubuntu packages." >&2
    rm -f /etc/apt/keyrings/docker.gpg /etc/apt/sources.list.d/docker.list
    apt-get update
    apt-get install -y docker.io docker-compose-v2
  fi
  systemctl enable docker
  systemctl start docker
fi

mkdir -p "${APP_DIR}"
cd "${APP_DIR}"

if [[ ! -f .env ]]; then
  cp .env.example .env
  python3 - <<'PY'
from pathlib import Path
import secrets

env_path = Path(".env")
content = env_path.read_text()
replacements = {
    "replace-with-a-strong-random-secret": secrets.token_urlsafe(48),
    "replace-with-a-strong-admin-password": secrets.token_urlsafe(18),
    "replace-if-needed": secrets.token_urlsafe(14),
}
for needle, value in replacements.items():
    content = content.replace(needle, value, 1)
env_path.write_text(content)
PY
fi

if [[ -z "${PUBLIC_HOST}" ]]; then
  PUBLIC_IP=$(curl -4fsSL https://api.ipify.org)
  PUBLIC_HOST="${PUBLIC_IP}.sslip.io"
fi

export PUBLIC_HOST
docker_compose up -d --build

echo "DEPLOY_OK https://${PUBLIC_HOST}"
