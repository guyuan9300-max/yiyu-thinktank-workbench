"""摸底表自动填写评估器.

定位:
  迭代优化爬虫/字典链路的客观基准. 输入一张真实摸底表 docx + 客户 id,
  自动检查每个字段能否从数据中心 (字典 + atomic_facts + entities + 原始文档)
  抽出候选值, 输出"已填 / 空白 / 命中率"。

为什么不直接 LLM 填表:
  LLM 填表会"编造"——本任务的目的是**测量我们抓到的真实数据覆盖了多少字段**,
  必须用确定性查询, 不能让 LLM 在数据缺口处脑补。

机制化设计 (不硬编码具体客户):
  - 字段名识别: 从 docx table 抽出所有空白单元格 + 其左侧/上方"字段标签"
  - 候选值查询: 按可靠度顺序 [字典verified > 字典pending > entities > atomic_facts > 全文检索]
  - 关键词归一: 字段名通过 _normalize_field 简化, 匹配字典 attribute_name
  - 报告: markdown 表格 + 命中率统计
"""
from __future__ import annotations

import logging
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)

NS_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


@dataclass
class TableFieldCell:
    """表格中的一个待填字段."""
    label: str                  # 字段名 (从相邻单元格抽出)
    row_idx: int
    col_idx: int
    section_title: str = ""     # 所属"二级标题"
    is_filled: bool = False
    existing_value: str = ""


@dataclass
class FieldFillResult:
    """单个字段的填写结果."""
    label: str
    section: str
    candidate_value: str = ""
    source: str = ""            # 'glossary_verified' / 'glossary_pending' / 'atomic_fact' / 'entity' / 'document_text'
    confidence: float = 0.0
    needs_user_fill: bool = False  # 主观字段
    extras: dict[str, Any] = field(default_factory=dict)


# 主观字段关键词 — 这些字段不能靠数据中心填, 必须用户主观陈述
SUBJECTIVE_KEYWORDS: tuple[str, ...] = (
    "建议", "诉求", "希望", "需求", "困难", "优势", "短板", "意见",
    "情况说明", "主观", "评价", "看法", "想法", "计划", "目标",
    "如何", "为何", "为什么", "怎么", "心得", "体会",
)


def _is_subjective_field(label: str) -> bool:
    return any(k in label for k in SUBJECTIVE_KEYWORDS)


def _extract_xml_text(elem) -> str:
    """递归提取 w:t 的文本内容."""
    parts = []
    for t in elem.iter(f"{{{NS_W}}}t"):
        if t.text:
            parts.append(t.text)
    return "".join(parts).strip()


def parse_docx_table_fields(docx_path: Path) -> list[TableFieldCell]:
    """从 docx 中抽出所有"键-值"对位置.

    启发式:
      - 表格每行: 若有偶数个非空标题单元格 + 对应空单元格, 认为是 "标题|值|标题|值" 形式
      - 表格只有 1 列: 单元格内若以"：/:"分隔, 认为是 KV
      - 字段标签 = 上面 H1/H2 段落的最近一个"X、" 节标题
    """
    with zipfile.ZipFile(docx_path) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    root = ET.fromstring(xml)
    body = root.find(f"{{{NS_W}}}body")
    if body is None:
        return []

    fields: list[TableFieldCell] = []
    current_section = ""

    def walk(elem):
        nonlocal current_section
        tag = elem.tag.split("}")[-1]
        if tag == "p":
            text = _extract_xml_text(elem)
            # 节标题: "一、" / "二、" / "三、" 开头
            if re.match(r"^[一二三四五六七八九十]+、", text):
                current_section = text.strip()
            return
        if tag == "tbl":
            rows = list(elem.findall(f".//{{{NS_W}}}tr"))
            for ri, tr in enumerate(rows):
                cells = list(tr.findall(f".//{{{NS_W}}}tc"))
                cell_texts = [_extract_xml_text(tc) for tc in cells]
                # 模式 1: "标题 | 值 | 标题 | 值"  (偶数列, 隔位标题)
                if len(cells) >= 2 and len(cells) % 2 == 0:
                    for ci in range(0, len(cells), 2):
                        label = cell_texts[ci]
                        value = cell_texts[ci + 1] if ci + 1 < len(cells) else ""
                        if not label:
                            continue
                        # 排除"序号"列、"备注"列空字段
                        if label in ("序号", "备注") and len(value) <= 2:
                            continue
                        fields.append(TableFieldCell(
                            label=label, row_idx=ri, col_idx=ci + 1,
                            section_title=current_section,
                            is_filled=bool(value),
                            existing_value=value,
                        ))
                    continue
                # 模式 2: "标题 | 长描述" (2 列, 标题 + 空 / 文字)
                if len(cells) == 2:
                    label = cell_texts[0]
                    value = cell_texts[1]
                    if label and len(label) < 60:
                        fields.append(TableFieldCell(
                            label=label, row_idx=ri, col_idx=1,
                            section_title=current_section,
                            is_filled=bool(value),
                            existing_value=value,
                        ))
            return
        for child in elem:
            walk(child)

    for child in body:
        walk(child)

    return fields


