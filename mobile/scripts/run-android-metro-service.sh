#!/usr/bin/env bash

set -euo pipefail

PORT="${1:-8081}"
LOG_FILE="${2:-}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

JAVA_HOME_DEFAULT="/Users/guyuanyuan/.openclaw/workspace/.codex-tools/jdks/jdk-17/Contents/Home"
ANDROID_HOME_DEFAULT="$HOME/Library/Android/sdk"

export JAVA_HOME="${JAVA_HOME:-$JAVA_HOME_DEFAULT}"
export ANDROID_HOME="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-$ANDROID_HOME_DEFAULT}}"
export ANDROID_SDK_ROOT="$ANDROID_HOME"
export EXPO_NO_TELEMETRY="${EXPO_NO_TELEMETRY:-1}"
export PATH="$JAVA_HOME/bin:$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$PATH"

if [[ -n "$LOG_FILE" ]]; then
  mkdir -p "$(dirname "$LOG_FILE")"
  exec >>"$LOG_FILE" 2>&1
fi

cd "$ROOT_DIR"

extra_args=()
if [[ "${YIYU_METRO_CLEAR:-0}" == "1" ]]; then
  extra_args+=(--clear)
fi

exec node ./node_modules/expo/bin/cli start --dev-client --host lan --port "$PORT" "${extra_args[@]}"
