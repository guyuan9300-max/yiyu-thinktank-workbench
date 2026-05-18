"""文本归一化 — atomic_facts 抽取 + 矛盾检测 + 字典匹配的基础设施.

解决 Codex 实测发现的 OCR 噪声问题:
- ^A 等控制字符 (来自 docx/pdf 解析)
- 繁简标点不一致 (引号 / 括号 / 句号)
- 多余空白 (制表符 / 全角空格 / 不可见字符)
- 中英文标点混用

设计原则:
- normalize_text(s) 是幂等的: f(f(s)) == f(s)
- 不改变语义, 只是清洗 + 归一标点
- 保留中文、英文字母、数字、必要标点
"""
from __future__ import annotations

import re
import unicodedata
from typing import Final

# 控制字符 (除了 \t \n) 全部清掉
_CONTROL_CHARS_RE: Final[re.Pattern[str]] = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]"
)

# 引号统一: 中英文各种引号 → 直引号
_QUOTE_TRANSLATE: Final[dict[int, str]] = {
    ord("“"): '"',  # "
    ord("”"): '"',  # "
    ord("‘"): "'",  # '
    ord("’"): "'",  # '
    ord("「"): '"',  # 「
    ord("」"): '"',  # 」
    ord("『"): '"',  # 『
    ord("』"): '"',  # 』
    ord("—"): "-",  # —
    ord("–"): "-",  # –
    ord("ー"): "-",  # ー
}

# 中文标点 → 英文标点 (用于比较时归一)
_CN_PUNCT_TRANSLATE: Final[dict[int, str]] = {
    ord("，"): ",",
    ord("。"): ".",
    ord("；"): ";",
    ord("："): ":",
    ord("！"): "!",
    ord("？"): "?",
    ord("（"): "(",
    ord("）"): ")",
    ord("【"): "[",
    ord("】"): "]",
    ord("《"): "<",
    ord("》"): ">",
    ord("　"): " ",  # 全角空格
    ord(" "): " ",  # nbsp
    ord("﻿"): "",  # BOM
}

# 繁简同义 (常见基金会词)
_TRAD_SIMP_TRANSLATE: Final[dict[int, str]] = {
    ord("廣"): "广",
    ord("區"): "区",
    ord("國"): "国",
    ord("學"): "学",
    ord("業"): "业",
    ord("務"): "务",
    ord("經"): "经",
    ord("營"): "营",
    ord("會"): "会",
    ord("專"): "专",
    ord("項"): "项",
    ord("關"): "关",
    ord("係"): "系",
    ord("時"): "时",
    ord("間"): "间",
    ord("動"): "动",
    ord("組"): "组",
    ord("織"): "织",
    ord("習"): "习",
    ord("貝"): "贝",
}

# 多余空白 (连续空白 → 单空格)
_MULTI_SPACE_RE: Final[re.Pattern[str]] = re.compile(r"[ \t]+")
# 连续换行 → 单换行 (最多)
_MULTI_NEWLINE_RE: Final[re.Pattern[str]] = re.compile(r"\n{2,}")


def clean_control_chars(s: str) -> str:
    """清掉所有控制字符 (^A ^B ... \x7f), 但保留 \t \n."""
    if not s:
        return ""
    return _CONTROL_CHARS_RE.sub("", s)


def normalize_quotes(s: str) -> str:
    """中英文各种引号 / 破折号 → 统一直引号 + 短横."""
    return s.translate(_QUOTE_TRANSLATE)


def normalize_punctuation(s: str) -> str:
    """中文标点 → 英文标点 (用于比较场景)."""
    return s.translate(_CN_PUNCT_TRANSLATE)


def simplify_traditional(s: str) -> str:
    """常见繁体字 → 简体 (浅层映射, 不替代专业 OpenCC)."""
    return s.translate(_TRAD_SIMP_TRANSLATE)


def normalize_text(s: str | None) -> str:
    """完整归一化: 清控制字符 + Unicode NFKC + 引号 + 多余空白.

    适用于: atomic_facts 抽取前预处理 / 文本展示前清洗.
    不改变标点的中英文 (因为正常显示需要中文标点)。
    """
    if not s:
        return ""
    s = clean_control_chars(s)
    # NFKC 把全角数字/字母 → 半角, 兼容字符归一
    s = unicodedata.normalize("NFKC", s)
    s = normalize_quotes(s)
    s = _MULTI_SPACE_RE.sub(" ", s)
    s = _MULTI_NEWLINE_RE.sub("\n", s)
    return s.strip()


def normalize_for_comparison(s: str | None) -> str:
    """比较专用归一化: 在 normalize_text 之上, 再统一标点 + 繁简 + 大小写.

    用于 fact_contradictions 检测: 两个 value 经过这层后相同, 即不算冲突
    (实际是 OCR/标点差异造成的伪报警)。
    """
    if not s:
        return ""
    s = normalize_text(s)
    s = normalize_punctuation(s)
    s = simplify_traditional(s)
    s = s.lower()
    # 比较时把所有空白都压成无 (因为 OCR 经常多空格)
    s = re.sub(r"\s+", "", s)
    return s


def is_noise_difference(a: str | None, b: str | None) -> bool:
    """判断两个文本是否只是 OCR/标点噪声差异 (语义相同)."""
    return normalize_for_comparison(a) == normalize_for_comparison(b)
