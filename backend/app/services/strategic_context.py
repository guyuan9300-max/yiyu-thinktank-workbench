"""客户战略文档 (战略定位 + 业务方法论) 的 prompt 注入 helper.

设计哲学 — 连锁克制 (Chained Honesty):
  用户没上传这两份 .md 时, AI 不允许编造客户的战略基线.
  在所有需要"战略层判断"的 LLM 调用前注入约束 prompt, 让 LLM 在输出文本里
  主动声明"我没看到战略文档, 此处判断可能不准", 而不是用替代算法补一个
  看着合理但实际可能错的答案.

  这样用户读 AI 输出时, 句子开头就告诉他可信度有保留 — 不需要 UI 额外
  贴警告条 (容易被忽略), 也不需要弹窗 (烦人).

用法:
  from app.services.strategic_context import get_strategic_context_for_prompt
  ctx = get_strategic_context_for_prompt(db, client_id)
  prompt = ctx["prompt_prefix"] + your_original_prompt + ctx["honesty_clause_appendix"]
"""
from __future__ import annotations

import sqlite3
from typing import TypedDict


class StrategicContext(TypedDict):
    configured: bool                  # 战略+方法论 都已上传
    has_strategy: bool
    has_methodology: bool
    strategy_md: str
    methodology_md: str
    prompt_prefix: str                # 拼在 user prompt 前面, 给 LLM 上下文 + 约束
    honesty_clause_appendix: str      # (可选) 拼在 prompt 末尾, 强调诚实声明要求


def get_strategic_context_for_prompt(
    db: sqlite3.Connection,
    client_id: str,
) -> StrategicContext:
    """读客户的战略文档, 返回 prompt 注入需要的全部上下文."""
    try:
        rows = db.execute(
            """SELECT doc_type, file_name, md_content
               FROM client_strategic_documents WHERE client_id = ?""",
            (client_id,),
        ).fetchall()
    except sqlite3.Error:
        rows = []
    docs = {str(r["doc_type"]): {
        "file_name": str(r["file_name"] or ""),
        "md_content": str(r["md_content"] or ""),
    } for r in rows}
    has_strategy = "strategy" in docs and bool(docs["strategy"]["md_content"].strip())
    has_methodology = "methodology" in docs and bool(docs["methodology"]["md_content"].strip())
    strategy_md = docs.get("strategy", {}).get("md_content", "") if has_strategy else ""
    methodology_md = docs.get("methodology", {}).get("md_content", "") if has_methodology else ""

    configured = has_strategy and has_methodology

    if configured:
        prompt_prefix = (
            "## 客户已上传的战略基线 (官方文档, 可信度高)\n\n"
            f"### 战略文档 ({docs['strategy']['file_name']})\n"
            f"{strategy_md}\n\n"
            f"### 方法论文档 ({docs['methodology']['file_name']})\n"
            f"{methodology_md}\n\n"
            "---\n"
            "⚙️ 使用约束: 凡是涉及战略层/方法论判断的地方, 必须基于以上两份文档. "
            "不要脱离文档自由发挥. 如果某个具体问题文档没覆盖, 老实说『文档没明确, "
            "以下仅就字面判断』, 不要从其他碎片资料推断战略含义.\n\n"
        )
        honesty_clause_appendix = ""
    elif has_strategy or has_methodology:
        which = "战略文档" if has_strategy else "方法论文档"
        missing = "方法论文档" if has_strategy else "战略文档"
        partial_md = strategy_md if has_strategy else methodology_md
        partial_label = docs["strategy"]["file_name"] if has_strategy else docs["methodology"]["file_name"]
        prompt_prefix = (
            f"## 客户部分上传的战略基线\n\n"
            f"### 已上传: {which} ({partial_label})\n"
            f"{partial_md}\n\n"
            "---\n"
            f"⚠️ 关键约束: 此客户**只上传了{which}, 未上传{missing}**. "
            f"凡是涉及{missing.replace('文档', '')}相关的判断, 你必须在输出开头声明:\n"
            f"  『我看到了{which}, 但客户的{missing}还没上传, 以下涉及"
            f"{missing.replace('文档', '')}的判断主要基于碎片资料和该领域的通用经验, "
            "战略层判断可能不准.』\n"
            f"在涉及{missing.replace('文档', '')}的部分, 用『看上去/可能/初步看』"
            "替代笃定语气, 避免编造结论性表述.\n\n"
        )
        honesty_clause_appendix = ""
    else:
        prompt_prefix = (
            "## ⚠️ 客户战略文档未配置\n\n"
            "此客户**尚未上传战略文档和方法论文档**. 这两份是品牌监控、提案、"
            "情报匹配等模块判断客户事情的关键基线.\n\n"
            "---\n"
            "⚠️ 关键约束: 你**不允许编造客户的战略定位或方法论**. "
            "你必须在输出第一句明确写:\n"
            "  『我在客户资料里没找到足够多的战略方向内容和明确的业务方法论, "
            "以下分析主要基于碎片文件和该领域的独特经验, 战略层判断可能不准, "
            "建议先上传战略文档.md和方法论文档.md.』\n\n"
            "在涉及战略层的判断时, 用『看上去/可能/初步看』替代笃定语气. "
            "宁可只就具体事实回答, 也不要硬推战略结论.\n\n"
        )
        honesty_clause_appendix = ""

    return {
        "configured": configured,
        "has_strategy": has_strategy,
        "has_methodology": has_methodology,
        "strategy_md": strategy_md,
        "methodology_md": methodology_md,
        "prompt_prefix": prompt_prefix,
        "honesty_clause_appendix": honesty_clause_appendix,
    }


__all__ = ["StrategicContext", "get_strategic_context_for_prompt"]
