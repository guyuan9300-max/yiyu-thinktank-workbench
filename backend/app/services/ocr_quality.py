"""OCR 质量自动评估器（R13 Phase 1）

输入 v2_documents 的 markdown_content + 原 PDF 信息，输出 QualityReport：
- 每页质量（字符密度/页面类型/可信度）
- 文档级质量（基线字符/章节连续性/总评分）
- 可疑页清单 + 推荐补救 action

设计为「纯函数」无副作用，不依赖 db/ai 服务，可在任何时机被调用：
- decompose 前自动跑（检测应不应该重 OCR）
- 用户上传后自动跑（告知质量分）
- 单元测试可直接跑
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal


# ===== 数据结构 =============================================================

PageType = Literal[
    "text",  # 纯文字页
    "cover",  # 合同封面/扉页（含「合同书」「协议书」等标题 + 简短信息）
    "appendix",  # 附录/补充说明/调整说明等附加页（内容少但完整）
    "image_with_text",  # 含文字图（架构图/截图等）
    "diagram",  # 架构图/流程图（无明显文字标签）
    "decorative",  # 装饰页（分隔页）
    "mixed",  # 文字+图混合
    "low_density",  # 字符密度异常低
    "empty",  # 完全空白
    "fallback",  # 仅含 OCR fallback 文本
    "signature",  # 签字盖章页（通常字符少+含「签字」「盖章」「年月日」）
    "unknown",
]


# 附录/补充页常见标题
APPENDIX_MARKERS = (
    "薪资调整说明",
    "薪酬调整",
    "工资调整",
    "调整说明",
    "补充说明",
    "补充协议",
    "附件",
    "附录",
    "附则",
    "签收单",
    "确认函",
)


# 合同封面常见标题
COVER_PAGE_MARKERS = (
    "劳动合同书",
    "劳动合同",
    "合同书",
    "协议书",
    "合作协议",
    "服务协议",
    "聘用合同",
    "捐赠协议",
)

# 签字页特征
SIGNATURE_MARKERS = (
    "签字",
    "盖章",
    "甲方（盖章）",
    "乙方（签字）",
    "签订日期",
    "签订地点",
    "签章",
    "(盖章)",
    "（盖章）",
)


@dataclass(frozen=True)
class PageQuality:
    page_number: int
    char_count: int
    density_ratio: float  # 实际字符 / 期望字符
    page_type: PageType
    suspected_issues: tuple[str, ...]  # 问题列表
    confidence: float  # 0-1 该页 OCR 可信度
    needs_retry: bool
    recommended_action: str  # 「重 OCR」「双 prompt」「人工核对」「无需处理」


@dataclass(frozen=True)
class QualityReport:
    document_id: str
    document_kind: str
    total_pdf_pages: int
    parsed_pages: int  # markdown 切分出的页数
    total_chars: int
    baseline_chars: int  # 按 kind 估算
    pages: tuple[PageQuality, ...]
    chapter_continuity_ok: bool
    chapter_gaps: tuple[str, ...]
    document_score: float  # 0-1 综合分
    overall_issues: tuple[str, ...]
    recommended_actions: tuple[str, ...]  # 文档级 action 清单
    suspicious_page_numbers: tuple[int, ...]  # 可疑页列表


# ===== 配置 ================================================================

# 按文档类型估算基线字符数（A4 文字页约 600-1200 字）
BASELINE_CHARS_BY_KIND: dict[str, int] = {
    "employee_contract": 2800,  # 劳动合同通常 3-4 页文字
    "meeting_minute": 1500,
    "project_proposal": 3000,
    "financial_report": 2000,
    "service_agreement": 2500,
    "donation_agreement": 2000,
    "other": 1000,
    "unknown": 1000,
}

# 单页期望字符（文字页）
PAGE_EXPECTED_CHARS = 600  # 保守估计，A4 文字页 ≥600 字
PAGE_LOW_DENSITY_THRESHOLD = 0.3  # 实际 < 30% 期望→ low_density
PAGE_TOO_FEW_CHARS = 50  # 单页 < 50 字→ 疑似图/空

# fallback 文本模式（OCR 服务返回的兜底字串）
FALLBACK_PATTERNS = (
    "[原文印刷模糊]",
    "[无法识别]",
    "[图片内容]",
    "[空白页]",
    "无可识别内容",
    "[此处内容缺失]",
    "未能解析",
    "无法识别",
)

# 章节标题模式（中文合同/文档常用）
CHAPTER_PATTERNS = [
    re.compile(r"第\s*([一二三四五六七八九十百零0-9]+)\s*条"),
    re.compile(r"第\s*([一二三四五六七八九十百零0-9]+)\s*章"),
    re.compile(r"第\s*([一二三四五六七八九十百零0-9]+)\s*节"),
    re.compile(r"^([一二三四五六七八九十]+)、", re.MULTILINE),
    re.compile(r"^(\d+)\.\s+[一-龥]", re.MULTILINE),  # "1. 中文"
]

# 中文数字 → 阿拉伯
_CN_NUM = {
    "零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
}


def _cn_to_int(s: str) -> int | None:
    s = s.strip()
    if s.isdigit():
        return int(s)
    if s in _CN_NUM:
        return _CN_NUM[s]
    # 简单处理「十一」「二十」「二十三」
    if "十" in s:
        parts = s.split("十")
        left = parts[0] or "一"
        right = parts[1] if len(parts) > 1 else "0"
        a = _CN_NUM.get(left)
        b = _CN_NUM.get(right) if right else 0
        if a is not None and b is not None:
            return a * 10 + b
    return None


# ===== 工具函数 =============================================================

def split_markdown_by_pages(markdown: str) -> dict[int, str]:
    """按 `## 第 N 页` 切分 markdown。"""
    if not markdown:
        return {}
    pages: dict[int, str] = {}
    # 匹配 「## 第 N 页」或 「## 第N页」
    pattern = re.compile(r"^##\s*第\s*(\d+)\s*页\s*$", re.MULTILINE)
    matches = list(pattern.finditer(markdown))
    if not matches:
        # 没有页标记 → 整篇当一页
        return {1: markdown.strip()}
    for i, m in enumerate(matches):
        page_num = int(m.group(1))
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown)
        pages[page_num] = markdown[start:end].strip()
    return pages


def count_meaningful_chars(text: str) -> int:
    """统计有意义字符（中文+英文+数字），排除空白/标点。"""
    if not text:
        return 0
    return sum(1 for ch in text if (
        "一" <= ch <= "鿿" or  # 中文
        ch.isalnum()
    ))


# ===== 单页校验 =============================================================

def detect_page_type(page_md: str, char_count: int, page_number: int = 0) -> PageType:
    """根据内容启发式判断页面类型。"""
    if not page_md or not page_md.strip():
        return "empty"

    # 优先级 1：fallback 文本
    if char_count < PAGE_TOO_FEW_CHARS and any(p in page_md for p in FALLBACK_PATTERNS):
        return "fallback"

    # 优先级 2：合同封面（通常是第 1 页，含「合同书」类标题，字数本来就少）
    has_cover_marker = any(m in page_md for m in COVER_PAGE_MARKERS)
    if page_number <= 1 and char_count < 200 and has_cover_marker:
        return "cover"

    # 优先级 3：附录/补充说明页（合同后附的薪资调整/补充协议等，内容少但完整）
    has_appendix_marker = any(m in page_md for m in APPENDIX_MARKERS)
    if has_appendix_marker and char_count >= 50:
        return "appendix"

    # 优先级 4：签字页（含「签字」「盖章」+「年月日」，字数少属正常）
    sig_count = sum(1 for m in SIGNATURE_MARKERS if m in page_md)
    has_date = bool(re.search(r"\d{4}\s*年", page_md))
    if char_count < 300 and (sig_count >= 2 or (sig_count >= 1 and has_date)):
        return "signature"

    if char_count < PAGE_TOO_FEW_CHARS:
        # 字符太少且不是封面/签字页/fallback → 看是否纯图
        if re.search(r"[图表流程架构组织结构]", page_md):
            return "diagram"
        return "empty"

    if char_count < int(PAGE_EXPECTED_CHARS * PAGE_LOW_DENSITY_THRESHOLD):
        return "low_density"

    # 检测是否含图描述（mermaid、表格、特殊符号占比高）
    image_markers = page_md.count("图：") + page_md.count("[图") + page_md.count("流程图")
    if image_markers >= 2:
        return "image_with_text"

    return "text"


def assess_page(page_number: int, page_md: str) -> PageQuality:
    char_count = count_meaningful_chars(page_md)
    density_ratio = char_count / PAGE_EXPECTED_CHARS if PAGE_EXPECTED_CHARS else 0.0
    page_type = detect_page_type(page_md, char_count, page_number)
    issues: list[str] = []
    recommended_action = "无需处理"
    needs_retry = False
    confidence = 1.0

    if page_type == "cover":
        # 合同封面：字数本来就少，正常
        recommended_action = "无需处理（封面页）"
        confidence = 1.0
    elif page_type == "appendix":
        # 附录/补充说明：内容少但完整
        recommended_action = "无需处理（附录补充页）"
        confidence = 1.0
    elif page_type == "signature":
        # 签字页：字数本来就少，正常
        recommended_action = "无需处理（签字盖章页）"
        confidence = 1.0
    elif page_type == "empty":
        issues.append(f"第{page_number}页 完全空白或仅含格式符")
        recommended_action = "重 OCR（高 DPI）"
        needs_retry = True
        confidence = 0.0
    elif page_type == "fallback":
        issues.append(f"第{page_number}页 仅含 OCR fallback 文本")
        recommended_action = "重 OCR（双 prompt 模式）"
        needs_retry = True
        confidence = 0.1
    elif page_type == "low_density":
        issues.append(
            f"第{page_number}页 字符密度仅 {density_ratio*100:.0f}% "
            f"({char_count} 字 / 期望 {PAGE_EXPECTED_CHARS})"
        )
        recommended_action = "重 OCR（高 DPI + 提示穷尽扫描）"
        needs_retry = True
        confidence = 0.4
    elif page_type == "diagram":
        issues.append(f"第{page_number}页 疑似纯图（架构图/流程图）")
        recommended_action = "切到「图描述+文字提取」双 prompt"
        needs_retry = True
        confidence = 0.5
    elif page_type == "image_with_text":
        issues.append(f"第{page_number}页 含图+文字混合")
        recommended_action = "已部分提取，可选「图描述」补强"
        needs_retry = False
        confidence = 0.7
    else:
        # text 页 - 检查 fallback 模式
        fb_count = sum(page_md.count(p) for p in FALLBACK_PATTERNS)
        if fb_count > 0:
            issues.append(f"第{page_number}页 含 {fb_count} 处 OCR 模糊标记")
            confidence = max(0.4, confidence - 0.2 * fb_count)
            recommended_action = "高 DPI 重 OCR 改善"
            needs_retry = fb_count >= 2

    return PageQuality(
        page_number=page_number,
        char_count=char_count,
        density_ratio=density_ratio,
        page_type=page_type,
        suspected_issues=tuple(issues),
        confidence=confidence,
        needs_retry=needs_retry,
        recommended_action=recommended_action,
    )


# ===== 文档级校验 ===========================================================

def check_chapter_continuity(markdown: str) -> tuple[bool, list[str]]:
    """检测章节编号连续性。返回 (ok, gaps)。"""
    if not markdown:
        return True, []

    # 用最常出现的 pattern 作为主章节
    pattern_matches: list[tuple[re.Pattern, list[int]]] = []
    for pattern in CHAPTER_PATTERNS:
        nums = []
        for m in pattern.finditer(markdown):
            n = _cn_to_int(m.group(1))
            if n is not None:
                nums.append(n)
        if len(nums) >= 3:  # 至少 3 个连续章节才算「有章节结构」
            pattern_matches.append((pattern, nums))

    if not pattern_matches:
        return True, []  # 没有可识别章节，不报问题

    # 取出现最多的 pattern
    pattern, nums = max(pattern_matches, key=lambda x: len(x[1]))
    nums_set = set(nums)
    if not nums:
        return True, []

    gaps: list[str] = []
    min_n, max_n = min(nums), max(nums)
    for i in range(min_n, max_n + 1):
        if i not in nums_set:
            gaps.append(f"第 {i} 条/章/节 缺失")

    return len(gaps) == 0, gaps


def estimate_baseline_chars(kind: str, pdf_pages: int) -> int:
    """计算基线字符数：取 kind-baseline 与「页数 × 单页期望」的较大值。

    PDF 页数已知时，按页数动态算（每页期望 500 字 × 70% = 350 字/页 是「过得去」的下限）。
    """
    kind_baseline = BASELINE_CHARS_BY_KIND.get(kind, BASELINE_CHARS_BY_KIND["unknown"])
    if pdf_pages > 0:
        # 每页期望 350-500 字（保守的 OCR 下限）
        page_baseline = pdf_pages * 350
        return max(kind_baseline, page_baseline)
    return kind_baseline


def check_total_chars_baseline(total_chars: int, kind: str, pdf_pages: int = 0) -> tuple[bool, str]:
    baseline = estimate_baseline_chars(kind, pdf_pages)
    if total_chars < baseline * 0.5:
        return False, (
            f"总字符 {total_chars} 远低于基线 {baseline} "
            f"（仅 {total_chars*100//baseline}%），强烈疑似 OCR 不全"
        )
    if total_chars < baseline * 0.8:
        return False, (
            f"总字符 {total_chars} 低于基线 {baseline} "
            f"（{total_chars*100//baseline}%），可能 OCR 有缺失"
        )
    return True, ""


def check_pdf_vs_parsed_pages(pdf_pages: int, parsed_pages: int) -> tuple[bool, str]:
    if pdf_pages <= 0:
        return True, ""
    if parsed_pages < pdf_pages:
        return False, (
            f"PDF 共 {pdf_pages} 页，markdown 仅切分出 {parsed_pages} 页内容"
            f"（缺 {pdf_pages - parsed_pages} 页）"
        )
    return True, ""


# ===== 主入口 ==============================================================

def assess_document_quality(
    document_id: str,
    markdown_content: str,
    total_pdf_pages: int,
    document_kind: str = "unknown",
) -> QualityReport:
    """跑全部校验，输出 QualityReport。"""
    pages_md = split_markdown_by_pages(markdown_content)
    page_qualities: list[PageQuality] = []
    for page_num, page_text in sorted(pages_md.items()):
        page_qualities.append(assess_page(page_num, page_text))

    total_chars = count_meaningful_chars(markdown_content)
    baseline = estimate_baseline_chars(document_kind, total_pdf_pages)

    overall_issues: list[str] = []
    actions: list[str] = []

    # 校验 1: PDF 页数 vs 解析页数
    pages_ok, pages_msg = check_pdf_vs_parsed_pages(total_pdf_pages, len(pages_md))
    if not pages_ok:
        overall_issues.append(pages_msg)
        actions.append("对未解析页跑 OCR retry")

    # 校验 2: 总字符基线（动态：取 kind-baseline 与「页数×350」较大值）
    chars_ok, chars_msg = check_total_chars_baseline(total_chars, document_kind, total_pdf_pages)
    if not chars_ok:
        overall_issues.append(chars_msg)
        actions.append("对低字符页跑高 DPI 重 OCR")

    # 校验 3: 章节连续性
    chapter_ok, chapter_gaps = check_chapter_continuity(markdown_content)
    if not chapter_ok:
        overall_issues.append(
            f"章节连续性中断：{', '.join(chapter_gaps[:5])}"
            f"{'…' if len(chapter_gaps) > 5 else ''}"
        )
        actions.append("定位缺失章节所在页并重 OCR")

    # 收集可疑页
    suspicious = tuple(p.page_number for p in page_qualities if p.needs_retry)
    if suspicious:
        actions.append(f"对第 {','.join(str(n) for n in suspicious)} 页单独重 OCR")

    # 综合评分：每页平均 confidence × 文档级因子
    page_avg = (
        sum(p.confidence for p in page_qualities) / len(page_qualities)
        if page_qualities else 0.0
    )
    doc_factor = 1.0
    if not pages_ok:
        doc_factor *= 0.6
    if not chars_ok:
        doc_factor *= 0.7
    if not chapter_ok:
        doc_factor *= 0.8
    document_score = page_avg * doc_factor

    return QualityReport(
        document_id=document_id,
        document_kind=document_kind,
        total_pdf_pages=total_pdf_pages,
        parsed_pages=len(pages_md),
        total_chars=total_chars,
        baseline_chars=baseline,
        pages=tuple(page_qualities),
        chapter_continuity_ok=chapter_ok,
        chapter_gaps=tuple(chapter_gaps),
        document_score=document_score,
        overall_issues=tuple(overall_issues),
        recommended_actions=tuple(actions),
        suspicious_page_numbers=suspicious,
    )


# ===== 报告格式化（人类可读）===============================================

def format_report(report: QualityReport) -> str:
    """生成可读报告（用于日志/调试/UI）。"""
    score_pct = report.document_score * 100
    quality_emoji = "✅" if score_pct >= 90 else "⚠️" if score_pct >= 70 else "❌"

    lines = [
        f"{quality_emoji} OCR 质量评估：{report.document_id}",
        f"  文档类型：{report.document_kind}",
        f"  PDF 页数：{report.total_pdf_pages} / 解析页数：{report.parsed_pages}",
        f"  总字符：{report.total_chars} / 基线：{report.baseline_chars}",
        f"  综合评分：{score_pct:.0f}%",
        "",
    ]

    if report.overall_issues:
        lines.append("⚠️ 文档级问题：")
        for issue in report.overall_issues:
            lines.append(f"  - {issue}")
        lines.append("")

    if report.suspicious_page_numbers:
        lines.append(f"🔍 可疑页：第 {','.join(str(n) for n in report.suspicious_page_numbers)} 页")
        for p in report.pages:
            if p.needs_retry:
                lines.append(
                    f"  • 第{p.page_number}页 [{p.page_type}] "
                    f"{p.char_count} 字 (密度 {p.density_ratio*100:.0f}%) "
                    f"→ {p.recommended_action}"
                )
        lines.append("")

    if report.recommended_actions:
        lines.append("📋 建议 action：")
        for action in report.recommended_actions:
            lines.append(f"  → {action}")

    return "\n".join(lines)
