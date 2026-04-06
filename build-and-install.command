#!/bin/bash
set -e
cd "$(dirname "$0")"
echo "========================================="
echo "  益语智库 - 打包并安装桌面版"
echo "========================================="
echo ""
echo "[1/4] npm run build ..."
npm run build 2>&1
echo ""
echo "[2/4] npm run dist:mac-local ..."
npm run dist:mac-local 2>&1
echo ""
echo "[3/4] npm run install:mac-local ..."
npm run install:mac-local 2>&1
echo ""
echo "[4/4] 关闭旧版并重新打开 ..."
pkill -x "益语智库自用平台" 2>/dev/null || true
sleep 2
open "/Users/guyuanyuan/Applications/益语智库自用平台.app"
echo ""
echo "========================================="
echo "  完成！桌面版已重新启动。"
echo "========================================="
echo ""
