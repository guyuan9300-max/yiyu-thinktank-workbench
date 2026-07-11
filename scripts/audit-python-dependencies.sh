#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/yiyu-python-audit.XXXXXX")"
trap 'rm -rf "${TMP_DIR}"' EXIT

command -v uv >/dev/null 2>&1 || { echo "uv is required" >&2; exit 2; }
command -v uvx >/dev/null 2>&1 || { echo "uvx is required" >&2; exit 2; }

python3 "${ROOT}/scripts/audit_chromadb_isolation.py"

echo "==> Exporting frozen backend lock"
(
  cd "${ROOT}/backend"
  uv export --frozen --no-dev --no-hashes --format requirements-txt \
    --output-file "${TMP_DIR}/backend-requirements.txt" >/dev/null
)

echo "==> Auditing backend lock (no exceptions)"
uvx pip-audit \
  --requirement "${TMP_DIR}/backend-requirements.txt" \
  --no-deps \
  --disable-pip \
  --progress-spinner off

echo "==> Exporting frozen cloud-backend lock"
(
  cd "${ROOT}/cloud_backend"
  uv export --frozen --no-dev --no-hashes --format requirements-txt \
    --output-file "${TMP_DIR}/cloud-requirements.txt" >/dev/null
)

echo "==> Auditing cloud lock (one exact, isolated, upstream-unfixed exception)"
uvx pip-audit \
  --requirement "${TMP_DIR}/cloud-requirements.txt" \
  --no-deps \
  --disable-pip \
  --progress-spinner off \
  --ignore-vuln PYSEC-2026-311

echo "==> Resolving and auditing cloud deployment requirements"
uv pip compile "${ROOT}/cloud_backend/requirements.deploy.txt" \
  --python-version 3.11 \
  --no-header \
  --no-annotate \
  --output-file "${TMP_DIR}/cloud-deploy-requirements.txt" >/dev/null
uvx pip-audit \
  --requirement "${TMP_DIR}/cloud-deploy-requirements.txt" \
  --no-deps \
  --disable-pip \
  --progress-spinner off \
  --ignore-vuln PYSEC-2026-311

echo "Python dependency audit passed"