# 字段名 → 字典 attribute_name 关键词映射 (机制化, 不写死客户名)
# 关键词列表里每个都用 LIKE %kw% 模糊匹配, 设计原则:
#   - 高频别名都列上 (LLM 抽时随机选, 我们要包容)
#   - 关键字越短越宽 (例: "成立" 比 "注册成立时间" 更宽容)
FIELD_TO_ATTR_HINTS: dict[str, list[str]] = {
    "基金会全称": ["全称", "机构名称", "组织名称", "名称", "组织全称"],
    "统一社会信用代码": ["信用代码", "组织机构代码", "社会信用"],
    "登记管理机关": ["登记机关", "登记管理", "注册登记"],
    "业务主管/指导单位": ["业务主管", "指导单位"],
    "评估等级": ["评估等级", "AAA", "4A", "5A", "社会组织评估"],
    "评估有效期": ["评估有效期", "有效期"],
    "成立时间": ["成立时间", "成立日期", "注册时间", "注册成立", "成立"],
    "原始基金数额": ["原始基金", "注册资金", "注册资本"],
    "法定代表人": ["法定代表人", "法人", "理事长"],  # 基金会的法人通常就是理事长
    "秘书长/负责人": ["秘书长", "负责人", "理事长"],
    "登记住所": ["登记住所", "注册地址", "住所地"],
    "实际办公地址": ["办公地址", "实际办公", "总部位置", "实际办公地址"],
    "主要业务范围": ["业务范围", "核心业务", "主要业务", "业务方向"],
    "基金会类型": ["基金会类型", "公募", "非公募", "机构性质", "组织性质"],
    "公开募捐资格": ["公开募捐资格", "募捐资格"],
    "慈善组织认定": ["慈善组织", "慈善组织认定"],
    "公益性捐赠税前扣除资格": ["税前扣除", "税前抵扣"],
    "理事人数": ["理事", "理事人数", "理事会人数"],
    "监事人数": ["监事", "监事人数"],
    "专职工作人员人数": ["专职人员", "全职职工", "员工人数"],
    "年度总收入": ["总收入", "年度总收入"],
    "捐赠收入": ["捐赠收入"],
    "公益事业支出": ["公益事业支出", "公益支出"],
    "管理费用": ["管理费用", "行政费"],
    "净资产": ["净资产", "年末净资产"],
    "限定性净资产": ["限定性净资产"],
    "非限定性净资产": ["非限定性净资产"],
    "互联网募捐平台": ["募捐平台", "腾讯公益", "支付宝公益", "水滴"],
    "服务对象总规模": ["服务对象", "受益人数", "覆盖人数", "覆盖学生", "覆盖儿童"],
    "覆盖区/县数量": ["覆盖区", "覆盖县", "覆盖城市"],
    "覆盖街镇/社区数量": ["覆盖街镇", "覆盖社区", "覆盖学校"],
    "年度项目总数": ["项目总数", "项目数量"],
    "年度募捐总额": ["募捐总额", "筹款", "募款", "捐款"],
    "核心服务领域1": ["核心业务", "核心服务", "服务领域", "业务方向"],
    "核心服务领域2": ["核心业务", "核心服务", "服务领域"],
    "核心服务领域3": ["核心业务", "核心服务", "服务领域"],
    "是否设立专项基金": ["专项基金"],
    "项目名称": ["项目名称", "项目"],
    "起止时间": ["发起时间", "启动时间", "项目时间"],
    "项目领域": ["项目领域", "项目方向"],
    "项目负责人": ["项目负责人", "项目主理人"],
    "服务对象与规模": ["服务对象", "覆盖人数", "受益人数"],
    "年度投入（万元）": ["项目投入", "项目支出", "项目预算"],
    "合作单位": ["合作单位", "合作方", "合作伙伴"],
    "官网/公众号/平台账号": ["官网", "公众号", "网站"],
    "志愿者注册人数": ["志愿者", "志愿者人数"],
    "志愿服务总时长": ["志愿服务"],
}


