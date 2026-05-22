#!/usr/bin/env bash
# [B] M-G · 装 git post-commit hook (V2.1 仓库 + 主仓库 都装)
#
# 服务: docs/B_AI_SYNC_20260522_M_G_EVALUATOR_AUTOMATION.md §Task 2
# 目的: 检测到 ingest/collector/generator/extractor 关键文件改动后,
#       后台跑双层 baseline, 5 分钟内出 L1+L2 P% 报告
#
# 用法:
#   cd ~/openclaw/workspace/V2.1
#   bash scripts/install-eval-hook.sh           # 装 V2.1 仓库 hook
#   bash scripts/install-eval-hook.sh --main    # 同时装主仓库 hook
#
# 卸载:
#   bash scripts/install-eval-hook.sh --uninstall
set -euo pipefail

V21_REPO="$HOME/openclaw/workspace/V2.1"
MAIN_REPO="$HOME/openclaw/workspace/yiyu-thinktank-workbench"
HOOK_NAME="post-commit"

HOOK_CONTENT='#!/usr/bin/env bash
# [B] M-G auto-eval hook — 自动 trigger 双层 baseline
# 触发条件: commit 改了 ingest_pipeline / narrative_collector / narrative_generator
#         / document_llm_extractor / smart_file_import / 任务复盘相关
# 详见: ~/openclaw/workspace/V2.1/docs/B_AI_SYNC_20260522_M_G_EVALUATOR_AUTOMATION.md

# 拿到当前 commit 的改动文件
CHANGED=$(git diff HEAD~1 HEAD --name-only 2>/dev/null || git diff --cached --name-only 2>/dev/null || echo "")

# 触发关键字 (sync 指令 §Task 2 + B 加 smart_file_import / task_review)
TRIGGER_PATTERN="narrative_collector|narrative_generator|ingest_pipeline|document_llm_extractor|smart_file_import|event_line_activities|task_review|metadata_for_"

if echo "$CHANGED" | grep -qE "$TRIGGER_PATTERN"; then
    COMMIT_SHA=$(git rev-parse --short HEAD)
    COMMIT_MSG=$(git log -1 --pretty=%s | head -c 80)
    TRIGGER_SUMMARY="${COMMIT_SHA}: ${COMMIT_MSG}"

    echo ""
    echo "[auto-eval] 检测到关键文件改动 (commit $COMMIT_SHA), 后台跑双层 baseline..."
    echo "[auto-eval] 改动: $(echo "$CHANGED" | grep -E "$TRIGGER_PATTERN" | head -3 | tr "\n" " ")"

    BASELINE_SCRIPT="$HOME/openclaw/workspace/V2.1/scripts/run_v22_dual_layer_baseline.py"
    PYTHON_BIN="$HOME/openclaw/workspace/yiyu-thinktank-workbench/backend/.venv/bin/python3"

    if [ ! -f "$BASELINE_SCRIPT" ]; then
        echo "[auto-eval] ✗ baseline script 不存在: $BASELINE_SCRIPT, 跳过"
        exit 0
    fi
    if [ ! -x "$PYTHON_BIN" ]; then
        echo "[auto-eval] ✗ python 不在 venv: $PYTHON_BIN, 跳过"
        exit 0
    fi

    # 后台跑, 不阻塞 commit
    LOG="/tmp/auto_eval_${COMMIT_SHA}.log"
    nohup "$PYTHON_BIN" "$BASELINE_SCRIPT" "日慈基金会" "$TRIGGER_SUMMARY" >"$LOG" 2>&1 &
    PID=$!
    echo "[auto-eval] 后台 PID=$PID, 日志 $LOG"
    echo "[auto-eval] 完成后看: ~/openclaw/workspace/V2.1/docs/AUTO_EVAL_LATEST.md"
    echo ""
fi

exit 0
'

install_hook() {
    local repo="$1"
    local hook_path="$repo/.git/hooks/$HOOK_NAME"

    if [ ! -d "$repo/.git" ]; then
        echo "✗ $repo 不是 git 仓库, 跳过"
        return 1
    fi

    # 备份现有 hook (如有)
    if [ -f "$hook_path" ] && ! grep -q "B M-G auto-eval hook" "$hook_path"; then
        cp "$hook_path" "$hook_path.before-m-g-$(date +%s)"
        echo "  ✓ 备份现有 hook: $hook_path.before-m-g-*"
    fi

    echo "$HOOK_CONTENT" > "$hook_path"
    chmod +x "$hook_path"
    echo "  ✓ 装好: $hook_path"
}

uninstall_hook() {
    local repo="$1"
    local hook_path="$repo/.git/hooks/$HOOK_NAME"
    if [ -f "$hook_path" ] && grep -q "B M-G auto-eval hook" "$hook_path"; then
        rm "$hook_path"
        echo "  ✓ 卸载: $hook_path"
        # 找最新备份还原
        local backup=$(ls -t "$hook_path.before-m-g-"* 2>/dev/null | head -1)
        if [ -n "$backup" ]; then
            mv "$backup" "$hook_path"
            chmod +x "$hook_path"
            echo "  ✓ 还原备份: $hook_path"
        fi
    fi
}

main() {
    local mode="install"
    local also_main=""

    for arg in "$@"; do
        case "$arg" in
            --uninstall) mode="uninstall" ;;
            --main) also_main="yes" ;;
            *) ;;
        esac
    done

    if [ "$mode" = "install" ]; then
        echo "[B M-G] 装 post-commit auto-eval hook"
        echo "▸ V2.1 仓库:"
        install_hook "$V21_REPO"
        if [ "$also_main" = "yes" ]; then
            echo "▸ 主仓库:"
            install_hook "$MAIN_REPO"
        fi
        echo ""
        echo "✓ 完成. 下次 commit 改 ingest/collector/generator/extractor 自动触发."
        echo "  验证: 在 V2.1 改 narrative_kernel.py 一行, git commit, 看输出有没有 [auto-eval]"
    else
        echo "[B M-G] 卸载 post-commit auto-eval hook"
        uninstall_hook "$V21_REPO"
        if [ "$also_main" = "yes" ]; then
            uninstall_hook "$MAIN_REPO"
        fi
    fi
}

main "$@"
