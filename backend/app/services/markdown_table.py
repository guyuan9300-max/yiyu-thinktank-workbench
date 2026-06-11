"""Markdown 表格公共解析器 + 导出格式智能识别。

docx 和 xlsx 导出共用这个解析器:
  - parse_markdown_tables(text) → 真返表格列表 [(headers, rows), ...]
  - strip_tables(text) → 真返"去掉所有表格行"的纯文字
  - detect_export_format(text) → 真返 'xlsx' / 'docx', 自动判
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class MarkdownTable:
    """解析出来的真表格。"""

    headers: list[str]
    rows: list[list[str]]
    """每行的真单元格内容 (可能含 markdown 内联标记如 **加粗**)。"""
    heading_above: str = ""
    """真表格上方最近的 markdown 标题 (# / ## / ###), 用作 xlsx sheet 名。
    空 = 没找到上方标题, fallback 用'表格N'命名。"""


# 真表格行: 以 | 起头, 以 | 结尾 (允许周围空格), 中间至少一个 |
_TABLE_ROW_RE = re.compile(r"^\s*\|.+\|\s*$")
# 真分隔行: | --- | :---: | ---: | (允许 :, -, 空格, |)
_TABLE_SEP_RE = re.compile(r"^\s*\|[\s:|\-]+\|\s*$")


def _split_table_cells(line: str) -> list[str]:
    """| a | b | c | → ['a', 'b', 'c']."""
    stripped = line.strip()
    # 去掉首尾的 |
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


# 真识别 markdown 标题行 (# / ## / ### / #### / #####)
_HEADING_RE = re.compile(r"^\s*(#{1,5})\s+(.+?)\s*$")


def _find_heading_above(lines: list[str], table_start_idx: int) -> str:
    """真从 table_start_idx 往回找最近的 markdown 标题, 跳过空行 + 普通段落。

    真规则: 真到上一个表格之前 OR 真扫超过 20 行就停 (避免拿太远的标题).
    """
    n_back = 0
    for idx in range(table_start_idx - 1, -1, -1):
        line = lines[idx]
        if _TABLE_ROW_RE.match(line) or _TABLE_SEP_RE.match(line):
            # 真碰到上一个表格 → 停 (它的 heading 不属于本表格)
            return ""
        match = _HEADING_RE.match(line)
        if match:
            return _strip_heading_marker(match.group(2))
        n_back += 1
        if n_back > 20:
            return ""
    return ""


# 真去掉中文标题的"序号"前缀 (一、 / 二、 / 1. / 2.) 真给 sheet name 更干净
_HEADING_NUMBER_PREFIX_RE = re.compile(
    r"^(?:[一二三四五六七八九十百零]+、|[0-9]+[.、]|[Ⅰ-ⅿ]+\.?|[（(][0-9一二三四五六七八九十]+[）)])\s*"
)


def _strip_heading_marker(heading_text: str) -> str:
    """清理 heading 真用作 sheet name:
      · 去掉序号前缀 (一、 / 二、 / 1. / 等)
      · 真 strip 内联 markdown (**xx**)
      · 真去 evidence badge token [📚...] / [⚠️...]
    """
    text = heading_text.strip()
    # 真去序号前缀
    cleaned = _HEADING_NUMBER_PREFIX_RE.sub("", text).strip()
    # 真去内联 markdown 装饰
    cleaned = markdown_inline_to_plain(cleaned)
    return cleaned or text  # 真不空时返清理版


def parse_markdown_tables(markdown_text: str) -> list[MarkdownTable]:
    """扫真 markdown 文本, 提取所有真表格 (含上方最近标题真用作 sheet name)。

    真识别 pattern:
      ## 机构基础信息表
      | a | b |
      |---|---|
      | 1 | 2 |

    返回 MarkdownTable 列表, heading_above 真带最近 H 标题文本。
    """
    tables: list[MarkdownTable] = []
    lines = markdown_text.split("\n")
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        # 真表格必须: 第 i 行是 table row + 第 i+1 行是 separator row
        if not _TABLE_ROW_RE.match(line):
            i += 1
            continue
        if i + 1 >= n or not _TABLE_SEP_RE.match(lines[i + 1]):
            i += 1
            continue
        # 真找到表头
        headers = _split_table_cells(line)
        if not headers:
            i += 1
            continue
        # 真找上方最近 heading
        heading_above = _find_heading_above(lines, i)
        # 真收集 body rows
        rows: list[list[str]] = []
        j = i + 2  # 跳过 separator
        while j < n and _TABLE_ROW_RE.match(lines[j]):
            cells = _split_table_cells(lines[j])
            # 真补齐 cell 数 = 表头列数 (容错: 用户漏写 |)
            if len(cells) < len(headers):
                cells = cells + [""] * (len(headers) - len(cells))
            elif len(cells) > len(headers):
                cells = cells[: len(headers)]
            rows.append(cells)
            j += 1
        tables.append(MarkdownTable(headers=headers, rows=rows, heading_above=heading_above))
        i = j  # 真跳到表格之后继续扫
    return tables


def strip_tables(markdown_text: str) -> str:
    """返回去掉所有真表格行后的剩余 markdown。

    用于真判"非表格部分有多少纯文字"。
    """
    lines = markdown_text.split("\n")
    out_lines: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        # 判断是不是表格起点
        if _TABLE_ROW_RE.match(line) and i + 1 < n and _TABLE_SEP_RE.match(lines[i + 1]):
            # 真跳过整个表格
            j = i + 2
            while j < n and _TABLE_ROW_RE.match(lines[j]):
                j += 1
            i = j
            continue
        out_lines.append(line)
        i += 1
    return "\n".join(out_lines)


# 阈值: 非表格纯文字 ≥ 这么多字符 → 走 docx (有大段文字)
# 否则 → 走 xlsx (主要是表格 + 标题)
# 顾源源 5/26: "只要有大段文字, Excel 都不合适" → 100 字阈值真合理
#   · "## 表格名" (≤ 15 字) → xlsx
#   · "## 表格名\n一行简短说明" (≤ 50 字) → xlsx
#   · 一段或多段说明 (> 100 字) → docx
EXPORT_FORMAT_TEXT_THRESHOLD = 100


def _count_pure_text_chars(text: str) -> int:
    """真扫去掉:
      - 标题行 (# ... 整行)
      - 空行
      - markdown 标记字符 (* _ ` # > | -)
    剩下的真纯文字字符数。
    """
    cleaned_parts: list[str] = []
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        # 真跳过标题行
        if line.startswith("#"):
            continue
        # 真跳过纯分隔线 (--- 或 ===)
        if re.match(r"^[-=]{3,}$", line):
            continue
        # 真跳过纯列表标记 (- 后接空 / 1. 后接空 — 罕见但稳一下)
        # 真去掉行内 markdown 装饰字符
        clean = re.sub(r"[\*_`#>|\-]", "", line)
        clean = clean.strip()
        if clean:
            cleaned_parts.append(clean)
    return sum(len(part) for part in cleaned_parts)


def detect_export_format(markdown_text: str) -> str:
    """真自动识别导出格式:
      · 无表格 → docx
      · 有表格 AND 非表格纯文字 ≥ 200 → docx (有大段说明文字, 走 Word)
      · 有表格 AND 非表格纯文字 < 200 → xlsx (主要是表格 + 标题, 走 Excel)

    返回: 'xlsx' / 'docx'
    """
    tables = parse_markdown_tables(markdown_text)
    if not tables:
        return "docx"
    non_table_text = strip_tables(markdown_text)
    text_chars = _count_pure_text_chars(non_table_text)
    if text_chars >= EXPORT_FORMAT_TEXT_THRESHOLD:
        return "docx"
    return "xlsx"


# Markdown inline 真去除 (用于 xlsx cell 真显示纯文本, 因为 Excel 不支持 cell 内富文本)
_INLINE_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_INLINE_ITALIC_RE = re.compile(r"(?<!\*)\*([^\*]+?)\*(?!\*)")
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_INLINE_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^\)]+)\)")

