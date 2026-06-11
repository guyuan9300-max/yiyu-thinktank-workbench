#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ADB_BIN="${ADB_BIN:-}"
if [[ -z "$ADB_BIN" ]]; then
  if command -v adb >/dev/null 2>&1; then
    ADB_BIN="$(command -v adb)"
  elif [[ -x "$HOME/Library/Android/sdk/platform-tools/adb" ]]; then
    ADB_BIN="$HOME/Library/Android/sdk/platform-tools/adb"
  fi
fi

echo "==> RC gate: TypeScript"
if [[ "${SKIP_TYPESCRIPT_GATE:-0}" != "1" ]]; then
  npx tsc --noEmit
else
  echo "skipped (handled by outer stability scan)"
fi

echo
echo "==> RC gate: core tests"
if [[ "${SKIP_CORE_TEST_GATE:-0}" != "1" ]]; then
  npm run test:core
else
  echo "skipped (handled by outer stability scan)"
fi

echo
echo "==> RC gate: guarded direct task API writes"
npm run check:no-direct-task-api-writes

echo
echo "==> RC gate: grep - taskBoard direct fetch paths"
taskboard_matches="$(rg -n 'fetchTaskBoard|loadWithCache\(.*taskBoard' app components lib -g '!node_modules/**' || true)"
if [[ -n "$taskboard_matches" ]]; then
  echo "$taskboard_matches"
  page_level_matches="$(printf '%s\n' "$taskboard_matches" | rg '^(app|components)/' || true)"
  if [[ -n "$page_level_matches" ]]; then
    echo
    echo "FAIL: page-level taskBoard direct fetch residuals found."
    exit 1
  fi
fi

echo
echo "==> RC gate: grep - UTC date key usage"
utc_matches="$(rg -n 'toISOString\(\)\.slice\(0, 10\)' app components lib -g '!node_modules/**' || true)"
if [[ -n "$utc_matches" ]]; then
  echo "$utc_matches"
  echo
  echo "FAIL: UTC date key residuals found."
  exit 1
fi

echo
echo "==> RC gate: grep - legacy DateTimePicker usage"
picker_matches="$(rg -n 'DateTimePicker([^S]|$)' app components lib -g '!node_modules/**' || true)"
if [[ -n "$picker_matches" ]]; then
  echo "$picker_matches"
  echo
  echo "FAIL: legacy DateTimePicker residuals found."
  exit 1
fi

echo
echo "==> RC gate: Android runtime flags"
rg -n 'newArchEnabled|hermesEnabled' android/gradle.properties

echo
echo "==> RC gate: Android APK presence"
APK_PATH="android/app/build/outputs/apk/release/app-release.apk"
if [[ ! -f "$APK_PATH" ]]; then
  echo "FAIL: release APK not found at $APK_PATH"
  exit 1
fi
echo "$APK_PATH"

echo
echo "==> RC gate: Android device detection"
if [[ -z "$ADB_BIN" ]]; then
  echo "BLOCKED: adb not found. Set ADB_BIN or install Android platform-tools."
  exit 2
fi

"$ADB_BIN" start-server >/dev/null
device_output="$("$ADB_BIN" devices -l)"
echo "$device_output"

device_count="$(printf '%s\n' "$device_output" | awk 'NR>1 && $2=="device" { count += 1 } END { print count + 0 }')"
if [[ "$device_count" -lt 1 ]]; then
  echo
  echo "BLOCKED: no Android device attached. Connect a real device, then rerun:"
  echo "  npm run verify:rc-android"
  exit 2
fi

echo
echo "PASS: automated RC gates succeeded and Android device is attached."
echo "Next: execute scripts/android-rc-blocker-checklist.md on the device."