def _value_looks_like_field(value: str, field_label: str) -> bool:
    """启发式: 看 value 内容是否像该字段类型 (避免"机构全称"匹配到几句话, 避免"理事人数"匹配到人名)."""
    import re as _re
    v = (value or "").strip()
    if not v:
        return False
    if field_label == "基金会全称":
        return len(v) < 30 and any(suf in v for suf in ("基金会", "中心", "学会", "服务中心", "公益"))
    if field_label == "统一社会信用代码":
        return bool(_re.match(r"^[A-Z0-9]{15,20}$", v.replace(" ", "")))
    if field_label == "成立时间":
        return bool(_re.search(r"\d{4}\s*[-/年]", v))
    if field_label in ("法定代表人", "秘书长/负责人"):
        # 人名: 2-5 字纯中文 (不能是机构名/句子/数字)
        return 2 <= len(v) <= 5 and all("一" <= c <= "鿿" for c in v)
    # 纯人数字段 — 必须是数字 (允许"X 人"/"X名"等单位)
    if field_label in (
        "理事人数", "监事人数", "专职工作人员人数", "专职人员总数",
        "兼职/顾问人数", "持证社工师人数", "近三年培训次数",
        "志愿者注册人数", "核心志愿者人数", "党员人数",
        "年度项目总数", "覆盖区/县数量", "覆盖街镇/社区数量",
        "公开募捐项目数量", "定向募捐项目数量", "年度资助项目数量",
        "企业合作数量", "政府合作数量", "高校/研究机构合作", "社会组织合作数量",
        "近三年投诉数量",
    ):
        return bool(_re.search(r"\d", v)) and len(v) < 40
    # 金额字段 — 必须含数字 + 单位 (元/万/亿/百万)
    if field_label in (
        "原始基金数额", "年度总收入", "捐赠收入", "政府购买/补助收入",
        "投资收益", "年度总支出", "公益事业支出", "管理费用", "筹资费用",
        "年末净资产", "限定性净资产", "非限定性净资产", "货币资金余额",
        "理财/投资余额", "固定资产原值", "年度募捐总额",
    ):
        return bool(_re.search(r"\d", v)) and any(u in v for u in ("元", "万", "亿", "RMB", "￥", "百万"))
    # 日期字段
    if field_label in ("评估有效期", "起止时间"):
        return bool(_re.search(r"\d{4}\s*[-/年]", v))
    # 是/否 字段
    if field_label.startswith("是否"):
        return any(k in v for k in ("是", "否", "有", "无", "不适用", "已设立", "未设立"))
    return True  # 默认不过滤


def _normalize_field(label: str) -> list[str]:
    """字段名归一 → 关键词列表."""
    s = label.strip()
    if s in FIELD_TO_ATTR_HINTS:
        return FIELD_TO_ATTR_HINTS[s]
    # 模糊匹配
    for key, hints in FIELD_TO_ATTR_HINTS.items():
        if key in s or s in key:
            return hints + [s]
    return [s]


