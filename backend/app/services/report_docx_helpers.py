"""生成日慈基金会战略陪伴报告（Q1 2026）的 Word 版本。

设计要点：
- 中文字体：微软雅黑（跨平台兼容）
- 英文字体：Arial
- 品牌色：益语蓝 #2E75B6
- 段落规范：标题层级清晰、表格统一样式、数据源标注用斜体灰色
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING
from docx.oxml.ns import nsmap, qn
from docx.shared import Cm, Pt, RGBColor
from docx.oxml import OxmlElement

OUTPUT_PATH = Path("/sessions/nifty-zen-euler/mnt/yiyu-thinktank-workbench/docs/日慈战略陪伴报告-Q1-2026.docx")

# ============ 设计 token ============
FONT_CN = "微软雅黑"
FONT_EN = "Arial"
COLOR_BRAND = RGBColor(0x2E, 0x75, 0xB6)  # 益语蓝
COLOR_TEXT = RGBColor(0x33, 0x33, 0x33)
COLOR_MUTED = RGBColor(0x88, 0x88, 0x88)
COLOR_TABLE_HEADER_BG = "2E75B6"  # 蓝色表头
COLOR_TABLE_ALT_BG = "F5F8FB"  # 浅蓝交替
COLOR_BORDER = "CCCCCC"


# ============ 工具函数 ============

def set_run_font(run, size=11, bold=False, color=COLOR_TEXT, italic=False):
    """设置 Run 的字体属性，中英文都用微软雅黑/Arial。"""
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color
    run.font.name = FONT_EN
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.insert(0, rFonts)
    rFonts.set(qn("w:eastAsia"), FONT_CN)
    rFonts.set(qn("w:ascii"), FONT_EN)
    rFonts.set(qn("w:hAnsi"), FONT_EN)


def add_paragraph(doc, text="", *, style=None, alignment=None, size=11,
                  bold=False, italic=False, color=COLOR_TEXT, line_spacing=1.5,
                  space_before=0, space_after=6):
    """添加段落并应用统一样式。"""
    p = doc.add_paragraph()
    if style:
        p.style = doc.styles[style]
    if alignment:
        p.alignment = alignment
    p.paragraph_format.line_spacing = line_spacing
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    if text:
        run = p.add_run(text)
        set_run_font(run, size=size, bold=bold, italic=italic, color=color)
    return p


def add_heading(doc, text, level=1):
    """统一的标题样式（不依赖默认 heading 样式）。"""
    config = {
        1: dict(size=22, color=COLOR_BRAND, space_before=18, space_after=10),
        2: dict(size=16, color=COLOR_BRAND, space_before=14, space_after=8),
        3: dict(size=13, color=COLOR_TEXT, space_before=10, space_after=6),
    }[level]
    return add_paragraph(
        doc, text,
        size=config["size"],
        bold=True,
        color=config["color"],
        space_before=config["space_before"],
        space_after=config["space_after"],
        line_spacing=1.3,
    )


def add_data_source(doc, text):
    """添加'数据源'标注，左侧蓝色粗线 + 斜体灰色小字。"""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(10)
    p.paragraph_format.left_indent = Cm(0.5)
    # 左侧粗线（用边框 XML）
    pPr = p._element.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    left_border = OxmlElement("w:left")
    left_border.set(qn("w:val"), "single")
    left_border.set(qn("w:sz"), "12")
    left_border.set(qn("w:space"), "8")
    left_border.set(qn("w:color"), "2E75B6")
    pBdr.append(left_border)
    pPr.append(pBdr)
    # 文本
    label_run = p.add_run("数据源 ")
    set_run_font(label_run, size=9, bold=True, color=COLOR_BRAND)
    body_run = p.add_run(text)
    set_run_font(body_run, size=9, italic=True, color=COLOR_MUTED)
    return p


def add_bullet(doc, text, *, level=0, size=11, bold=False):
    """添加无序列表项（用缩进 + 圆点）。"""
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Cm(0.6 + level * 0.6)
    p.paragraph_format.line_spacing = 1.5
    p.paragraph_format.space_after = Pt(3)
    bullet_run = p.add_run("• ")
    set_run_font(bullet_run, size=size, color=COLOR_BRAND, bold=True)
    text_run = p.add_run(text)
    set_run_font(text_run, size=size, bold=bold)
    return p


def add_callout(doc, text):
    """添加引用块/重点框（缩进 + 浅色背景）。"""
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Cm(0.5)
    p.paragraph_format.right_indent = Cm(0.5)
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(8)
    run = p.add_run(text)
    set_run_font(run, size=11, italic=True, color=COLOR_TEXT)
    # 添加左侧粗线（用边框 XML）
    pPr = p._element.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    left_border = OxmlElement("w:left")
    left_border.set(qn("w:val"), "single")
    left_border.set(qn("w:sz"), "24")
    left_border.set(qn("w:space"), "12")
    left_border.set(qn("w:color"), "2E75B6")
    pBdr.append(left_border)
    pPr.append(pBdr)
    return p


def set_cell_bg(cell, hex_color):
    """设置单元格背景色。"""
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tcPr.append(shd)


def set_cell_borders(cell, color=COLOR_BORDER, size="4"):
    """设置单元格四边边框（浅灰）。"""
    tcPr = cell._tc.get_or_add_tcPr()
    tcBorders = OxmlElement("w:tcBorders")
    for edge in ("top", "left", "bottom", "right"):
        b = OxmlElement(f"w:{edge}")
        b.set(qn("w:val"), "single")
        b.set(qn("w:sz"), size)
        b.set(qn("w:color"), color)
        tcBorders.append(b)
    tcPr.append(tcBorders)


def add_table(doc, headers, rows, *, widths=None, header_color=COLOR_TABLE_HEADER_BG,
              header_text_color=RGBColor(0xFF, 0xFF, 0xFF), zebra=True):
    """添加统一样式的表格。
    headers: 表头文本列表
    rows: 二维数据
    widths: 列宽（Cm 单位的浮点数列表），可选
    """
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False

    # 表头
    hdr_cells = table.rows[0].cells
    for i, h in enumerate(headers):
        cell = hdr_cells[i]
        set_cell_bg(cell, header_color)
        set_cell_borders(cell)
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        # 清空默认段落
        cell.text = ""
        p = cell.paragraphs[0]
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(2)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(h)
        set_run_font(run, size=10.5, bold=True, color=header_text_color)
        if widths and i < len(widths):
            cell.width = Cm(widths[i])

    # 数据行
    for ri, row_data in enumerate(rows):
        row = table.rows[ri + 1]
        for ci, val in enumerate(row_data):
            cell = row.cells[ci]
            set_cell_borders(cell)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            if zebra and ri % 2 == 1:
                set_cell_bg(cell, COLOR_TABLE_ALT_BG)
            cell.text = ""
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(2)
            run = p.add_run(str(val))
            set_run_font(run, size=10)
            if widths and ci < len(widths):
                cell.width = Cm(widths[ci])

    # 表格后留空
    add_paragraph(doc, "", space_after=4)
    return table


def add_page_break(doc):
    """添加分页符。"""
    p = doc.add_paragraph()
    run = p.add_run()
    run.add_break(WD_BREAK.PAGE)


def add_horizontal_rule(doc):
    """添加水平分隔线。"""
    p = doc.add_paragraph()
    pPr = p._element.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "CCCCCC")
    pBdr.append(bottom)
    pPr.append(pBdr)


# ============ 内容构建 ============

def build():
    doc = Document()

    # 页面：US Letter / A4 由系统默认（python-docx 默认 Letter）
    for section in doc.sections:
        section.top_margin = Cm(2.5)
        section.bottom_margin = Cm(2.5)
        section.left_margin = Cm(2.5)
        section.right_margin = Cm(2.5)

    # 默认段落字体（应用到 "Normal" 样式）
    normal_style = doc.styles["Normal"]
    normal_style.font.name = FONT_EN
    normal_style.font.size = Pt(11)
    normal_style.font.color.rgb = COLOR_TEXT
    rPr = normal_style.element.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.insert(0, rFonts)
    rFonts.set(qn("w:eastAsia"), FONT_CN)
    rFonts.set(qn("w:ascii"), FONT_EN)
    rFonts.set(qn("w:hAnsi"), FONT_EN)

    # ============ 封面 ============
    # 顶部留白
    for _ in range(3):
        add_paragraph(doc, "", space_after=4)

    # 主标题
    add_paragraph(
        doc, "日慈公益基金会",
        alignment=WD_ALIGN_PARAGRAPH.CENTER,
        size=32, bold=True, color=COLOR_BRAND,
        space_before=20, space_after=4, line_spacing=1.2,
    )
    add_paragraph(
        doc, "战略陪伴阶段总结报告",
        alignment=WD_ALIGN_PARAGRAPH.CENTER,
        size=24, bold=True, color=COLOR_TEXT,
        space_after=14, line_spacing=1.2,
    )

    # 分隔线
    add_paragraph(doc, "", space_after=4)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("━" * 18)
    set_run_font(run, size=10, color=COLOR_BRAND, bold=True)
    add_paragraph(doc, "", space_after=4)

    # 副标题
    add_paragraph(
        doc, "2026 Q1 季度复盘 · 甲方交付版",
        alignment=WD_ALIGN_PARAGRAPH.CENTER,
        size=14, color=COLOR_MUTED, italic=True,
        space_after=40,
    )

    # 元信息表
    meta_rows = [
        ["报告期", "2026 年 1 月 — 4 月（Q1）"],
        ["编制单位", "益语智库"],
        ["报告类型", "战略陪伴季度复盘（甲方交付版）"],
        ["编制日期", "2026-05-12"],
        ["主理人", "顾源源"],
    ]
    add_table(
        doc,
        headers=["", ""],
        rows=meta_rows,
        widths=[4, 9],
        header_color="FFFFFF",
        header_text_color=COLOR_BRAND,
        zebra=True,
    )

    # 页脚备注
    add_paragraph(doc, "", space_after=40)
    add_paragraph(
        doc, "本报告版权归日慈公益基金会与益语智库共同所有；未经双方书面同意不得对外披露",
        alignment=WD_ALIGN_PARAGRAPH.CENTER,
        size=9, color=COLOR_MUTED, italic=True,
    )

    add_page_break(doc)

    # ============ 报告说明 ============
    add_callout(
        doc,
        "本报告基于 2026-01-01 至 2026-04-30 期间日慈基金会与益语智库的全部战略陪伴"
        "交流（含会议纪要、判断沉淀、资料共享、事件线推进）自动生成，由益语智库主理人"
        "审阅。涉及具体数字均带来源引用，结论性判断标注证据强度。"
    )
    add_data_source(
        doc,
        "生成依据：ThreadContextPack（线程记忆）+ confirmedJudgments（确认判断）"
        " + events（事件线）+ memory_facts（事实库）+ tasks（行动项）"
    )

    add_horizontal_rule(doc)
    add_paragraph(doc, "", space_after=8)

    # ============ 一、本期摘要 ============
    add_heading(doc, "一、本期摘要", level=1)
    add_paragraph(
        doc,
        "本季度日慈基金会在「以关系重塑一切」韧性生态战略框架下推进四大核心项目，"
        "关键进展如下。"
    )

    add_heading(doc, "核心判断（本季度沉淀）", level=2)
    judgments = [
        "日慈四大核心项目已确立战略层级划分：第一曲线（心灵魔法学院）+ 第二曲线（心松松、心盛）+ 生态层（繁心计划）。",
        "心松松 - 教师心理关怀计划 被确认为当前战略潜力最高的项目，承担教育实践飞轮与生态协作飞轮的联动枢纽角色。",
        "2026 年全机构核心目标是完成从「单次活动交付」到「关系资产沉淀」的逻辑切换；当前尚处于逻辑验证与基础搭建阶段，不具备规模化扩张条件。",
    ]
    for j in judgments:
        add_bullet(doc, j)

    add_heading(doc, "关键决定（本季度）", level=2)
    decisions = [
        ("[已定]", "心松松项目数字化基于飞书一期搭建，目标 6 月底前完成（对接同济资助结项要求）", COLOR_BRAND),
        ("[已定]", "心盛计划进入业务逻辑对齐阶段，纠偏「活动期」思维", COLOR_BRAND),
        ("[注意]", "心灵魔法学院 2026 节奏调整为「小步迭代」，暂不做规模化扩张", RGBColor(0xC0, 0x39, 0x2B)),
    ]
    for mark, text, mark_color in decisions:
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Cm(0.6)
        p.paragraph_format.line_spacing = 1.5
        p.paragraph_format.space_after = Pt(3)
        bullet_run = p.add_run("• ")
        set_run_font(bullet_run, size=11, color=COLOR_BRAND, bold=True)
        mark_run = p.add_run(f"{mark}  ")
        set_run_font(mark_run, size=10, bold=True, color=mark_color)
        text_run = p.add_run(text)
        set_run_font(text_run, size=11)

    add_heading(doc, "待解决问题", level=2)
    problems = [
        "心松松现金牛产品「学校心理画像 + 行动处方订阅」的包装与定价逻辑（Q2 重点）",
        "心灵魔法学院数据如何向心松松前端供能的具体方案",
        "心盛计划业务产出从「活动记录」到「关系数据」转变的量化标准",
    ]
    for p in problems:
        add_bullet(doc, p)

    add_data_source(
        doc,
        "数据源：confirmedJudgments[1..8] + lastSelectedObject + openQuestions"
    )

    add_page_break(doc)

    # ============ 二、战略目标进展 ============
    add_heading(doc, "二、战略目标进展", level=1)

    add_heading(doc, "2.1 战略核心（不变量）", level=2)
    add_paragraph(doc, "")

    # 战略核心架构 - 用表格替代 ASCII art
    strategy_table = doc.add_table(rows=4, cols=1)
    strategy_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    strategy_table.autofit = False

    strategy_layers = [
        ("使命", "构建普惠关系支持系统，提升孩子与青年心理韧性", "F0F4F9"),
        ("战略核心", "以关系重塑一切（韧性生态战略）", "DCEAF6"),
        ("两大飞轮", "教育实践飞轮（儿童侧） ＋  生态协作飞轮（行业侧）", "C5DDEE"),
        ("联动枢纽", "心松松 - 教师心理关怀计划", "2E75B6"),
    ]

    for i, (label, content, bg) in enumerate(strategy_layers):
        row = strategy_table.rows[i]
        cell = row.cells[0]
        set_cell_bg(cell, bg)
        set_cell_borders(cell, color="FFFFFF", size="8")
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        cell.text = ""
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(6)
        p.paragraph_format.space_after = Pt(6)

        lbl_run = p.add_run(f"【{label}】 ")
        text_color = RGBColor(0xFF, 0xFF, 0xFF) if i == 3 else COLOR_BRAND
        set_run_font(lbl_run, size=11, bold=True, color=text_color)

        text_run = p.add_run(content)
        body_color = RGBColor(0xFF, 0xFF, 0xFF) if i == 3 else COLOR_TEXT
        set_run_font(text_run, size=11, bold=(i == 3), color=body_color)

    add_paragraph(doc, "", space_after=8)
    add_data_source(
        doc,
        "数据源：organization_dna_v2（机构 DNA 表）+ mentionedObjects（项目实体抽取）"
    )

    add_heading(doc, "2.2 四大核心项目进展矩阵", level=2)
    projects = [
        ["心灵魔法学院", "第一曲线（成熟）", "数字化改造 + 存量内容资产标准化", "数字化梳理阶段", "● 平稳", "低"],
        ["心松松 - 教师心理关怀", "第二曲线（攻坚）", "飞书一期数字化（6 月底前）", "基础搭建", "● 关键期", "中"],
        ["心盛计划", "第二曲线（数字化样板）", "业务逻辑对齐 + 关系型架构落地", "业务逻辑对齐", "● 摸索期", "中"],
        ["繁心计划", "生态支撑", "议题行动网络 + 行业执行标准", "网络搭建", "● 推进中", "低"],
    ]
    project_status_colors = [
        RGBColor(0x2E, 0xA0, 0x47),  # 绿
        RGBColor(0xE6, 0x9F, 0x00),  # 黄
        RGBColor(0xE6, 0x9F, 0x00),  # 黄
        RGBColor(0x2E, 0xA0, 0x47),  # 绿
    ]
    table = add_table(
        doc,
        headers=["项目", "战略层级", "2026 核心目标", "当前阶段", "状态", "风险"],
        rows=projects,
        widths=[2.6, 2.3, 3.4, 2.4, 1.6, 1.0],
    )
    # 给状态列的圆点上色
    for i, color in enumerate(project_status_colors):
        cell = table.rows[i + 1].cells[4]
        cell.text = ""
        p = cell.paragraphs[0]
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(2)
        dot_run = p.add_run("● ")
        set_run_font(dot_run, size=11, bold=True, color=color)
        label_run = p.add_run(projects[i][4].split(" ", 1)[1])
        set_run_font(label_run, size=10)
    add_data_source(
        doc,
        "数据源：每个项目对应 event_lines 时间线 + tasks 行动项汇总 + memory_facts.confidence "
        "累计置信度 + 状态由系统按 last_updated_at 与 next_milestone 比对自动给出"
    )

    add_heading(doc, "2.3 关键指标快照", level=2)
    metrics = [
        ["教师带领者池规模", "已跑通完整闭环（报名筛选→实践认证→入池）", "新增 2 轮培训", "2026 年 2-4 月"],
        ["关系资产沉淀方法论", "心盛计划纠偏中", "仍在逻辑验证", "是 2026 全机构指标切换的前置"],
        ["数字化基础设施", "飞书工作流 + 自动资料发放（心灵魔法学院已落地）", "心松松数字化启动", "Q2 完成一期"],
    ]
    add_table(
        doc,
        headers=["指标", "当前状态", "与上季度对比", "备注"],
        rows=metrics,
        widths=[3.5, 4.5, 3.2, 3.5],
    )
    add_data_source(
        doc,
        "数据源：metric_snapshots（待主动能力 A7 实现后才有定量；当前为定性）"
    )

    add_page_break(doc)

    # ============ 三、关键事件回顾 ============
    add_heading(doc, "三、关键事件回顾", level=1)

    add_heading(doc, "3.1 重要事件时间线", level=2)
    events = [
        ["2026-01", "Q1 战略框架确认会议", "四大项目战略层级划分确立"],
        ["2026-02", "心松松第一轮教师带领者培训", "首次跑通「报名筛选 → 实践认证 → 入池」闭环"],
        ["2026-03", "心盛计划业务逻辑对齐会议", "决定：纠偏「活动期」思维、重构关系型架构"],
        ["2026-04", "心松松第二轮带领者培训", "一线验证：教师情绪支持价值得到确认"],
        ["2026-05", "项目组合战略潜力评估", "心松松判定为战略潜力最高项目；现金牛产品立项"],
        ["2026-06（计划）", "心松松飞书一期数字化完成", "同济资助 Q2 结项节点"],
    ]
    add_table(
        doc,
        headers=["时间", "事件", "关键产出 / 决策"],
        rows=events,
        widths=[2.4, 4.2, 7.4],
    )
    add_data_source(
        doc,
        "数据源：event_lines（事件线主表）+ event_line_entries（每条事件记录）"
    )

    add_heading(doc, "3.2 重要决策事项", level=2)
    decisions_table = [
        ["心灵魔法学院 2026 节奏调整为「小步迭代」、暂不扩张", "2026-Q1", "日慈方主理人", "第一曲线整体", "执行中"],
        ["心松松项目数字化优先级提升至机构第一", "2026-Q1", "战略陪伴双方共识", "第二曲线攻坚", "推进中"],
        ["心盛计划纠偏「活动期」思维", "2026-03", "心盛项目组", "心盛计划方向", "重构中"],
        ["「学校心理画像 + 行动处方订阅」立项", "2026-04", "战略陪伴双方共识", "心松松载体", "概念阶段"],
    ]
    add_table(
        doc,
        headers=["决策", "时间", "决策人", "影响范围", "执行状态"],
        rows=decisions_table,
        widths=[5.0, 1.7, 2.6, 2.4, 2.3],
    )
    add_data_source(
        doc,
        "数据源：judgments 表（official_judgment 类型）+ proposal_records（决策类记录，status=approved）"
    )

    add_heading(doc, "3.3 风险与卡点", level=2)
    risks = [
        ["心松松训练模块库尚未迭代完成", "中", "心松松", "Q2 内完成"],
        ["教师互助小程序未落地", "中", "心松松", "Q2 内完成"],
        ["心盛计划全链路业务设计未打磨完", "中", "心盛", "持续打磨"],
        ["现金牛产品定价逻辑空白", "高", "心松松", "Q2 重点"],
        ["心灵魔法学院数据向心松松前端供能的方案未定", "高", "跨项目", "Q2-Q3"],
    ]
    risk_severity_colors = [
        RGBColor(0xE6, 0x9F, 0x00),  # 中
        RGBColor(0xE6, 0x9F, 0x00),  # 中
        RGBColor(0xE6, 0x9F, 0x00),  # 中
        RGBColor(0xC0, 0x39, 0x2B),  # 高
        RGBColor(0xC0, 0x39, 0x2B),  # 高
    ]
    risk_table = add_table(
        doc,
        headers=["风险 / 卡点", "严重度", "关联项目", "进展"],
        rows=risks,
        widths=[6.5, 1.6, 2.4, 3.5],
    )
    # 给严重度列上色
    for i, color in enumerate(risk_severity_colors):
        cell = risk_table.rows[i + 1].cells[1]
        cell.text = ""
        p = cell.paragraphs[0]
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(2)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        dot_run = p.add_run("● ")
        set_run_font(dot_run, size=11, bold=True, color=color)
        label_run = p.add_run(risks[i][1])
        set_run_font(label_run, size=10, bold=True, color=color)
    add_data_source(
        doc,
        "数据源：meeting_followup.risks + tasks 中 risk 类型 + data_center_quality.gap_detection"
    )

    add_page_break(doc)

    # ============ 四、战略洞察与判断 ============
    add_heading(doc, "四、战略洞察与判断（益语方）", level=1)
    add_data_source(
        doc,
        "本部分由 ThreadContextPack 的 confirmedJudgments + 益语主理人审阅润色生成"
    )

    add_heading(doc, "4.1 当前阶段定位", level=2)
    add_paragraph(
        doc,
        "日慈正处于「战略转型期」的关键时刻 —— 从过去依赖单次活动交付的传统公益模式，"
        "向关系资产沉淀的可持续模式切换。这是一个逻辑验证大于规模扩张的阶段，"
        "企图过早扩张会破坏关系资产的形成机制。"
    )

    add_paragraph(doc, "关键不变量：", bold=True, color=COLOR_BRAND, space_before=8)
    invariants = [
        "战略核心「以关系重塑一切」不动",
        "双飞轮模型（教育实践 + 生态协作）不动",
        "心松松作为双飞轮联动枢纽的角色不动",
    ]
    for x in invariants:
        add_bullet(doc, x)

    add_paragraph(doc, "关键变量：", bold=True, color=COLOR_BRAND, space_before=8)
    variables = [
        "现金牛产品的定价与包装路径仍在探索",
        "数字化基础设施（飞书一期）的落地节奏",
        "心灵魔法学院数据向心松松供能的具体方案",
    ]
    for x in variables:
        add_bullet(doc, x)

    add_heading(doc, "4.2 核心判断：心松松为何是战略潜力最高项目", level=2)
    xss_judgment = [
        ["飞轮枢纽", "唯一同时联动两个飞轮的项目；前端承接儿童心理画像数据，后端培养教师带领者推动学校接入"],
        ["变现确定性", "唯一同时满足「付费意愿确定 + 核心资产变现 + 驱动飞轮」三大筛选条件"],
        ["杠杆效应", "「1 个优秀教师 → 整个班级心育环境改善」的扩张机制；ROI 远高于直接触达儿童的项目"],
    ]
    add_table(
        doc,
        headers=["维度", "心松松独特价值"],
        rows=xss_judgment,
        widths=[3.0, 11.0],
    )

    add_paragraph(doc, "判断置信度：★★★★★（高）",
                  bold=True, color=COLOR_BRAND, space_before=4)
    add_paragraph(
        doc,
        "基于完整闭环跑通 + 用户接受度一线验证 + 多轮战略陪伴讨论共识。",
        italic=True, size=10, color=COLOR_MUTED,
    )
    add_data_source(
        doc,
        "数据源：evidence_quality_annotations + confirmedJudgments[8] + lastSelectedObject "
        "+ 关联 event_lines 中的两轮培训记录"
    )

    add_heading(doc, "4.3 待澄清的开放问题", level=2)
    open_questions = [
        "心松松订阅产品的单校年费定价区间尚无锚点参考",
        "心松松带领者留存激励机制未设计",
        "心灵魔法学院 → 心松松 的数据接口与权限边界未定",
        "心盛计划「关系数据 vs 活动数据」的量化区分标准模糊",
        "繁心计划的生态伙伴认证标准尚未拟定",
    ]
    for q in open_questions:
        add_bullet(doc, q)
    add_data_source(
        doc,
        "数据源：openQuestions（线程记忆中的开放问题）+ missingContext（每次回答的缺口提示）"
    )

    add_page_break(doc)

    # ============ 五、核心议题深度分析 ============
    add_heading(doc, "五、核心议题深度分析", level=1)

    # 议题 1
    add_heading(doc, "议题 1：心松松数字化 vs 心盛计划数字化 — 谁该先做？", level=2)
    add_paragraph(doc, "议题背景：", bold=True, color=COLOR_BRAND, space_before=4)
    add_paragraph(doc, "两个项目都需要数字化投入。资源有限，需要排序。")

    add_paragraph(doc, "益语方分析：", bold=True, color=COLOR_BRAND, space_before=6)
    add_bullet(doc, "心松松数字化：硬节点（同济资助 6 月结项）+ 现金牛产品载体 + 已跑通带领者闭环 → 优先级 1")
    add_bullet(doc, "心盛计划数字化：自身就是数字化样板项目，但当前还在业务逻辑对齐阶段；先逻辑、后数字化 → 优先级 2")

    add_paragraph(doc, "建议结论：", bold=True, color=COLOR_BRAND, space_before=6)
    add_callout(
        doc,
        "Q2 重点资源向心松松倾斜，心盛在 Q2 完成业务逻辑收敛，Q3 才进入数字化重点投入。"
    )
    add_data_source(
        doc,
        "数据源：本议题为 synthesis 类回答，由 workspace_query_router.workflow=synthesis 路径生成；"
        "引用 events + tasks + judgments + DNA"
    )

    # 议题 2
    add_heading(doc, "议题 2：关系资产沉淀的量化标准是什么？", level=2)
    add_paragraph(doc, "议题背景：", bold=True, color=COLOR_BRAND, space_before=4)
    add_paragraph(
        doc,
        "全机构 2026 年要从「活动记录」切换到「关系资产沉淀」，但什么算「关系资产」，"
        "沉淀到什么程度算达标，目前模糊。"
    )

    add_paragraph(doc, "益语方初步建议（待 Q2 进一步讨论）：",
                  bold=True, color=COLOR_BRAND, space_before=6)
    add_bullet(doc, "量化口径 A（教师侧）：累计活跃带领者人数 + 月度带领次数 + 带领者持续参与时长")
    add_bullet(doc, "量化口径 B（儿童侧）：校均心育空间使用频次 + 班级心理文化包激活率 + 儿童心理画像数据条目数")
    add_bullet(doc, "量化口径 C（机构侧）：跨项目数据复用次数 + 沉淀方法论文档数 + 标准化资产模块数")

    add_paragraph(doc, "建议：", bold=True, color=COLOR_BRAND, space_before=6)
    add_callout(
        doc,
        "Q2 召开专题会议，三个口径各提一个 KPI 列入半年度考核试运行。"
    )
    add_data_source(
        doc,
        "数据源：themes（话题）+ topic_candidates 待提议建议 + 多轮 chat 综合分析"
    )

    # 议题 3
    add_heading(doc, "议题 3：现金牛产品「学校心理画像 + 行动处方订阅」落地节奏", level=2)
    add_paragraph(doc, "议题背景：", bold=True, color=COLOR_BRAND, space_before=4)
    add_paragraph(
        doc,
        "这是心松松的变现核心载体，但目前仍是概念阶段，无定价无包装。"
    )

    add_paragraph(doc, "益语方建议节奏：", bold=True, color=COLOR_BRAND, space_before=6)
    add_bullet(doc, "2026 Q2：完成产品 MVP 定义（「心理画像」覆盖哪些维度？「行动处方」包含哪些模块？）")
    add_bullet(doc, "2026 Q3：选 3-5 个意向学校做 PoC（不收费），验证产品价值与付费意愿")
    add_bullet(doc, "2026 Q4：完成定价模型 + 商业化包装，2027 启动小范围试售")

    add_paragraph(doc, "关键卡点：", bold=True, color=RGBColor(0xC0, 0x39, 0x2B), space_before=6)
    add_callout(
        doc,
        "心灵魔法学院的儿童数据如何脱敏后给心松松「画像」用 —— 这是产品成立的基础。"
    )
    add_data_source(
        doc,
        "数据源：projects + dependencies graph（来自 entities + relationship_triples，"
        "等理解深度 迭代 5 完成才有结构化关系）"
    )

    add_page_break(doc)

    # ============ 六、行动建议与下阶段计划 ============
    add_heading(doc, "六、行动建议与下阶段计划", level=1)

    add_heading(doc, "6.1 短期（5 月 — 6 月）", level=2)
    short_term = [
        ["P0", "心松松飞书一期数字化完成", "日慈 + 飞书", "6 / 30"],
        ["P0", "心松松训练模块库完成第一版", "日慈心松松组", "6 / 30"],
        ["P1", "教师互助小程序上线", "日慈数字化组", "6 / 30"],
        ["P1", "心盛计划业务逻辑对齐收敛", "日慈心盛组", "5 / 31"],
        ["P1", "召开「关系资产量化标准」专题会议", "双方", "5 月内"],
        ["P2", "心松松现金牛产品 MVP 概念草案", "益语提初稿 + 日慈确认", "6 / 15"],
    ]
    add_table(
        doc,
        headers=["优先级", "行动项", "负责方", "截止"],
        rows=short_term,
        widths=[1.6, 6.5, 4.0, 1.9],
    )

    add_heading(doc, "6.2 中期（Q3）", level=2)
    midterm = [
        "心松松开始训练模块的产品化封装",
        "心松松现金牛产品 PoC（3-5 个意向学校）",
        "心灵魔法学院数字化形态探索 + 数据接口设计",
        "心盛计划进入数字化实施",
    ]
    for x in midterm:
        add_bullet(doc, x)

    add_heading(doc, "6.3 长期（H2）", level=2)
    longterm = [
        "现金牛产品定价模型 + 商业化包装完成",
        "繁心计划行业执行标准发布",
        "双飞轮联动数据回路跑通",
    ]
    for x in longterm:
        add_bullet(doc, x)

    add_data_source(
        doc,
        "数据源：本节由 action_suggestion_service + LLM synthesis 生成；"
        "每个 action item 由现有 task 关联或新建"
    )

    add_page_break(doc)

    # ============ 七、附录 ============
    add_heading(doc, "七、附录", level=1)

    add_heading(doc, "7.1 本期资料来源清单", level=2)
    sources = [
        ["战略陪伴会议纪要", "6 份", "2026 Q1"],
        ["益语方判断沉淀", "8 条核心判断", "累计"],
        ["项目 DNA 文档", "4 份（每项目 1 份）", "持续更新"],
        ["任务行动项", "14 条（未结案）", "截至本报告期末"],
        ["外部资料引用", "同济资助文件 + 飞书工作流文档", "—"],
    ]
    add_table(
        doc,
        headers=["类型", "数量", "范围"],
        rows=sources,
        widths=[4.5, 4.5, 5.0],
    )
    add_data_source(
        doc,
        "数据源：document_card（文档卡片汇总）+ filter by 报告期 + sourceType"
    )

    add_heading(doc, "7.2 关键人员", level=2)
    add_paragraph(
        doc,
        "（占位 —— 待理解深度迭代 2 实体抽取上线后自动填充。当前阶段为占位）",
        italic=True, color=COLOR_MUTED, size=10,
    )
    persons = [
        ["日慈方主理人", "（占位）", "全局"],
        ["心松松项目负责人", "（占位）", "心松松"],
        ["心盛项目负责人", "（占位）", "心盛"],
        ["益语战略陪伴主理人", "顾源源", "全局"],
    ]
    add_table(
        doc,
        headers=["角色", "姓名", "所属项目"],
        rows=persons,
        widths=[5.0, 4.0, 5.0],
    )
    add_data_source(
        doc,
        "数据源：entities WHERE type='person' AND client_id='日慈'"
    )

    add_heading(doc, "7.3 报告生成机制说明", level=2)
    add_paragraph(
        doc,
        "本报告由益语智库「报告自动生成模块」基于客户工作台积累的资料、判断、"
        "事件线、任务自动生成初稿，再由益语主理人审阅润色。"
    )
    add_paragraph(doc, "信任级别：", bold=True, color=COLOR_BRAND, space_before=4)
    add_paragraph(
        doc,
        "文中带 📊 引用标记的内容为结构化数据自动拼接，可追溯；其余文字为 LLM 综合推断或"
        "主理人补充，已经过人工审阅。"
    )

    add_paragraph(doc, "", space_before=8)
    add_paragraph(doc, "版本：v1.0 自动生成 + 益语主理人 1 轮润色",
                  size=10, color=COLOR_MUTED, italic=True)
    add_paragraph(doc, "下次自动生成：2026-08-12（Q2 季度报告）",
                  size=10, color=COLOR_MUTED, italic=True)

    # 底部版权
    add_horizontal_rule(doc)
    add_paragraph(doc, "", space_after=8)
    add_paragraph(
        doc,
        "© 2026 日慈公益基金会 ｜ 益语智库   版权所有",
        alignment=WD_ALIGN_PARAGRAPH.CENTER,
        size=9, color=COLOR_MUTED, italic=True,
    )

    return doc


def main():
    doc = build()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUTPUT_PATH)
    print(f"✅ 已生成：{OUTPUT_PATH}")
    print(f"   文件大小：{OUTPUT_PATH.stat().st_size} bytes")


if __name__ == "__main__":
    main()
