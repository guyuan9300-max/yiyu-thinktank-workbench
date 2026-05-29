"""字典属性自动 verify 规则引擎.

== 用户原话 (核心需求) ==

"我看见里面有大量的内容, 实际上根本不用人来澄清,
 资讯情报站都可以把握很多官方渠道, 这里怎么还需要人来澄清呢?"

== 设计原则 ==

满足下面任何一档 → 自动 verified, 不进 pending 队列 (不浪费用户时间):

  档 A · 白名单基础登记字段 + 权威源
      字段: 注册名/成立时间/原始基金/登记机关/基金会类型 等历史事实
      来源: 百度百科/南都基金会/民政厅/天眼查/官网/慈善中国
      理由: 这些字段是注册时确定的,权威源记录稳定,自动 verify 比让用户点点点更高效

  档 B · 客观可查格式
      URL 字段 (官网地址) / 社交账号字段 (公众号/抖音/微博/小红书) / 是否字段
      理由: value 格式天然防错, 不可能写错

  档 C · 多源交叉验证
      同一 (term, attribute_name) 在 2+ 不同来源都抽出且 value 等价
      理由: 多源印证 = 比单源 + 用户审更可靠

防误判:
  · 黑名单: SUBJECTIVE 字段(突出优势/主要困难/政策建议) 永不自动 verify
  · 冲突保护: 同 (term, attribute_name) 存在多个不同值的 pending → 不自动 verify (走 drift_alert)
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


# 档 A · 白名单字段 (符合"客户官方注册时确定的历史事实"特征)
# 包含两种命名: 标准摸底表名 + 抽取器实际产出名 (LLM 不一定严格对齐 schema)
AUTO_VERIFY_FIELD_WHITELIST: set[str] = {
    # 注册登记类 (标准名)
    "基金会全称",
    "统一社会信用代码",
    "登记管理机关",
    "业务主管/指导单位",
    "成立时间",
    "原始基金数额",
    "登记住所",
    # 注册登记类 (抽取器常见变体)
    "成立日期", "注册时间", "注册日期", "发起时间", "前身发起时间",
    "注册机关", "注册登记机关", "登记机关",
    "注册地址", "登记地址", "注册地",
    "原始基金", "注册资金", "注册资本",
    "统一信用代码", "社会信用代码",
    "业务主管单位", "业务指导单位", "主管单位",

    # 治理类 (标准)
    "法定代表人",
    "秘书长/负责人",
    "实际办公地址",
    "主要业务范围",
    "基金会类型",
    # 治理类 (变体)
    "理事长", "理事长姓名",
    "秘书长", "秘书长姓名",
    "机构性质", "组织性质", "单位性质",
    "办公地址", "办公地点", "办公区域",
    "业务范围", "主营业务",
    "机构类型", "组织类型",

    # 资质类
    "公开募捐资格", "公开募捐资质", "募捐资格",
    "慈善组织认定", "慈善组织资格", "慈善组织属性",
    "公益性捐赠税前扣除资格", "税前扣除资格", "公益性税前扣除",
    "评估等级", "AAA等级", "5A等级",

    # 互联网公开渠道
    "互联网募捐备案/合作平台",
    "官网/公众号/平台账号",
    "官网", "官网地址", "网址", "网站",

    # 项目命名 (稳定)
    "项目名称",
    "项目领域", "议题领域", "服务领域",
    "实施地区", "项目地区", "覆盖地区",
}


# 权威源关键词 (出现在 source_evidence / source_type / source_url 任一处)
AUTHORITY_SOURCE_TOKENS: tuple[str, ...] = (
    # 百科类
    "百度百科", "搜狗百科", "维基百科", "百科",
    # 政府/民政
    "民政厅", "民政部", "慈善中国", "慈善组织登记",
    "gov.cn", "mca.gov", "mzj.gz", "cszg.mca", "csmh",
    # 行业权威
    "南都公益基金会", "基金会中心网", "北师大公益研究院",
    "天眼查", "企查猫", "爱企查", "企查宝", "企查查",
    # 客户自己的官方源
    "官网", "官方网站", "官方简介", "信息公开",
    "年度工作报告", "年报", "审计报告", "财务报告",
    "机构章程", "章程", "组织架构",
)


# 主观字段黑名单 (永不自动 verify, 必须人审)
SUBJECTIVE_FIELD_PATTERNS: tuple[str, ...] = (
    "建议", "诉求", "希望", "需求", "困难", "优势", "短板", "意见",
    "情况说明", "主观", "评价", "看法", "想法", "心得", "体会",
    "如何", "为何", "怎么",
)


def _is_subjective(attribute_name: str) -> bool:
    name = (attribute_name or "").strip()
    return any(p in name for p in SUBJECTIVE_FIELD_PATTERNS)


def _has_authority_source(attr: dict) -> bool:
    """判断 attribute 的来源是不是权威源."""
    blob = " ".join([
        str(attr.get("source_evidence", "") or ""),
        str(attr.get("source_type", "") or ""),
        str(attr.get("source_doc_id", "") or ""),
        str(attr.get("source_doc_title", "") or ""),
    ])
    return any(tok in blob for tok in AUTHORITY_SOURCE_TOKENS)


def _looks_like_url(value: str) -> bool:
    v = (value or "").strip()
    if v.startswith(("http://", "https://")) or v.startswith("www."):
        return True
    # 多段域名: foo.org.cn / foo.com / foo.gov.cn 等
    return bool(re.match(r"^[a-zA-Z0-9-]+(\.[a-zA-Z0-9-]+){1,3}(/.*)?$", v))


def _looks_like_social_account_field(attribute_name: str) -> bool:
    """字段名属于'社交账号'类 (官方公众号/抖音/微博/小红书 等)."""
    name = (attribute_name or "").lower()
    return any(k in name for k in (
        "公众号", "微博", "抖音", "小红书", "b站", "bilibili",
        "知乎", "视频号", "账号", "platform", "social",
    ))


def _looks_like_yes_no_field(attribute_name: str, value: str) -> bool:
    """字段名'是否X' 且 value 是简单 yes/no 答复."""
    name = (attribute_name or "").strip()
    v = (value or "").strip()
    if not name.startswith("是否"):
        return False
    return v in ("是", "否", "有", "无", "已", "未", "不适用", "暂无")


def can_auto_verify(attr: dict) -> tuple[bool, str]:
    """对一条 pending attribute 判定能否自动 verify.

    返回 (可否, 原因标签).
    """
    name = str(attr.get("attribute_name", "") or "")
    value = str(attr.get("value_text", "") or "")
    conf = float(attr.get("confidence", 0) or 0)

    if not name or not value:
        return False, "empty"

    # 黑名单: SUBJECTIVE 字段永远不自动
    if _is_subjective(name):
        return False, "subjective_field"

    # 必要门槛: confidence ≥ 0.9
    if conf < 0.9:
        return False, "conf_too_low"

    # 档 B 优先 (天然防错, 直接通过)
    # URL 字段
    if _looks_like_url(value):
        return True, "B_url_value"
    # 社交账号字段
    if _looks_like_social_account_field(name):
        return True, "B_social_account_field"
    # 是否字段简单回答
    if _looks_like_yes_no_field(name, value):
        return True, "B_yes_no_simple"

    # 档 A · 白名单字段 + (权威源 或 conf ≥ 0.98)
    if name in AUTO_VERIFY_FIELD_WHITELIST:
        if _has_authority_source(attr):
            return True, "A_whitelist_field_authority_source"
        if conf >= 0.98:
            return True, "A_whitelist_field_very_high_conf"

    # 档 D · 兜底规则: 高 conf (≥ 0.95) + 权威源 + 非主观 + 非"决策规则/政策/管理"类
    #   (用户原话: 资讯情报站抓到的官方资料 conf 这么高, 这里怎么还需要人来澄清?)
    # 黑名单字段头: 包含这些词的字段名极易模糊 (制度/政策/规则/要求), 留人审
    NONFACT_TOKENS = ("规则", "标准", "要求", "制度", "政策", "管理", "决策")
    if conf >= 0.95 and _has_authority_source(attr):
        if not any(tok in name for tok in NONFACT_TOKENS):
            return True, "D_high_conf_authority_source"

    return False, "no_rule_matched"


def has_value_conflict(db: Any, client_id: str, term_id: str, attribute_name: str, candidate_value: str) -> bool:
    """档 C 防护: 看是否有同 (term, attribute_name) 的不同 value 在 pending 或 verified.

    冲突 → 不自动 verify (走 drift_alert 让用户决策).
    """
    rows = db.fetchall(
        """SELECT value_text FROM glossary_attributes
           WHERE client_id = ? AND term_id = ? AND attribute_name = ?
             AND verification_status IN ('pending', 'verified')""",
        (client_id, term_id, attribute_name),
    )
    if not rows:
        return False
    # 简单归一: 去空格/标点比较
    def _norm(v: str) -> str:
        return re.sub(r"[\s,。·、\-\—_]+", "", str(v or "").strip())
    cand_norm = _norm(candidate_value)
    for r in rows:
        if _norm(str(r["value_text"])) != cand_norm:
            return True
    return False


def auto_verify_qualifying_attributes(
    db: Any,
    client_id: str,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """扫客户所有 pending attributes, 对满足规则的自动 verify.

    用法: Stage 3 抽完后立即调; 或 worker 定时跑 (扫整个数据库的 pending).
    dry_run=True: 只算不写库 (用于 UI 预览).

    返回 stats:
      {
        "total_pending": N,
        "auto_verified": X,
        "skipped_subjective": Y,
        "skipped_low_conf": Z,
        "skipped_conflict": W,
        "details": [...]
      }
    """
    rows = db.fetchall(
        """SELECT ga.id, ga.term_id, ga.attribute_name, ga.value_text, ga.value_category,
                  ga.confidence, ga.source_evidence, ga.source_type,
                  ga.source_doc_id, cg.term
           FROM glossary_attributes ga JOIN client_glossary cg ON cg.id = ga.term_id
           WHERE ga.client_id = ? AND ga.verification_status = 'pending'""",
        (client_id,),
    )
    stats = {
        "total_pending": len(rows),
        "auto_verified": 0,
        "skipped_subjective": 0,
        "skipped_low_conf": 0,
        "skipped_no_match": 0,
        "skipped_conflict": 0,
        "details": [],
    }
    now = datetime.now(timezone.utc).isoformat()
    for r in rows:
        attr = {
            "id": r["id"],
            "term": r["term"],
            "term_id": r["term_id"],
            "attribute_name": r["attribute_name"],
            "value_text": r["value_text"],
            "value_category": r["value_category"],
            "confidence": r["confidence"],
            "source_evidence": r["source_evidence"],
            "source_type": r["source_type"],
            "source_doc_id": r["source_doc_id"],
        }
        ok, reason = can_auto_verify(attr)
        if not ok:
            if reason == "subjective_field":
                stats["skipped_subjective"] += 1
            elif reason == "conf_too_low":
                stats["skipped_low_conf"] += 1
            else:
                stats["skipped_no_match"] += 1
            continue
        # 冲突检测
        if has_value_conflict(db, client_id, attr["term_id"], attr["attribute_name"], attr["value_text"]):
            stats["skipped_conflict"] += 1
            stats["details"].append({
                "id": attr["id"],
                "term": attr["term"],
                "attribute_name": attr["attribute_name"],
                "value_text": str(attr["value_text"])[:50],
                "action": "skipped_conflict",
                "reason": "同字段在字典里有不同 value, 走 drift_alert 不自动 verify",
            })
            continue
        if not dry_run:
            try:
                db.execute(
                    """UPDATE glossary_attributes
                       SET verification_status = 'verified',
                           verified_by = 'auto_verify_rule',
                           verified_at = ?
                       WHERE id = ?""",
                    (now, attr["id"]),
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("[auto-verify] update failed for %s: %s", attr["id"], exc)
                continue
        stats["auto_verified"] += 1
        stats["details"].append({
            "id": attr["id"],
            "term": attr["term"],
            "attribute_name": attr["attribute_name"],
            "value_text": str(attr["value_text"])[:50],
            "action": "auto_verified",
            "rule": reason,
        })

    logger.info(
        "[auto-verify] client=%s total_pending=%d auto_verified=%d "
        "skipped_subj=%d low_conf=%d conflict=%d no_match=%d",
        client_id, stats["total_pending"], stats["auto_verified"],
        stats["skipped_subjective"], stats["skipped_low_conf"],
        stats["skipped_conflict"], stats["skipped_no_match"],
    )
    return stats
