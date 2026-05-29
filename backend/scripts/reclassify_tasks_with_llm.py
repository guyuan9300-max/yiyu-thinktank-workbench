"""C · 用 LLM 重分类 tasks.business_category

用途：把"未分类"（之前 fallback 兜底的"专项推进"）的任务用 LLM 重新分类到
6 个真实业务类目里。

默认 dry-run，加 --apply 才真正写 db。

用法：
    # 看建议（默认 dry-run）
    .venv/bin/python scripts/reclassify_tasks_with_llm.py --user user_admin_demo

    # 真正写回 db
    .venv/bin/python scripts/reclassify_tasks_with_llm.py --user user_admin_demo --apply

    # 限制条数
    .venv/bin/python scripts/reclassify_tasks_with_llm.py --user user_admin_demo --limit 20

依赖：qwen3-vl:32b（复用现有本地模型）。如果 Ollama 不可用，会回退到 cloud
模型；都不可用时退出。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# 把项目根加进 path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db import Database
from app.services import ai as ai_service


CATEGORIES = [
    "产品化沉淀",
    "组织协同",
    "管理机制",
    "业务扩展",
    "项目推进",
    "外部合作",
    "主要业务",
]
CATEGORIES_TEXT = "\n".join(f"  · {c}" for c in CATEGORIES)


SYSTEM_PROMPT = f"""你是一个企业工作分类专家。这是一家战略咨询公司。根据任务标题、描述、关联客户、项目模块名等信息，判断这条任务属于以下类目中的哪一个：

{CATEGORIES_TEXT}

类目语义说明：
- 产品化沉淀：把经验/标准/模板沉淀成可复用资产（手册、知识库、归档、官网设计、系统设计）
- 组织协同：内部多人协调（审批、复核、确认、对齐、同步、协同、会签）
- 管理机制：建立流程、规则、制度、治理机制
- 业务扩展：对外开拓（拜访、约见、合作、报价、客户赋能）
- 项目推进：具体交付（开发、上线、实施、演示、需求）
- 外部合作：跨组织合作（伙伴、联盟、生态、开源）
- 主要业务：战略咨询公司的核心业务工作（客户战略陪伴、研究、洞察等）—— 不能明确归到上面 6 类时归到这里

只输出一个 JSON，格式：{{"category": "XXX", "confidence": 0.0-1.0, "reason": "一句话原因"}}
"""


def _build_prompt(row) -> str:
    parts = []
    parts.append(f"标题：{row['title'] or '(无)'}")
    if row.get("description"):
        parts.append(f"描述：{row['description'][:200]}")
    if row.get("client_name"):
        parts.append(f"关联客户：{row['client_name']}")
    if row.get("event_line_name"):
        parts.append(f"事件线：{row['event_line_name']}")
    if row.get("project_module_name"):
        parts.append(f"项目模块：{row['project_module_name']}")
    return "\n".join(parts)


def _ask_llm(prompt: str) -> dict:
    """调 LLM 拿分类结果。优先 ollama 本地，失败 fallback 云端。"""
    try:
        # 尝试本地 qwen3-vl
        result_text = ai_service.invoke_local_text_model(
            system=SYSTEM_PROMPT,
            user=prompt,
            model="qwen3-vl:32b",
            max_tokens=200,
            timeout=15,
        )
    except Exception as e_local:
        try:
            result_text = ai_service.invoke_cloud_text_model(
                system=SYSTEM_PROMPT,
                user=prompt,
                max_tokens=200,
                timeout=20,
            )
        except Exception as e_cloud:
            return {
                "category": "未分类",
                "confidence": 0.0,
                "reason": f"local: {type(e_local).__name__}; cloud: {type(e_cloud).__name__}",
            }
    try:
        # 提取 JSON
        text = result_text.strip()
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
    except Exception:
        pass
    return {"category": "主要业务", "confidence": 0.0, "reason": "解析失败: " + result_text[:100]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", required=True, help="user_id (如 user_admin_demo)")
    parser.add_argument("--apply", action="store_true", help="真正写回 db（默认 dry-run）")
    parser.add_argument("--limit", type=int, default=0, help="限制处理条数（默认全部）")
    parser.add_argument("--db", default=None, help="db 路径（默认从 YIYU_WORKBENCH_DATA_DIR 找）")
    args = parser.parse_args()

    db_path = args.db or os.path.join(
        os.environ.get("YIYU_WORKBENCH_DATA_DIR")
        or str(Path.home() / "Library" / "Application Support" / "YiyuThinkTankWorkbench2"),
        "app.db",
    )
    print(f"DB: {db_path}")
    print(f"User: {args.user}")
    print(f"Mode: {'APPLY (写回 db)' if args.apply else 'DRY-RUN (只打印建议)'}")
    print()

    db = Database(db_path)

    # 拉所有「未分类」或「专项推进」的 tasks
    query = """
        SELECT t.id, t.title, t.description,
               t.business_category AS current_category,
               t.event_line_id, t.client_id,
               c.name AS client_name
        FROM tasks t
        LEFT JOIN clients c ON c.id = t.client_id
        WHERE t.owner_id = ?
          AND t.business_category IN ('主要业务', '未分类', '专项推进', '')
        ORDER BY t.created_at DESC
    """
    rows = db.fetchall(query, (args.user,))
    print(f"待重分类任务: {len(rows)} 条")
    if args.limit > 0:
        rows = rows[: args.limit]
        print(f"限制处理: {len(rows)} 条")
    print()

    new_counts: dict[str, int] = {}
    unchanged = 0
    written = 0

    for i, row in enumerate(rows, 1):
        prompt = _build_prompt(dict(row))
        t0 = time.time()
        result = _ask_llm(prompt)
        cost = time.time() - t0
        new_cat = result.get("category", "未分类")
        conf = float(result.get("confidence") or 0)
        reason = result.get("reason", "")[:60]

        marker = "✓" if conf >= 0.6 and new_cat != "主要业务" else "?"
        print(f"  [{i:>3}/{len(rows)}] {marker} {cost:>4.1f}s  {row['current_category']:>5s}→{new_cat:<10s} conf={conf:.2f}  {row['title'][:30]!r}")
        if reason:
            print(f"          reason: {reason}")

        new_counts[new_cat] = new_counts.get(new_cat, 0) + 1

        # 只有高置信度且分到细分类目（非主要业务）才覆盖原值
        if new_cat != "主要业务" and conf >= 0.5 and new_cat in CATEGORIES:
            if args.apply:
                db.execute(
                    "UPDATE tasks SET business_category = ?, updated_at = datetime('now') WHERE id = ?",
                    (new_cat, str(row["id"])),
                )
                written += 1
        else:
            unchanged += 1

    print()
    print("=" * 50)
    print(f"分类分布:")
    for cat, cnt in sorted(new_counts.items(), key=lambda x: -x[1]):
        print(f"  {cat:>10s}: {cnt:>3d}")
    print()
    print(f"高置信度（≥0.5）可写回: {len(rows) - unchanged}")
    print(f"低置信度保持未分类: {unchanged}")
    if args.apply:
        print(f"✅ 已写回 db: {written} 条")
    else:
        print(f"🔍 DRY-RUN 模式，未写回。加 --apply 真正更新")


if __name__ == "__main__":
    main()