def query_candidate_value(db: Any, client_id: str, label: str) -> FieldFillResult:
    """对一个字段名, 从数据中心找最高可信度的值.

    顺序:
      1. 字典 verified (最高可信度 — 用户审过)
      2. 字典 pending (中可信度 — 系统抽出待审)
      3. atomic_facts (低可信度 — 规则抽取)
      4. entities (粗略 — 仅人名/机构名/地点)
    """
    result = FieldFillResult(label=label, section="")
    if _is_subjective_field(label):
        result.needs_user_fill = True
        result.source = "subjective"
        return result

    keywords = _normalize_field(label)

    # 1. glossary_attributes verified — 同时按 attribute_name LIKE 和 term LIKE 匹配
    for kw in keywords:
        for r in db.fetchall(
            """SELECT ga.value_text, ga.value_unit, ga.scope, ga.as_of_date, cg.term, ga.attribute_name, ga.confidence
               FROM glossary_attributes ga JOIN client_glossary cg ON cg.id = ga.term_id
               WHERE ga.client_id = ? AND ga.verification_status = 'verified'
                 AND (ga.attribute_name LIKE ? OR cg.term LIKE ?)
               ORDER BY ga.confidence DESC, length(ga.value_text) DESC LIMIT 5""",
            (client_id, f"%{kw}%", f"%{kw}%"),
        ):
            v = str(r["value_text"])
            if not _value_looks_like_field(v, label):
                continue
            result.candidate_value = v
            result.source = "glossary_verified"
            result.confidence = 0.95
            result.extras["term"] = r["term"]
            result.extras["attribute_name"] = r["attribute_name"]
            return result

    # 2. glossary_attributes pending — 同时按 attribute_name LIKE 和 term LIKE
    for kw in keywords:
        for r in db.fetchall(
            """SELECT ga.value_text, cg.term, ga.attribute_name, ga.confidence
               FROM glossary_attributes ga JOIN client_glossary cg ON cg.id = ga.term_id
               WHERE ga.client_id = ? AND ga.verification_status = 'pending'
                 AND (ga.attribute_name LIKE ? OR cg.term LIKE ?)
               ORDER BY ga.confidence DESC, length(ga.value_text) DESC LIMIT 5""",
            (client_id, f"%{kw}%", f"%{kw}%"),
        ):
            v = str(r["value_text"])
            if not _value_looks_like_field(v, label):
                continue
            result.candidate_value = v
            result.source = "glossary_pending"
            result.confidence = 0.60
            result.extras["term"] = r["term"]
            result.extras["attribute_name"] = r["attribute_name"]
            return result

    # 3. atomic_facts
    for kw in keywords:
        row = db.fetchone(
            """SELECT subject_text, attribute, value_text FROM atomic_facts
               WHERE client_id = ? AND status = 'active'
                 AND (attribute LIKE ? OR attribute = ?)
               ORDER BY confidence DESC, length(value_text) DESC LIMIT 1""",
            (client_id, f"%{kw}%", kw),
        )
        if row:
            result.candidate_value = str(row["value_text"])
            result.source = "atomic_fact"
            result.confidence = 0.40
            result.extras["subject"] = row["subject_text"]
            return result

    # 4. 文档全文检索 (v2_chunks) — 仅用作"参考片段", 不当填表权威值
    # 对严格类型字段 (人数/金额/信用代码) 跳过此路径 — doc 全文搜命中无法保证类型正确
    strict_typed = label.startswith("是否") or label in (
        "理事人数","监事人数","专职工作人员人数","专职人员总数",
        "兼职/顾问人数","持证社工师人数","近三年培训次数",
        "志愿者注册人数","核心志愿者人数","党员人数",
        "原始基金数额","年度总收入","捐赠收入","政府购买/补助收入",
        "投资收益","年度总支出","公益事业支出","管理费用","筹资费用",
        "年末净资产","限定性净资产","非限定性净资产","货币资金余额",
        "理财/投资余额","固定资产原值","年度募捐总额",
        "统一社会信用代码","成立时间","法定代表人","秘书长/负责人",
    )
    if not strict_typed:
        for kw in keywords:
            row = db.fetchone(
                """SELECT substr(content, max(1, instr(content, ?) - 30), 120) AS snippet
                   FROM v2_chunks v JOIN v2_documents d ON d.id = v.v2_document_id
                   WHERE d.client_id = ? AND v.content LIKE ?
                   LIMIT 1""",
                (kw, client_id, f"%{kw}%"),
            )
            if row and row["snippet"]:
                result.candidate_value = str(row["snippet"]).strip()
                result.source = "document_text"
                result.confidence = 0.20
                return result

    return result


