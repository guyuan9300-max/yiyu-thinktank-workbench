"""Chat 意图探测：识别用户的 prompt 是任务型请求还是分析型问答。

任务型 = 用户要求 AI 产出具体产物（表/列表/草稿/摘要）
分析型 = 用户要 AI 给出分析、判断、思考

任务型探测到后，chat 链路会：
1. 强制走单次 LLM（绕过 multipass，避免把"做产物"扩成"做产物的方法论"）
2. system_instruction 加任务执行模式块，强制结构化输出
"""

from __future__ import annotations

import re


# R8：任务型请求探测 —— 只收明确的任务动词，不收"分析/评估/讨论/思考"等分析型词。
TASK_REQUEST_TOKENS: tuple[str, ...] = (
    # 表格类
    "做表", "做一张表", "做一份表", "做个表", "做成表",
    "整理成表", "整理成一张表", "列成表", "列张表", "汇总成表",
    # 表格通用产物（"做一份 / 做一张 + X" 包含表/清单/列表/报告等）
    "做一份", "做一张", "做一个",
    # 提取类
    "提取", "抽取", "抽出", "列出", "列一下", "罗列",
    "整理", "整理成", "整理出",
    # 生成类
    "生成", "输出", "给我一份", "给我一张", "给我列",
    "给一份", "给一张",
    # 转换类
    "总结成", "转成", "改成", "改写成", "重写成",
    # 草拟类
    "写一份", "写一封", "草拟", "起草", "拟一份",
    # 帮我类
    "帮我做", "帮我提", "帮我列", "帮我整理",
    "帮我抽", "帮我生成", "帮我写",
)


def is_task_request(prompt: str) -> bool:
    """探测 prompt 是否为任务型请求（要求 AI 产出具体产物）。

    返回 True 表示走任务执行链路：强制单次 LLM + 强制结构化输出 + 禁止方法论元文档。
    """
    compact = re.sub(r"\s+", "", str(prompt or "")).lower()
    return any(token in compact for token in TASK_REQUEST_TOKENS)


def normalize_markdown_table(text: str) -> str:
    """兜底修复 markdown 表格的三种常见退化：

    1. **单行表格**：所有 `| ... |` 塞一行（行间用空格连接）→ 切回多行
       例：`| 列1 | 列2 | | --- | --- | | 1 | 张 |`
    2. **被 ``` 代码块包裹**：LLM 把表格放进 ```markdown ... ``` 里 → 前端不渲染表格 → 剥离包裹
    3. **表格行间有空行**：header / 分隔行 / 数据行之间隔空行 → GFM 解析器认为表格结束 → 去除空行

    对正常多行表格不做修改。
    """
    if not text or "|" not in text:
        return text

    # 第 1 步：剥离 ```markdown 表格 ``` 这种把表格关进代码块的退化
    # 探测：代码块内部是不是 markdown 表格（有 | ... | --- | 分隔行）
    def _strip_table_codeblock(match: re.Match[str]) -> str:
        inner = match.group(1)
        # 看代码块内部是不是 markdown 表格（至少有一行 `| --- |` 分隔符）
        if re.search(r"\|\s*-{2,}\s*\|", inner):
            return inner.strip() + "\n"
        return match.group(0)  # 非表格代码块原样保留
    text = re.sub(
        r"```(?:markdown|md)?\s*\n(.*?)\n```",
        _strip_table_codeblock,
        text,
        flags=re.DOTALL,
    )

    # 第 2 步：把单行内的多个 `| ... | | ... |` 边界切回多行
    text = re.sub(r"\|[ \t]+\|", "|\n|", text)

    # 第 3 步：去除表格行之间的多余空行
    # 检测连续两个表格行之间夹空行（`| ... |\n\n| ... |` → `| ... |\n| ... |`）
    # 用循环替换以处理多个连续空行
    prev = None
    while prev != text:
        prev = text
        text = re.sub(r"(\|[^\n]*\|)\n\s*\n(\s*\|)", r"\1\n\2", text)

    return text
