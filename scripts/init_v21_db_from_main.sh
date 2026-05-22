#!/bin/bash
# V2.1 Lab db 初始化 — 从主仓库 prod db 复制一份独立副本 (顾源源 5/22 方案 C)
#
# 用途: 首次启动 V2.1 lab 前跑一次, 把主仓库当前 db 复制到 V2.1 lab userData,
# 之后 V2.1 lab db 独立演化, 不污染主仓库.
#
# 跑法: bash scripts/init_v21_db_from_main.sh

set -e

MAIN_DB="$HOME/Library/Application Support/YiyuThinkTankWorkbench2/app.db"
LAB_DIR="$HOME/Library/Application Support/YiyuThinkTankWorkbench2_V21Lab"
LAB_DB="$LAB_DIR/app.db"

echo "==============================================="
echo "  V2.1 Lab db 初始化"
echo "  源 (主仓库): $MAIN_DB"
echo "  目标 (V2.1 lab): $LAB_DB"
echo "==============================================="

if [ ! -f "$MAIN_DB" ]; then
    echo "✗ 主仓库 db 不存在: $MAIN_DB"
    echo "  先启动主仓库 app 让它生成 db, 再跑本脚本"
    exit 1
fi

# 看主仓库 db 大小
MAIN_SIZE=$(stat -f %z "$MAIN_DB" 2>/dev/null || stat -c %s "$MAIN_DB")
echo ""
echo "▸ 主仓库 db 大小: $((MAIN_SIZE / 1024 / 1024)) MB"

# 检查目标
if [ -f "$LAB_DB" ]; then
    LAB_SIZE=$(stat -f %z "$LAB_DB" 2>/dev/null || stat -c %s "$LAB_DB")
    echo ""
    echo "⚠️  V2.1 lab db 已存在, 大小: $((LAB_SIZE / 1024 / 1024)) MB"
    read -p "覆盖? (V2.1 lab 现有数据会丢失!) [y/N] " ans
    if [ "$ans" != "y" ] && [ "$ans" != "Y" ]; then
        echo "已取消"
        exit 0
    fi
fi

# 创建目录
mkdir -p "$LAB_DIR"

# 复制 db (含 -wal / -shm 一起复制以保证一致性)
echo ""
echo "▸ 复制 db..."
cp "$MAIN_DB" "$LAB_DB"

# 清掉 wal/shm 副本 (避免引用过期连接)
for ext in "-wal" "-shm"; do
    [ -f "$MAIN_DB$ext" ] && cp "$MAIN_DB$ext" "$LAB_DB$ext" || true
done

echo "✓ db 复制完成"
echo ""
echo "▸ 验证:"
ls -la "$LAB_DIR/"
echo ""
echo "==============================================="
echo "  完成. 现在可以跑:"
echo "    bash scripts/run-v21-lab.sh"
echo "==============================================="
