"""Markdown → .docx 渲染器（python-docx）。

主要给录音转写的会议纪要用：LLM 摘要返回 markdown，后端在挂附件前把它转成 .docx，
这样用户在任务详情里双击附件能直接用 Word / Pages 打开和编辑，而不是看一份 .md 源码。

只支持常见 markdown subset（标题、列表、加粗、普通段落）——会议纪要的结构一般就这些，
不需要完整的 markdown 引擎。其他没识别的语法当作普通段落原样输出。
"""

from __future__ import annotations

import re
from io import BytesIO

_BOLD_PATTERN = re.compile(r"\*\*(.+?)\*\*")
_BULLET_PATTERN = re.compile(r"^[-*+]\s+")
_NUMBERED_PATTERN = re.compile(r"^\d+\.\s+")


def _add_paragraph_with_inline_bold(paragraph, text: str) -> None:
    """把 **xx** 标记的部分作为 bold run 插入到段落里。"""
    cursor = 0
    for match in _BOLD_PATTERN.finditer(text):
        if match.start() > cursor:
            paragraph.add_run(text[cursor : match.start()])
        run = paragraph.add_run(match.group(1))
        run.bold = True
        cursor = match.end()
    if cursor < len(text):
        paragraph.add_run(text[cursor:])


def render_markdown_to_docx_bytes(
    markdown_text: str,
    *,
    document_title: str | None = None,
) -> bytes:
    """渲染 markdown → .docx 字节流。

    支持：
      - `# / ## / ### / #### / #####` 标题（对应 docx heading 1-5）
      - `- / * / +` 无序列表
      - `1. / 2. ...` 有序列表
      - `**加粗**` 内联加粗
      - 普通段落（含中文）
    """
    # 延迟 import 避免 backend 启动时间被 python-docx 拖慢
    from docx import Document  # type: ignore[import-not-found]

    doc = Document()
    if document_title:
        doc.add_heading(document_title, level=0)

    for raw_line in markdown_text.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            # 空行 → 段落分隔
            doc.add_paragraph()
            continue
        # 标题
        if line.startswith("#####"):
            doc.add_heading(line.lstrip("#").strip(), level=5)
            continue
        if line.startswith("####"):
            doc.add_heading(line.lstrip("#").strip(), level=4)
            continue
        if line.startswith("###"):
            doc.add_heading(line.lstrip("#").strip(), level=3)
            continue
        if line.startswith("##"):
            doc.add_heading(line.lstrip("#").strip(), level=2)
            continue
        if line.startswith("#"):
            doc.add_heading(line.lstrip("#").strip(), level=1)
            continue
        # 列表
        bullet_match = _BULLET_PATTERN.match(line)
        if bullet_match:
            text = line[bullet_match.end() :]
            paragraph = doc.add_paragraph(style="List Bullet")
            _add_paragraph_with_inline_bold(paragraph, text)
            continue
        numbered_match = _NUMBERED_PATTERN.match(line)
        if numbered_match:
            text = line[numbered_match.end() :]
            paragraph = doc.add_paragraph(style="List Number")
            _add_paragraph_with_inline_bold(paragraph, text)
            continue
        # 普通段落
        paragraph = doc.add_paragraph()
        _add_paragraph_with_inline_bold(paragraph, line)

    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()
