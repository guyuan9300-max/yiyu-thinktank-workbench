#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AVD_NAME="${YIYU_AVD_NAME:-Yiyu_Android35_Dev}"
PORT="${YIYU_METRO_PORT:-8081}"
CLOUD_PORT="${YIYU_CLOUD_PORT:-47830}"
APP_ID="${YIYU_ANDROID_APP_ID:-com.yiyu.mobile}"
DEVICE_SERIAL="${YIYU_ANDROID_SERIAL:-emulator-5554}"
METRO_LABEL="${YIYU_METRO_LABEL:-com.yiyu.mobile.metro}"
EMULATOR_LABEL="${YIYU_EMULATOR_LABEL:-com.yiyu.mobile.emulator}"
CLOUD_LABEL="${YIYU_CLOUD_LABEL:-com.yiyu.mobile.cloud-backend}"
LOG_DIR="$ROOT_DIR/output/android-dev-env"
CLOUD_BACKEND_DIR="${YIYU_CLOUD_BACKEND_DIR:-$(cd "$ROOT_DIR/.." && pwd)/cloud_backend}"
CLOUD_DATA_DIR="${YIYU_CLOUD_DATA_DIR:-$LOG_DIR/cloud-data}"
CLOUD_ADMIN_EMAIL="${YIYU_CLOUD_BOOTSTRAP_ADMIN_EMAIL:-guyuan@klngo.org}"

JAVA_HOME_DEFAULT="/Users/guyuanyuan/.openclaw/workspace/.codex-tools/jdks/jdk-17/Contents/Home"
ANDROID_HOME_DEFAULT="$HOME/Library/Android/sdk"

export JAVA_HOME="${JAVA_HOME:-$JAVA_HOME_DEFAULT}"
export ANDROID_HOME="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-$ANDROID_HOME_DEFAULT}}"
export ANDROID_SDK_ROOT="$ANDROID_HOME"
export PATH="$JAVA_HOME/bin:$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$PATH"

REINSTALL=0
STOP=0

usage() {
  cat <<EOF
Usage: bash scripts/start-android-dev-env.sh [--reinstall] [--stop]

Starts the local Android dev-test environment:
  - Pixel AVD: $AVD_NAME
  - Metro dev server: http://localhost:$PORT
  - Mobile cloud debug backend: http://localhost:$CLOUD_PORT
  - Debug app: $APP_ID

Options:
  --reinstall  Rebuild and install the Android debug app from current source.
  --stop       Stop the launchctl Metro service and the emulator.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --reinstall)
      REINSTALL=1
      ;;
    --stop)
      STOP=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
  shift
done

mkdir -p "$LOG_DIR"

ADB_BIN="$(command -v adb || true)"
EMULATOR_BIN="$(command -v emulator || true)"

if [[ -z "$ADB_BIN" ]]; then
  echo "ERROR: adb not found. Expected Android platform-tools under $ANDROID_HOME." >&2
  exit 1
fi

if [[ -z "$EMULATOR_BIN" ]]; then
  EMULATOR_BIN="$ANDROID_HOME/emulator/emulator"
fi

stop_env() {
  launchctl remove "$CLOUD_LABEL" >/dev/null 2>&1 || true
  launchctl remove "$METRO_LABEL" >/dev/null 2>&1 || true
  launchctl remove "$EMULATOR_LABEL" >/dev/null 2>&1 || true
  if "$ADB_BIN" devices | awk -v serial="$DEVICE_SERIAL" '$1 == serial && $2 == "device" { found = 1 } END { exit !found }'; then
    "$ADB_BIN" -s "$DEVICE_SERIAL" emu kill >/dev/null 2>&1 || true
  fi
  echo "Stopped Android dev environment."
}

if [[ "$STOP" == "1" ]]; then
  stop_env
  exit 0
fi

if [[ ! -x "$JAVA_HOME/bin/java" ]]; then
  echo "ERROR: Java not found at $JAVA_HOME/bin/java." >&2
  exit 1
fi

if [[ ! -x "$EMULATOR_BIN" ]]; then
  echo "ERROR: Android emulator not found at $EMULATOR_BIN." >&2
  exit 1
fi

if ! "$EMULATOR_BIN" -list-avds | grep -qx "$AVD_NAME"; then
  echo "ERROR: AVD '$AVD_NAME' not found. Available AVDs:" >&2
  "$EMULATOR_BIN" -list-avds >&2 || true
  exit 1
fi

device_ready() {
  "$ADB_BIN" devices | awk -v serial="$DEVICE_SERIAL" '$1 == serial && $2 == "device" { found = 1 } END { exit !found }'
}

