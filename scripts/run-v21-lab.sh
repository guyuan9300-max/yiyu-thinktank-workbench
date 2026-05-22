#!/bin/bash
# V2.1 Lab 模式启动脚本 (顾源源 5/22 方案 C)
#
# 用途: 在主仓库 app 已运行的情况下, 同时启动 V2.1 lab app, 双 app 物理隔离
# - V2.1 app 用端口 47831 (主仓库用 47829, 不冲突)
# - V2.1 userData 用 YiyuThinkTankWorkbench2_V21Lab (主仓库用 YiyuThinkTankWorkbench2, db 独立)
# - V2.1 app bundle id com.yiyu.selfworkbench2.v21lab (主仓库 com.yiyu.selfworkbench2, macOS 允许同跑)
# - V2.1 productName "益语智库 V2.1 Lab" (主仓库 "益语智库自用平台 V2.0")
#
# 跑法:
#     cd ~/openclaw/workspace/V2.1
#     bash scripts/run-v21-lab.sh
#
# 首次跑前: bash scripts/init_v21_db_from_main.sh (从主仓库 db copy 初始数据)
#
# 跑完后顾源源屏幕上会有 2 个 app:
#   - 益语智库自用平台 V2.0 (主仓库, 47829, 稳定运行)
#   - 益语智库 V2.1 Lab    (V2.1 仓库, 47831, 实验数据中心)
# 同一日慈基金会数据, 两个 app 看到的 6 段叙事可对比

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

echo "==============================================="
echo "  V2.1 Lab 模式启动 (YIYU_LAB_MODE=1)"
echo "  仓库: $REPO_ROOT"
echo "  端口: 47831 (backend) + 47832 (cloud)"
echo "  userData: ~/Library/Application Support/YiyuThinkTankWorkbench2_V21Lab"
echo "==============================================="

# 检查初始 db 是否已 copy
LAB_DB_DIR="$HOME/Library/Application Support/YiyuThinkTankWorkbench2_V21Lab"
if [ ! -f "$LAB_DB_DIR/app.db" ]; then
    echo ""
    echo "⚠️  V2.1 lab db 不存在: $LAB_DB_DIR/app.db"
    echo "   首次跑请先执行: bash scripts/init_v21_db_from_main.sh"
    echo ""
    read -p "现在自动初始化? [Y/n] " ans
    if [ "$ans" != "n" ] && [ "$ans" != "N" ]; then
        bash "$REPO_ROOT/scripts/init_v21_db_from_main.sh"
    else
        echo "已退出, 没有初始化"
        exit 1
    fi
fi

# 启动 V2.1 dev:lab (vite 4174 + electron + main tsc-watch)
# dev:lab 是 V2.1 lab 专属脚本, vite port 4174 (主仓库用 4173, 避冲突)
echo ""
echo "▸ 启动 V2.1 lab dev (YIYU_LAB_MODE=1 + vite:4174 + backend:47831)..."
export YIYU_LAB_MODE=1
npm run dev:lab
