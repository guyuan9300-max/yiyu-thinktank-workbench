#!/usr/bin/env bash

set -euo pipefail

AVD_NAME="${1:-Yiyu_Android35_Dev}"
LOG_FILE="${2:-}"

JAVA_HOME_DEFAULT="/Users/guyuanyuan/.openclaw/workspace/.codex-tools/jdks/jdk-17/Contents/Home"
ANDROID_HOME_DEFAULT="$HOME/Library/Android/sdk"

export JAVA_HOME="${JAVA_HOME:-$JAVA_HOME_DEFAULT}"
export ANDROID_HOME="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-$ANDROID_HOME_DEFAULT}}"
export ANDROID_SDK_ROOT="$ANDROID_HOME"
export PATH="$JAVA_HOME/bin:$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$PATH"

EMULATOR_BIN="$(command -v emulator || true)"
if [[ -z "$EMULATOR_BIN" ]]; then
  EMULATOR_BIN="$ANDROID_HOME/emulator/emulator"
fi

if [[ -n "$LOG_FILE" ]]; then
  mkdir -p "$(dirname "$LOG_FILE")"
  exec >>"$LOG_FILE" 2>&1
fi

exec "$EMULATOR_BIN" -avd "$AVD_NAME" -netdelay none -netspeed full -gpu host
