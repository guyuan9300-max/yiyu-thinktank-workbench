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
        # 修订: 删强制 LLM 复述声明 (会污染所有 narrative 文本); 只保留事实告知 + 语气约束.
        # UI 上已有 StrategicDnaCard 显式标"未配置"提示, 无需 LLM 再重复写在文本里.
        prompt_prefix = (
            f"## 客户部分上传的战略基线\n\n"
            f"### 已上传: {which} ({partial_label})\n"
            f"{partial_md}\n\n"
            "---\n"
            f"⚙️ 使用约束: 此客户只上传了{which}, 未上传{missing}. "
            f"涉及{missing.replace('文档', '')}相关判断时, 用『看上去/可能/初步看』"
            "替代笃定语气, 不要编造结论性表述. 不要在 narrative 文本里复述"
            "『未上传方法论文档』这类元信息 — UI 已有显式标识.\n\n"
        )
        honesty_clause_appendix = ""
    else:
        # 修订: 同上, 删强制复述指令.
        # 原版让 LLM 在每个 narrative 维度第一句复述"我在客户资料里没找到..." → 污染所有客户的战略陪伴.
        # 改成: 事实告知 + 语气约束, 不强制 LLM 把这段元信息写进 narrative 文本.
        prompt_prefix = (
            "## ⚙️ 客户战略文档未配置\n\n"
            "此客户尚未上传战略文档和方法论文档.\n\n"
            "---\n"
            "⚙️ 使用约束: 不允许编造客户的战略定位或方法论. "
            "涉及战略层判断时, 用『看上去/可能/初步看』替代笃定语气. "
            "宁可只就具体事实回答, 也不要硬推战略结论. "
            "不要在 narrative 文本里复述『战略文档未配置』这类元信息 — UI 已有显式标识.\n\n"
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
