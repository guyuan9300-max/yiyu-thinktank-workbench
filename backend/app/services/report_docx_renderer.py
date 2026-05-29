"""R3 · 把 ReportArtifact 渲染为 docx。

输入：ReportArtifact（blueprint + sections，sections.charts 已含 PNG base64）
输出：docx 文件落到磁盘，返回 Path

渲染流程：
1. 封面（标题 / 副标题 / 客户 / 期间）
2. 报告说明（受众 / 基调 / 生成时间 / open_questions）
3. 各章节：标题 + markdown 正文（[CHART:N] 替换为图）+ 数据源段
4. 附录：章节级 warnings 汇总（如有）

支持的 markdown 语法：
- # / ## / ### 标题
- - / * / + 无序列表（按缩进分层级）
- 1. 编号列表
- > callout（连续行合并）
- | a | b | c | 表格（首行表头，第二行 |---| 分隔可选）
- [CHART:N] 占位符 → 嵌入 PNG（来自 SectionContent.charts[N]）
- 空行：忽略
- 其它：按普通段落渲染
"""

from __future__ import annotations

import base64
import io
import logging
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt

from app.models import (
    GeneratedChart,
    ReportArtifact,
    SectionContent,
)
from app.services.report_docx_helpers import (
    COLOR_BRAND,
    COLOR_MUTED,
    add_bullet,
    add_callout,
    add_data_source,
    add_heading,
    add_page_break,
    add_paragraph,
    add_table,
    set_run_font,
)


logger = logging.getLogger(__name__)


_CHART_PLACEHOLDER_RE = re.compile(r"^\s*\[CHART:(\d+)\]\s*$")
_CHART_INLINE_RE = re.compile(r"\[CHART:(\d+)\]")
_NUMBERED_LIST_RE = re.compile(r"^(\s*)(\d+)\.\s+(.*)$")
_TABLE_SEPARATOR_CELL_RE = re.compile(r"^:?-+:?$")


class DocxRenderError(RuntimeError):
    """渲染失败（输入异常、文件写入失败等）。"""


def add_image_from_bytes(
    doc,
    png_bytes: bytes,
    *,
    width_cm: float = 14.5,
    caption: str | None = None,
) -> None:
    """把 PNG bytes 居中插入 docx；可选下方斜体小字图注。"""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run()
    run.add_picture(io.BytesIO(png_bytes), width=Cm(width_cm))
    if caption:
        c = doc.add_paragraph()
        c.alignment = WD_ALIGN_PARAGRAPH.CENTER
        c.paragraph_format.space_after = Pt(10)
        run = c.add_run(caption)
        set_run_font(run, size=9, italic=True, color=COLOR_MUTED)


def render_report_artifact_to_docx(
    artifact: ReportArtifact,
    output_path: Path,
    *,
    client_name: str | None = None,
) -> Path:
    """主入口：把 ReportArtifact 渲染到指定 docx 路径。

    Args:
        artifact: 报告产物（blueprint + sections 内容已起草完成）
        output_path: 目标 docx 路径
        client_name: 可选客户名（blueprint 只有 client_id；前端调用方传名字进来更直观）

    Returns:
        实际写入的 docx 路径（绝对路径）

    Raises:
        DocxRenderError: 输入异常或写入失败
    """
    if not artifact.sections:
        raise DocxRenderError("ReportArtifact 没有任何章节，无法渲染")

    doc = Document()
    for section in doc.sections:
        section.top_margin = Cm(2.5)
        section.bottom_margin = Cm(2.5)
        section.left_margin = Cm(2.5)
        section.right_margin = Cm(2.5)

    blueprint = artifact.blueprint

    _render_cover(doc, blueprint, client_name=client_name)
    add_page_break(doc)

    _render_report_meta(doc, blueprint)
    add_page_break(doc)

    for section_content in artifact.sections:
        _render_section(doc, section_content)

    warnings_aggregate = _collect_warnings(artifact.sections)
    if warnings_aggregate:
        add_page_break(doc)
        _render_warnings_appendix(doc, warnings_aggregate)

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(output_path))
    except Exception as exc:
        raise DocxRenderError(f"写入 docx 失败: {exc}") from exc

    return output_path.resolve()