if ! device_ready; then
  echo "Starting emulator $AVD_NAME..."
  launchctl remove "$EMULATOR_LABEL" >/dev/null 2>&1 || true
  : >"$LOG_DIR/emulator.log"
  if command -v launchctl >/dev/null 2>&1; then
    launchctl submit -l "$EMULATOR_LABEL" -- "$ROOT_DIR/scripts/run-android-emulator-service.sh" "$AVD_NAME" "$LOG_DIR/emulator.log"
  else
    nohup "$ROOT_DIR/scripts/run-android-emulator-service.sh" "$AVD_NAME" "$LOG_DIR/emulator.log" >/dev/null 2>&1 &
    echo "$!" >"$LOG_DIR/emulator.pid"
  fi
fi

echo "Waiting for emulator boot..."
"$ADB_BIN" -s "$DEVICE_SERIAL" wait-for-device
for _ in {1..120}; do
  booted="$("$ADB_BIN" -s "$DEVICE_SERIAL" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r' || true)"
  if [[ "$booted" == "1" ]]; then
    break
  fi
  sleep 2
done

booted="$("$ADB_BIN" -s "$DEVICE_SERIAL" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r' || true)"
if [[ "$booted" != "1" ]]; then
  echo "ERROR: emulator did not finish booting." >&2
  exit 1
fi

"$ADB_BIN" -s "$DEVICE_SERIAL" reverse "tcp:$PORT" "tcp:$PORT" >/dev/null
"$ADB_BIN" -s "$DEVICE_SERIAL" reverse "tcp:$CLOUD_PORT" "tcp:$CLOUD_PORT" >/dev/null || true

if ! lsof -nP -iTCP:"$CLOUD_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Starting mobile cloud debug backend on port $CLOUD_PORT..."
  launchctl remove "$CLOUD_LABEL" >/dev/null 2>&1 || true
  : >"$LOG_DIR/cloud-backend.log"
  if command -v launchctl >/dev/null 2>&1; then
    launchctl submit -l "$CLOUD_LABEL" -- "$ROOT_DIR/scripts/run-android-cloud-backend-service.sh" "$CLOUD_BACKEND_DIR" "$CLOUD_DATA_DIR" "$CLOUD_PORT" "$LOG_DIR/cloud-backend.log" "$CLOUD_ADMIN_EMAIL"
  else
    nohup "$ROOT_DIR/scripts/run-android-cloud-backend-service.sh" "$CLOUD_BACKEND_DIR" "$CLOUD_DATA_DIR" "$CLOUD_PORT" "$LOG_DIR/cloud-backend.log" "$CLOUD_ADMIN_EMAIL" >/dev/null 2>&1 &
  fi

  for _ in {1..60}; do
    if curl -fsS "http://127.0.0.1:$CLOUD_PORT/health" >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
fi

if ! curl -fsS "http://127.0.0.1:$CLOUD_PORT/health" >/dev/null 2>&1; then
  echo "ERROR: mobile cloud debug backend did not start. See $LOG_DIR/cloud-backend.log." >&2
  exit 1
fi

if ! lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Starting Metro on port $PORT..."
  launchctl remove "$METRO_LABEL" >/dev/null 2>&1 || true
  : >"$LOG_DIR/metro.log"
  if command -v launchctl >/dev/null 2>&1; then
    launchctl submit -l "$METRO_LABEL" -- "$ROOT_DIR/scripts/run-android-metro-service.sh" "$PORT" "$LOG_DIR/metro.log"
  else
    nohup "$ROOT_DIR/scripts/run-android-metro-service.sh" "$PORT" "$LOG_DIR/metro.log" >/dev/null 2>&1 &
  fi

  for _ in {1..60}; do
    if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
fi

if ! lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "ERROR: Metro did not start. See $LOG_DIR/metro.log." >&2
  exit 1
fi

installed_path="$("$ADB_BIN" -s "$DEVICE_SERIAL" shell pm path "$APP_ID" 2>/dev/null | tr -d '\r' || true)"
if [[ "$REINSTALL" == "1" || -z "$installed_path" ]]; then
  echo "Installing debug app from current source..."
  (cd "$ROOT_DIR/android" && ./gradlew :app:installDebug -PreactNativeDevServerPort="$PORT")
fi

echo "Launching $APP_ID..."
"$ADB_BIN" -s "$DEVICE_SERIAL" shell am force-stop "$APP_ID" >/dev/null
"$ADB_BIN" -s "$DEVICE_SERIAL" shell am start -W -n "$APP_ID/.MainActivity"

cat <<EOF

Android dev environment is ready.
- JS/UI edits: save files, then reload in the emulator.
- Native/Android dependency edits: rerun with --reinstall.
- Service address inside the Android emulator: http://10.0.2.2:$CLOUD_PORT
- Metro log: $LOG_DIR/metro.log
- Cloud backend log: $LOG_DIR/cloud-backend.log
- Emulator log: $LOG_DIR/emulator.log
EOF