def evaluate_table(docx_path: Path, db: Any, client_id: str) -> dict[str, Any]:
    """运行评估 → 返回 {fields, stats, by_section}."""
    cells = parse_docx_table_fields(docx_path)
    results: list[FieldFillResult] = []
    by_section: dict[str, list[FieldFillResult]] = {}
    for c in cells:
        if c.is_filled:  # 模板里本来就有值的不算"待填" (如填写说明、栏目分隔行)
            continue
        if not c.label.strip() or len(c.label) > 50:
            continue
        # 排除明显的非字段标签 ("序号", "1", "2", "金额单位" 等)
        if c.label.strip() in ("序号", "金额单位", "公益事业支出", "口径说明/备注"):
            # 财务表那种 "公益事业支出 | 2023 | 2024 | 2025 | 口径说明" 模式特殊
            pass
        r = query_candidate_value(db, client_id, c.label)
        r.section = c.section_title
        results.append(r)
        by_section.setdefault(r.section, []).append(r)

    stats = {
        "total": len(results),
        "filled_verified": sum(1 for r in results if r.source == "glossary_verified"),
        "filled_pending": sum(1 for r in results if r.source == "glossary_pending"),
        "filled_fact": sum(1 for r in results if r.source == "atomic_fact"),
        "filled_doc": sum(1 for r in results if r.source == "document_text"),
        "subjective": sum(1 for r in results if r.needs_user_fill),
        "empty": sum(1 for r in results if not r.candidate_value and not r.needs_user_fill),
    }
    stats["filled_any"] = stats["filled_verified"] + stats["filled_pending"] + stats["filled_fact"] + stats["filled_doc"]
    # 真实可信填充率 = verified + pending (字典审过的) / 客观字段总数
    # doc_text 全文片段不算可信填充 (容易混入合同甲方等无关内容)
    stats["filled_trusted"] = stats["filled_verified"] + stats["filled_pending"]
    stats["fill_rate"] = stats["filled_trusted"] / max(stats["total"] - stats["subjective"], 1)
    stats["fill_rate_loose"] = stats["filled_any"] / max(stats["total"] - stats["subjective"], 1)
    return {"fields": results, "by_section": by_section, "stats": stats}


def render_report(eval_result: dict[str, Any]) -> str:
    """渲染 markdown 评估报告."""
    s = eval_result["stats"]
    lines = [
        "# 摸底表自动填写评估报告",
        "",
        f"- 总待填字段: **{s['total']}**",
        f"- ✅ 字典 verified 命中: **{s['filled_verified']}**",
        f"- 🟡 字典 pending 命中: {s['filled_pending']}",
        f"- 🔸 atomic_fact 命中: {s['filled_fact']}",
        f"- 📄 文档全文命中: {s['filled_doc']}",
        f"- 🏠 主观字段 (需用户填): {s['subjective']}",
        f"- ❌ 完全空白: **{s['empty']}**",
        f"- 🎯 客观字段填充率: **{s['fill_rate']*100:.1f}%** (filled / (total - subjective))",
        "",
    ]
    for section, rs in eval_result["by_section"].items():
        lines.append(f"## {section}")
        for r in rs:
            if r.needs_user_fill:
                icon = "🏠"
                val = "(用户主观)"
            elif r.source == "glossary_verified":
                icon = "✅"
                val = r.candidate_value[:60]
            elif r.source == "glossary_pending":
                icon = "🟡"
                val = r.candidate_value[:60]
            elif r.source == "atomic_fact":
                icon = "🔸"
                val = r.candidate_value[:60]
            elif r.source == "document_text":
                icon = "📄"
                val = r.candidate_value[:60]
            else:
                icon = "❌"
                val = "空"
            lines.append(f"- {icon} **{r.label}**: {val}")
        lines.append("")
    return "\n".join(lines)