def render_report_artifact_to_markdown(
    artifact: ReportArtifact,
    output_path: Path,
    *,
    client_name: str | None = None,
) -> Path:
    """把 ReportArtifact 渲染成 markdown 文件（纯文本归档备份）。

    图表用 `![title](data:image/png;base64,...)` 数据 URI 内嵌，
    保证 md 单文件自包含。
    """
    bp = artifact.blueprint
    lines: list[str] = []
    lines.append(f"# {bp.title}")
    if bp.subtitle:
        lines.append(f"\n_{bp.subtitle}_\n")
    lines.append("")
    lines.append(f"**客户**：{client_name or bp.client_id}")
    lines.append(f"**报告期间**：{bp.period_start} ~ {bp.period_end}")
    lines.append(f"**受众**：{bp.audience}")
    lines.append(f"**基调**：{bp.tone}")
    lines.append(f"**生成时间**：{bp.generated_at}")
    lines.append("")
    if bp.open_questions_for_human:
        lines.append("> **需主理人确认的问题**：")
        for q in bp.open_questions_for_human:
            lines.append(f"> - {q}")
        lines.append("")

    for sc in artifact.sections:
        level_prefix = "##" if sc.plan.level == 1 else "###"
        lines.append(f"{level_prefix} {sc.plan.title}")
        lines.append("")
        markdown = _replace_chart_placeholders_with_data_uri(
            sc.markdown, sc.charts
        )
        lines.append(markdown.strip())
        lines.append("")
        if sc.data_source_annotation:
            lines.append(f"> **数据源**：_{sc.data_source_annotation}_")
            lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        output_path.write_text("\n".join(lines), encoding="utf-8")
    except Exception as exc:
        raise DocxRenderError(f"写入 md 失败: {exc}") from exc
    return output_path.resolve()


def convert_docx_to_pdf_via_libreoffice(
    docx_path: Path,
    output_dir: Path,
    *,
    timeout_seconds: int = 90,
) -> Path | None:
    """用 LibreOffice headless 把 docx 转 PDF。

    机器没装 LO 时返回 None，不报错——PDF 是可选产物。
    转换失败时记 warning 返回 None。
    """
    if not docx_path.exists():
        logger.warning("convert_docx_to_pdf: 源文件不存在 %s", docx_path)
        return None

    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        logger.info(
            "convert_docx_to_pdf: 未找到 LibreOffice (soffice/libreoffice)，跳过"
        )
        return None

    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        soffice,
        "--headless",
        "--convert-to",
        "pdf",
        "--outdir",
        str(output_dir),
        str(docx_path),
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        logger.warning(
            "convert_docx_to_pdf: LibreOffice 超时 (%ds)", timeout_seconds
        )
        return None
    except Exception as exc:
        logger.warning("convert_docx_to_pdf: 调用 soffice 异常 %s", exc)
        return None

    expected_pdf = output_dir / (docx_path.stem + ".pdf")
    if result.returncode != 0 or not expected_pdf.exists():
        logger.warning(
            "convert_docx_to_pdf: 转换失败 stderr=%s", result.stderr[:300]
        )
        return None
    return expected_pdf.resolve()


# ============================================================
# 内部辅助
# ============================================================


def _render_cover(doc, blueprint, *, client_name: str | None) -> None:
    add_paragraph(doc, "", space_after=80)
    add_paragraph(
        doc,
        blueprint.title,
        alignment=WD_ALIGN_PARAGRAPH.CENTER,
        size=28,
        bold=True,
        color=COLOR_BRAND,
        space_before=80,
        space_after=20,
        line_spacing=1.2,
    )
    if blueprint.subtitle:
        add_paragraph(
            doc,
            blueprint.subtitle,
            alignment=WD_ALIGN_PARAGRAPH.CENTER,
            size=14,
            italic=True,
            color=COLOR_MUTED,
            space_after=40,
        )
    add_paragraph(doc, "", space_after=60)
    add_paragraph(
        doc,
        f"客户：{client_name or blueprint.client_id}",
        alignment=WD_ALIGN_PARAGRAPH.CENTER,
        size=12,
        space_after=4,
    )
    period_text = (
        f"{blueprint.period_start} ~ {blueprint.period_end}"
        if blueprint.period_start and blueprint.period_end
        else (blueprint.period_start or blueprint.period_end or "—")
    )
    add_paragraph(
        doc,
        f"报告期间：{period_text}",
        alignment=WD_ALIGN_PARAGRAPH.CENTER,
        size=12,
        space_after=4,
        color=COLOR_MUTED,
    )
    add_paragraph(
        doc,
        f"报告类型：{blueprint.report_kind}",
        alignment=WD_ALIGN_PARAGRAPH.CENTER,
        size=11,
        color=COLOR_MUTED,
    )


