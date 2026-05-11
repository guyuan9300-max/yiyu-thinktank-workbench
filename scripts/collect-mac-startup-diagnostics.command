#!/bin/bash
set -u

TS="$(date +%Y%m%d-%H%M%S)"
OUT="$HOME/Desktop/yiyu-startup-diagnostics-$TS.txt"
APP_NAME="益语智库自用平台 V2.0.app"
EXE_NAME="益语智库自用平台 V2.0"

exec > >(tee -a "$OUT") 2>&1

echo "Yiyu startup diagnostics"
echo "timestamp=$TS"
echo "output=$OUT"
echo

echo "== System =="
sw_vers || true
echo "arch=$(uname -m)"
echo "user=$(whoami)"
echo

echo "== Locate app =="
CANDIDATES=(
  "$HOME/Applications/$APP_NAME"
  "/Applications/$APP_NAME"
  "$HOME/Desktop/$APP_NAME"
  "$HOME/Downloads/$APP_NAME"
)

APP_PATH=""
for candidate in "${CANDIDATES[@]}"; do
  if [[ -d "$candidate" ]]; then
    APP_PATH="$candidate"
    break
  fi
done

if [[ -z "$APP_PATH" ]]; then
  echo "APP_NOT_FOUND"
  echo "Searched standard locations. Matching files nearby:"
  find "$HOME/Desktop" "$HOME/Downloads" "$HOME/Applications" -maxdepth 2 -name "$APP_NAME" -print 2>/dev/null | sed -n '1,40p'
  echo
  echo "DONE: $OUT"
  exit 2
fi

echo "app=$APP_PATH"
EXE_PATH="$APP_PATH/Contents/MacOS/$EXE_NAME"
INFO_PLIST="$APP_PATH/Contents/Info.plist"
echo "exe=$EXE_PATH"
echo

echo "== App metadata =="
if [[ -f "$INFO_PLIST" ]]; then
  /usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$INFO_PLIST" 2>/dev/null || true
  /usr/libexec/PlistBuddy -c 'Print :CFBundleVersion' "$INFO_PLIST" 2>/dev/null || true
fi
if [[ -f "$EXE_PATH" ]]; then
  file "$EXE_PATH" || true
  lipo -archs "$EXE_PATH" || true
else
  echo "EXECUTABLE_NOT_FOUND"
fi
echo

echo "== Signature and Gatekeeper =="
codesign --verify --deep --strict --verbose=4 "$APP_PATH" || true
codesign -dv --verbose=4 "$APP_PATH" 2>&1 | sed -n '1,120p' || true
spctl -a -vv --type execute "$APP_PATH" || true
echo

echo "== Quarantine attributes =="
xattr -l "$APP_PATH" || true
echo

echo "== Launch =="
open "$APP_PATH" || true
sleep 12
echo

echo "== Processes =="
pgrep -fl "$EXE_NAME|YiyuThinkTankWorkbench2|backend-venv/bin/python|uvicorn" || true
echo

echo "== Electron bootstrap log =="
tail -n 160 /tmp/yiyu-thinktank-electron-bootstrap.log 2>/dev/null || true
echo

echo "== App launch log =="
LOG_DIR="$HOME/Library/Application Support/YiyuThinkTankWorkbench2/logs"
tail -n 240 "$LOG_DIR/electron-launch.log" 2>/dev/null || true
echo

echo "== Recent macOS logs =="
log show \
  --predicate 'process CONTAINS "益语智库" OR eventMessage CONTAINS "YiyuThinkTankWorkbench2" OR eventMessage CONTAINS "yiyu-thinktank"' \
  --last 5m \
  --style compact 2>/dev/null | tail -n 240 || true
echo

echo "DONE: $OUT"