# 顾源源 5/26 真用反馈: chat 答案里 [📚 xxx] / [⚠️ 引用失效: xxx] 真 evidence badge token
# 是 chat UI 渲染角标用的, 真不该出现在 Excel cell. 真 strip 掉.
# 真示例:
#   "测试机构A [📚 测试机构A.基金会全称]"  →  "测试机构A"
#   "地方性非公募基金会 [⚠️ 引用失效：「...」不在字典 verified 列表，请...]"  →  "地方性非公募基金会"
_EVIDENCE_BADGE_RE = re.compile(r"\s*\[(?:📚|⚠️|⚠|✓|❌|🔗|🔍)[^\]]*\]\s*")


def markdown_inline_to_plain(text: str) -> str:
    """真去掉 markdown 内联装饰 + evidence badge token, 返纯文本 (供 xlsx cell 用)。

    · **加粗** → 加粗
    · *斜体* → 斜体
    · `code` → code
    · [文字](url) → 文字 (url)  (真保留 url 在括号里, 用户能看到)
    · [📚 xxx] / [⚠️ xxx]  → 真去掉 (evidence badge, 软件 UI 角标真不进 Excel)
    """
    if not text:
        return ""
    out = text
    # 真先 strip evidence badge (在 link 之前, 因为 [📚 ...] 也是 [...] 模式)
    out = _EVIDENCE_BADGE_RE.sub("", out)
    out = _INLINE_LINK_RE.sub(lambda m: f"{m.group(1)} ({m.group(2)})", out)
    out = _INLINE_BOLD_RE.sub(r"\1", out)
    out = _INLINE_ITALIC_RE.sub(r"\1", out)
    out = _INLINE_CODE_RE.sub(r"\1", out)
    # 真 strip 多余空格 (badge 真去掉后可能留双空格)
    out = re.sub(r"  +", " ", out).strip()
    return out