def _render_report_meta(doc, blueprint) -> None:
    add_heading(doc, "报告说明", level=2)
    add_paragraph(doc, f"目标受众：{blueprint.audience}")
    add_paragraph(doc, f"整体基调：{blueprint.tone}")
    add_paragraph(doc, f"推导主题：{blueprint.inferred_theme}")
    add_paragraph(
        doc,
        f"生成时间：{_format_iso_datetime(blueprint.generated_at)}（由益语智库自动起草，已经过主理人审阅）",
        color=COLOR_MUTED,
        size=10,
    )

    if blueprint.open_questions_for_human:
        questions_text = "需主理人确认的问题：\n" + "\n".join(
            f"• {q}" for q in blueprint.open_questions_for_human
        )
        add_callout(doc, questions_text)


def _render_section(doc, section_content: SectionContent) -> None:
    plan = section_content.plan
    docx_level = 1 if plan.level == 1 else 2
    add_heading(doc, plan.title, level=docx_level)

    _render_markdown_into_doc(
        doc, section_content.markdown, section_content.charts
    )

    if section_content.data_source_annotation:
        add_data_source(doc, section_content.data_source_annotation)


def _render_warnings_appendix(doc, warnings: list[tuple[str, str]]) -> None:
    add_heading(doc, "附录 · 起草警告", level=2)
    add_paragraph(
        doc,
        "以下警告由 AI 起草员在自查时主动 raise，"
        "说明对应章节的事实基础尚不充分，正式发布前请主理人复核：",
        size=10,
        color=COLOR_MUTED,
    )
    for section_title, warning in warnings:
        add_bullet(doc, f"【{section_title}】{warning}")


def _collect_warnings(
    sections: list[SectionContent],
) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for sc in sections:
        for w in sc.warnings:
            if w.strip():
                out.append((sc.plan.title, w.strip()))
    return out


def _render_markdown_into_doc(
    doc, markdown: str, charts: list[GeneratedChart]
) -> None:
    if not markdown:
        return
    lines = markdown.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        m_chart = _CHART_PLACEHOLDER_RE.match(line)
        if m_chart:
            idx = int(m_chart.group(1))
            _embed_chart(doc, idx, charts)
            i += 1
            continue

        # 标题（# / ## / ###）
        if line.startswith("### "):
            add_heading(doc, line[4:].strip(), level=3)
            i += 1
            continue
        if line.startswith("## "):
            add_heading(doc, line[3:].strip(), level=2)
            i += 1
            continue
        if line.startswith("# "):
            # 章节内的 # 视为二级，避免与封面/章节标题冲突
            add_heading(doc, line[2:].strip(), level=2)
            i += 1
            continue

        # 无序列表
        if stripped.startswith(("- ", "* ", "+ ")):
            indent = len(line) - len(line.lstrip())
            level = min(2, indent // 2)
            text = stripped[2:].strip()
            add_bullet(doc, text, level=level)
            i += 1
            continue

        # 编号列表
        num = _NUMBERED_LIST_RE.match(line)
        if num:
            indent_chars = len(num.group(1))
            level = min(2, indent_chars // 2)
            text = f"{num.group(2)}. {num.group(3).strip()}"
            add_bullet(doc, text, level=level)
            i += 1
            continue

        # callout（连续 > ... ）
        if stripped.startswith("> "):
            quote_lines: list[str] = []
            while i < len(lines) and lines[i].strip().startswith("> "):
                quote_lines.append(lines[i].strip()[2:].strip())
                i += 1
            add_callout(doc, "\n".join(quote_lines))
            continue
        if stripped == ">":
            i += 1
            continue

        # 表格
        if stripped.startswith("|"):
            table_lines: list[str] = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i].strip())
                i += 1
            _render_table_block(doc, table_lines)
            continue

        # 默认：普通段落（可能含行内 [CHART:N]，需要拆段插图）
        if _CHART_INLINE_RE.search(stripped):
            _render_paragraph_with_inline_charts(doc, stripped, charts)
        else:
            add_paragraph(doc, stripped)
        i += 1


