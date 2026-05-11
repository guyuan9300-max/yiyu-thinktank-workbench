#!/bin/bash
#
# 一键：构建 → 打 DMG → 复制到桌面 → 打印 sha256
#
# 用法：
#   方式 A  双击 Finder 里这个 .command 文件
#   方式 B  在终端里跑：
#           bash "<repo>/scripts/build-and-ship-dmg.command"
#
# 产物：~/Desktop/益语智库自用平台 V2.0-<timestamp>-arm64-local.dmg
# 日志：~/Desktop/yiyu-build-<timestamp>.log（即使中途失败也会留下）
#
# 退出码：0 成功；非 0 失败（日志里会标 [FAIL] 行）
#

# 注意：macOS 自带 bash 3.2，不开 set -u（与多层变量展开有兼容坑）
# 用 explicit `|| fail` 兜底每一步关键命令

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP_NAME="益语智库自用平台 V2.0"
TS="$(date +%Y%m%d-%H%M%S)"
LOG_PATH="$HOME/Desktop/yiyu-build-$TS.log"
DESKTOP_DIR="$HOME/Desktop"
# package-local-mac-dmg.mjs 默认产物路径（注意：脚本本身不加 -local 后缀，
# -local 是我们对外的命名约定，仅在 cp 到桌面时挂上去用来标识"本机构建非签名版"）
DEFAULT_DMG="$REPO_ROOT/dist/${APP_NAME}-0.1.0-arm64.dmg"
FINAL_DMG="$DESKTOP_DIR/${APP_NAME}-$TS-arm64-local.dmg"
TOTAL=8

# 防御性导出：避免子 shell（如 tee 进程替换内）丢失关键变量
export REPO_ROOT APP_NAME TS LOG_PATH DESKTOP_DIR DEFAULT_DMG FINAL_DMG TOTAL

# 所有输出同时写到日志与 stdout
exec > >(tee -a "$LOG_PATH") 2>&1

say()  { printf "\n>>> %s\n" "$*"; }
fail() { printf "\n[FAIL] %s\n" "$*"; printf "\n日志在：%s\n" "$LOG_PATH"; printf "\n按回车关闭窗口..."; read -r _ignored; exit 1; }
step() { say "[$1/$TOTAL] $2"; }

say "===================================================="
say "  益语智库 DMG 打包一键脚本"
say "  时间戳：$TS"
say "  仓库路径：$REPO_ROOT"
say "  日志：$LOG_PATH"
say "===================================================="

# ----- 0. 环境前置检查 -----
step 0 "环境前置检查"
if [[ "$(uname)" != "Darwin" ]]; then
  fail "此脚本只在 macOS 上运行，当前系统：$(uname)"
fi
if [[ "$(uname -m)" != "arm64" ]]; then
  printf "[WARN] 当前架构是 %s，dist:mac-local 默认产 arm64 包；若同事是 Intel Mac，需要单独走 Intel 构建。\n" "$(uname -m)"
fi
for bin in node npm uv; do
  if ! command -v "$bin" >/dev/null 2>&1; then
    fail "找不到 $bin，请确认已装 Node + npm + uv"
  fi
done
say "node:  $(node --version)"
say "npm:   $(npm --version)"
say "uv:    $(uv --version 2>&1 | head -1)"
say "Repo OK：$REPO_ROOT"

cd "$REPO_ROOT" || fail "无法 cd 到 $REPO_ROOT"

# ----- 1. 工作区状态记录 -----
step 1 "记录 git 状态（仅记录，不修改）"
git status --short 2>&1 | sed 's/^/    /'
say "当前 HEAD：$(git log -1 --oneline 2>&1)"

# ----- 2. 清场（保留旧 DMG 作回滚证据） -----
step 2 "清场：删 dist/mac-arm64 + dist/packaged-runtime（旧 DMG 保留）"
[[ -d dist/mac-arm64 ]] && rm -rf dist/mac-arm64 && say "已删 dist/mac-arm64"
[[ -d dist/packaged-runtime ]] && rm -rf dist/packaged-runtime && say "已删 dist/packaged-runtime"
say "保留：$DEFAULT_DMG（如果存在）"

# ----- 3. 安装依赖（只在 node_modules 缺失时装；package-lock 里有 linux-only
#         的 rollup 原生包条目，npm ci 会因平台失配拒装，所以这里不走 npm ci） -----
step 3 "前端依赖：检查 node_modules"
if [[ ! -d node_modules ]]; then
  say "node_modules 不存在，跑 npm install（用 --no-audit --no-fund 提速）"
  npm install --no-audit --no-fund --ignore-scripts=false 2>&1 || \
    fail "npm install 失败（如果是 EBADPLATFORM，试试 npm install --force）"
else
  say "node_modules 已就绪，直接复用（你之前能跑 npm run build 就说明依赖完整）"
fi

# ----- 4. 构建前端 -----
step 4 "npm run build（前端编译 + tsc 校验）"
npm run build || fail "npm run build 失败（看上方报错；先排 TS 类型错或 Vite 构建错）"

# ----- 5. 构建 packaged-runtime（含 Python seed + wheelhouse） -----
# dist:mac-local 内部会调 build:packaged-runtime
step 5 "npm run dist:mac-local（electron-builder + stabilize + verify-packaged-app）"
npm run dist:mac-local || fail "dist:mac-local 失败（最常见：python-seed 缺 encodings；或 codesign 失败；或 wheelhouse 装包失败）"

# ----- 6. 打 DMG -----
step 6 "node scripts/package-local-mac-dmg.mjs"
node scripts/package-local-mac-dmg.mjs || fail "package-local-mac-dmg.mjs 失败（看上方报错；hdiutil / ditto / verify 任一可能失败）"

if [[ ! -f "$DEFAULT_DMG" ]]; then
  fail "脚本声称成功但 DMG 没找到：$DEFAULT_DMG"
fi
say "DMG 已产出：$DEFAULT_DMG（$(du -h "$DEFAULT_DMG" | awk '{print $1}')）"

# ----- 7. 验证 DMG -----
step 7 "node scripts/verify-mac-dmg.mjs"
node scripts/verify-mac-dmg.mjs || fail "verify-mac-dmg 失败：DMG 校验未过，先别发同事"

# ----- 8. 复制到桌面 + sha256 -----
step 8 "复制到桌面（带时间戳避免覆盖）+ 计算 sha256"
cp "$DEFAULT_DMG" "$FINAL_DMG" || fail "复制到桌面失败"

# 顺便清掉可能被 Finder 挂上的 quarantine 属性（本机 build 通常没有，但保险起见）
xattr -dr com.apple.quarantine "$FINAL_DMG" 2>/dev/null || true

SHA256=$(shasum -a 256 "$FINAL_DMG" | awk '{print $1}')
SIZE=$(du -h "$FINAL_DMG" | awk '{print $1}')

say "===================================================="
say "  ✅ 完成"
say ""
say "  桌面 DMG：$FINAL_DMG"
say "  大小：    $SIZE"
say "  sha256：  $SHA256"
say ""
say "  发同事前必看："
say "    1. 让他们下载完先跑：xattr -dr com.apple.quarantine <dmg path>"
say "    2. 装到 ~/Applications（不是 /Applications），第一次右键打开"
say "    3. 首次启动如报 Python 错误，让他双击 scripts/collect-mac-startup-diagnostics.command"
say ""
say "  完整日志：$LOG_PATH"
say "===================================================="

# 双击运行时窗口默认会立刻关闭，pause 让用户看到结果
printf "\n按回车关闭窗口..."
read -r