def _render_paragraph_with_inline_charts(
    doc, text: str, charts: list[GeneratedChart]
) -> None:
    """段落内含 `[CHART:N]`：先 emit 文本（删占位符），再依次 emit 图。

    LLM B 经常把图占位符嵌在句子里（"...如时间线[CHART:0]所示。"），
    强行拆段语意会断裂；先输出完整文字（去掉占位），再在段后追加图，
    读者能 infer "本段对应的图在下方"。
    """
    chart_indices = [
        int(m.group(1)) for m in _CHART_INLINE_RE.finditer(text)
    ]
    clean_text = _CHART_INLINE_RE.sub("", text).strip()
    if clean_text:
        add_paragraph(doc, clean_text)
    for idx in chart_indices:
        _embed_chart(doc, idx, charts)


def _embed_chart(
    doc, idx: int, charts: list[GeneratedChart]
) -> None:
    if idx < 0 or idx >= len(charts):
        add_paragraph(
            doc,
            f"[CHART:{idx}]（图表索引越界，已跳过）",
            italic=True,
            color=COLOR_MUTED,
            size=10,
        )
        return
    chart = charts[idx]
    if not chart.png_bytes_base64:
        # table_only / callout_only 不出图，安静跳过
        return
    try:
        png = base64.b64decode(chart.png_bytes_base64)
    except Exception as exc:
        logger.warning("chart %d base64 解码失败: %s", idx, exc)
        return
    caption = chart.hint.caption or chart.hint.title
    add_image_from_bytes(
        doc, png, width_cm=chart.width_cm, caption=caption
    )


def _render_table_block(doc, table_lines: list[str]) -> None:
    if not table_lines:
        return
    parsed_rows = [_parse_table_row(line) for line in table_lines]
    headers = parsed_rows[0]
    rest = parsed_rows[1:]
    if rest and _is_separator_row(rest[0]):
        data_rows = rest[1:]
    else:
        data_rows = rest
    if not headers:
        return
    width = len(headers)
    normalized: list[list[str]] = []
    for row in data_rows:
        padded = row + [""] * max(0, width - len(row))
        normalized.append(padded[:width])
    add_table(doc, headers, normalized)


def _parse_table_row(line: str) -> list[str]:
    stripped = line.strip().strip("|")
    return [cell.strip() for cell in stripped.split("|")]


def _is_separator_row(cells: list[str]) -> bool:
    if not cells:
        return False
    return all(
        _TABLE_SEPARATOR_CELL_RE.match(c.strip()) is not None
        for c in cells
        if c
    )


def _replace_chart_placeholders_with_data_uri(
    markdown: str, charts: list[GeneratedChart]
) -> str:
    """把 markdown 里的 [CHART:N] 替换成 data URI 内嵌图。"""
    def _replace(match: re.Match) -> str:
        idx = int(match.group(1))
        if idx < 0 or idx >= len(charts):
            return match.group(0)
        chart = charts[idx]
        if not chart.png_bytes_base64:
            return ""
        caption = chart.hint.caption or chart.hint.title
        return (
            f"\n\n![{caption}](data:image/png;base64,"
            f"{chart.png_bytes_base64})\n\n"
        )

    return re.sub(r"\[CHART:(\d+)\]", _replace, markdown)


def _format_iso_datetime(iso: str) -> str:
    """把 ISO 8601 时间转成更易读的"2026-05-12 17:43"。失败返回原值。"""
    try:
        cleaned = iso.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return iso
