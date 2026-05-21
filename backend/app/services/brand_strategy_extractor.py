"""品牌战略推演树抽取 (P14-D, 2026-05-20).

输入: client_strategic_documents 的 strategy.md + methodology.md (用户上传, 已澄清确认)
处理: 一次 LLM 调用 (qwen3-vl:32b, 复用模型按 [[project_yiyu_model_reuse]]),
     按"业务设计方法论"演绎应然利益相关方角色清单 (数量不预设).
输出: 战略主张段 + 方法学段 + 利益相关方应然清单, 入 client_brand_strategy_extracts.

设计哲学 (跟 strategic_context helper 一致):
  - 严格基于用户上传的 .md, 不允许编造
  - 缺 strategy 或 methodology 时直接拒绝抽取 (不偷换)
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.db import Database

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────
# 业务设计方法论 (益语智库 IP 草案; 后续会让用户在系统层配置覆盖)
# ──────────────────────────────────────────────────────────────────────────
# 这是 LLM 演绎利益相关方角色时的"拆分规则", 不是预设枚举.
# LLM 根据客户的战略+方法论, 引用这里的规则做演绎; 实际产出数量和粒度可变.

DEFAULT_BUSINESS_METHODOLOGY = """\
公益机构利益相关方拆分规则 (益语智库业务设计方法论 v0.1):

资金链路必须按沟通策略差异分层, 不要简单合成"资助方":
  - 大额单次资助方 (企业 CSR / 大基金会): 需要 ROI 数据 + 治理透明
  - 月捐 / 持续小额公众: 需要持续陪伴感 + 进度仪式感
  - 单次小额公众: 需要即时温暖故事
  - 物资 / 资源捐赠方: 需要使用反馈 + 受益规模
  - 政府专项拨款: 需要合规说明 + 政策对齐

政府层级必须按合规需求分层:
  - 部委 / 中央政策制定者
  - 省级 (业务主管)
  - 地级 / 县级 (执行落地)
  - 民政 / 教育 / 卫健 等不同条线 (按客户业务领域决定哪些是关键)

学术 / 行业必须按合作模式分层:
  - 上游研究者 (理论制定者) - 需要原创方法论
  - 同行机构 (标准协调) - 需要行业引领姿态
  - 智库 (决策影响) - 需要数据洞察

媒体必须按发声方式分层:
  - 主流权威 (深度故事)
  - 垂直行业 (专业报道)
  - 自媒体 (情感共鸣)
  - KOL 二级传播 (引爆点)

受益侧必须按关注点分层:
  - 一线执行 (教师 / 社工等) - 需要可上手工具
  - 中间层 (校长 / 主管等) - 需要管理价值
  - 受益人本人 - 需要被尊重感
  - 受益人关键关联方 (家长等) - 需要安心感

人才市场:
  - 应届求职者 - 需要价值观与成长
  - 行业转岗候选 - 需要专业积累
  - 志愿者 - 需要参与感

判断原则:
  1. 如果两类利益相关方"应传递的核心要素"或"期望动作"明显不同, 必须独立成类
  2. 如果客户战略里没有涉及某一类 (例: 客户战略不依赖月捐), 则不必列出
  3. 不预设固定 7 类或 12 类, 数量完全由客户战略+方法论演绎得出 (实际可能 5-20 类)
"""


# ──────────────────────────────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().replace(microsecond=0).isoformat()


def _md_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class BrandStrategyExtract:
    client_id: str
    strategic_objective: str
    strategic_objective_sources: list[str]
    methodology: str
    methodology_sources: list[str]
    stakeholders: list[dict[str, Any]]
    source_strategy_md_hash: str
    source_methodology_md_hash: str
    llm_model: str
    error: str | None
    extracted_at: str
    confirmed_by: str | None
    confirmed_at: str | None
    is_stale: bool  # 源 md hash 跟当前不一致, 需要重抽


_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "strategic_objective", "methodology", "stakeholders",
    ],
    "properties": {
        "strategic_objective": {"type": "string", "minLength": 60, "maxLength": 600},
        "strategic_objective_sources": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 8,
        },
        "methodology": {"type": "string", "minLength": 60, "maxLength": 800},
        "methodology_sources": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 8,
        },
        "stakeholders": {
            "type": "array",
            "minItems": 3,
            "maxItems": 25,
            "items": {
                "type": "object",
                "required": ["name", "core_message", "desired_action"],
                "properties": {
                    "name": {"type": "string", "maxLength": 40},
                    "rationale": {"type": "string", "maxLength": 200},
                    "distinguishing_feature": {"type": "string", "maxLength": 120},
                    "core_message": {"type": "string", "maxLength": 200},
                    "desired_action": {"type": "string", "maxLength": 150},
                    "key_examples": {
                        "type": "array",
                        "items": {"type": "string"},
                        "maxItems": 6,
                    },
                },
            },
        },
    },
}


def _build_prompt(
    *, client_name: str, strategy_md: str, methodology_md: str,
    business_methodology: str,
) -> str:
    return f"""下面是「{client_name}」的战略文档与业务方法论, 都是客户已澄清确认的官方资料 (.md 上传)。
请按"业务设计方法论"演绎应然利益相关方矩阵。

## 任务要求

输出严格 JSON, 含以下三块:

1. `strategic_objective` (60-100 字, **严格上限 100**): 一句话讲清楚客户的战略主张 — 文档里最核心的 What & Why.
   不展开背景, 不写"在 2026-2028 年" 这种铺垫. 让没读过文档的人 30 秒 get 到客户想做什么+为什么.
   `strategic_objective_sources` (3-6 项): 标注是从战略文档的哪些章节/段落抽出 (例 ["机构使命", "2026 工作重点"]).

2. `methodology` (60-100 字, **严格上限 100**): 一句话讲清楚客户实现战略的方法学骨架 — 关键路径/飞轮/抓手.
   **战略主张+方法学加起来不超过 200 字**, 用最锋利的语言, 不要客套, 不要小标题, 不要分段.
   `methodology_sources` (3-6 项): 标注从方法论文档的哪些章节抽出.

3. `stakeholders` (5-20 项, 数量不预设): 应然利益相关方角色清单, 严格按"业务设计方法论"演绎. 每项含:
   - `name`: 自由命名 (例: "大额企业资助方" / "月捐人" / "县教育局" / "高校 SEL 研究者"). **数量和粒度完全由客户战略决定**, 不要硬凑 7 类或 12 类.
   - `rationale`: 为什么这类利益相关方对实现战略**必要** (60-120 字)
   - `distinguishing_feature`: 跟"隔壁角色"的关键区别 (30-60 字, 例: "跟单次捐赠者的区别在于持续陪伴需求")
   - `core_message`: 应当向此角色传递的核心要素 (60-150 字)
   - `desired_action`: 期望此角色产生什么动作 (30-100 字)
   - `key_examples` (可选): 战略/方法论文档里**明确提到的**具体例子 (3-6 个, 例 ["腾讯", "字节"])

## 硬约束

- **严格基于上传的两份 .md**, 不要从其他知识源补充客户战略. 文档没覆盖的, 老实留空, 不要编.
- **不要预设数量**: 如果客户战略不依赖月捐, 就不要硬列月捐. 如果客户高度依赖学术合作, 就要拆出"上游研究者 / 同行机构 / 智库"等多类.
- 每个 stakeholder 都要解释"为什么必须独立成类", 不能简单合并 ("资助方"这种概括性词必须拆开).
- 用中文回答.

## 业务设计方法论 (拆分规则参考)

{business_methodology}

## 客户战略文档

{strategy_md}

## 客户业务方法论文档

{methodology_md}
"""


def _coerce_payload(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\s*```$", "", text)
        return json.loads(text)
    raise ValueError(f"LLM 返回类型异常: {type(raw).__name__}")


def _sanitize_stakeholders(raw: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for entry in raw or []:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "").strip()
        core = str(entry.get("core_message") or "").strip()
        action = str(entry.get("desired_action") or "").strip()
        if not name or not core or not action:
            continue
        out.append({
            "name": name[:40],
            "rationale": str(entry.get("rationale") or "").strip()[:240],
            "distinguishingFeature": str(entry.get("distinguishing_feature") or "").strip()[:160],
            "coreMessage": core[:240],
            "desiredAction": action[:180],
            "keyExamples": [
                str(e).strip() for e in (entry.get("key_examples") or []) if str(e).strip()
            ][:6],
        })
    return out


def _read_strategic_docs(db: Database, client_id: str) -> dict[str, str]:
    """读两份 md. 返回 {'strategy': md, 'methodology': md}, 缺失则空串."""
    cur = db.conn.execute(
        """SELECT doc_type, md_content FROM client_strategic_documents
           WHERE client_id = ?""",
        (client_id,),
    )
    out = {"strategy": "", "methodology": ""}
    for row in cur.fetchall():
        doc_type = str(row[0] or "")
        if doc_type in out:
            out[doc_type] = str(row[1] or "")
    return out


def run_brand_strategy_extraction(
    db: Database,
    ai_service: Any,
    *,
    client_id: str,
    client_name: str,
    business_methodology: str | None = None,
) -> BrandStrategyExtract:
    """同步跑一次抽取 (约 30-90 秒) → 入库 → 返回结果."""
    if ai_service is None or not hasattr(ai_service, "_qwen_generate"):
        raise RuntimeError("AI 服务不可用, 无法生成战略推演树")

    docs = _read_strategic_docs(db, client_id)
    if not docs["strategy"].strip() or not docs["methodology"].strip():
        missing = []
        if not docs["strategy"].strip():
            missing.append("战略文档")
        if not docs["methodology"].strip():
            missing.append("方法论文档")
        raise ValueError(
            f"客户尚未上传 {' + '.join(missing)}, 请先在战略陪伴页上传"
        )

    strategy_md = docs["strategy"]
    methodology_md = docs["methodology"]
    bm = (business_methodology or DEFAULT_BUSINESS_METHODOLOGY).strip()

    prompt = _build_prompt(
        client_name=client_name,
        strategy_md=strategy_md,
        methodology_md=methodology_md,
        business_methodology=bm,
    )
    system_instruction = (
        "你是品牌战略顾问, 善于从客户官方战略文档里演绎应然利益相关方矩阵. "
        "严格基于客户上传的 .md, 不要从其他知识源补充. "
        "数量不预设, 完全由客户战略决定. 输出严格 JSON."
    )

    llm_model = ""
    error: str | None = None
    payload: dict[str, Any] = {}
    try:
        raw_text = ai_service._qwen_generate(
            prompt=prompt,
            system_instruction=system_instruction,
            response_schema=_RESPONSE_SCHEMA,
            timeout_seconds=180.0,
            max_tokens=6000,
            temperature=0.3,
            top_p=0.85,
        )
        payload = _coerce_payload(raw_text)
        llm_model = "qwen3-vl:32b"
    except Exception as exc:  # noqa: BLE001
        error = f"llm_failed: {str(exc)[:400]}"
        logger.warning("[brand-strategy-extract] LLM 失败 client=%s: %s", client_id, exc)

    strategic_objective = str(payload.get("strategic_objective") or "").strip()
    strategic_objective_sources = [
        str(x).strip() for x in (payload.get("strategic_objective_sources") or []) if str(x).strip()
    ][:8]
    methodology = str(payload.get("methodology") or "").strip()
    methodology_sources = [
        str(x).strip() for x in (payload.get("methodology_sources") or []) if str(x).strip()
    ][:8]
    stakeholders = _sanitize_stakeholders(payload.get("stakeholders") or [])

    now = _now_iso()
    strategy_hash = _md_hash(strategy_md)
    methodology_hash = _md_hash(methodology_md)

    db.execute(
        """INSERT INTO client_brand_strategy_extracts (
            client_id, strategic_objective, strategic_objective_sources_json,
            methodology, methodology_sources_json, stakeholders_json,
            source_strategy_md_hash, source_methodology_md_hash,
            llm_model, llm_raw_json, error,
            extracted_at, confirmed_by, confirmed_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?)
        ON CONFLICT(client_id) DO UPDATE SET
            strategic_objective = excluded.strategic_objective,
            strategic_objective_sources_json = excluded.strategic_objective_sources_json,
            methodology = excluded.methodology,
            methodology_sources_json = excluded.methodology_sources_json,
            stakeholders_json = excluded.stakeholders_json,
            source_strategy_md_hash = excluded.source_strategy_md_hash,
            source_methodology_md_hash = excluded.source_methodology_md_hash,
            llm_model = excluded.llm_model,
            llm_raw_json = excluded.llm_raw_json,
            error = excluded.error,
            extracted_at = excluded.extracted_at,
            confirmed_by = NULL,
            confirmed_at = NULL,
            updated_at = excluded.updated_at""",
        (
            client_id, strategic_objective,
            json.dumps(strategic_objective_sources, ensure_ascii=False),
            methodology,
            json.dumps(methodology_sources, ensure_ascii=False),
            json.dumps(stakeholders, ensure_ascii=False),
            strategy_hash, methodology_hash,
            llm_model,
            json.dumps(payload, ensure_ascii=False)[:200000],
            error, now, now,
        ),
    )
    db.conn.commit()

    return BrandStrategyExtract(
        client_id=client_id,
        strategic_objective=strategic_objective,
        strategic_objective_sources=strategic_objective_sources,
        methodology=methodology,
        methodology_sources=methodology_sources,
        stakeholders=stakeholders,
        source_strategy_md_hash=strategy_hash,
        source_methodology_md_hash=methodology_hash,
        llm_model=llm_model,
        error=error,
        extracted_at=now,
        confirmed_by=None,
        confirmed_at=None,
        is_stale=False,
    )


def get_brand_strategy_extract(
    db: Database, *, client_id: str,
) -> dict[str, Any] | None:
    """读最新的抽取缓存, 含 is_stale 标记 (源 md 是否被更新过)."""
    cur = db.conn.execute(
        """SELECT strategic_objective, strategic_objective_sources_json,
                  methodology, methodology_sources_json, stakeholders_json,
                  source_strategy_md_hash, source_methodology_md_hash,
                  llm_model, error, extracted_at, confirmed_by, confirmed_at
           FROM client_brand_strategy_extracts
           WHERE client_id = ?""",
        (client_id,),
    )
    row = cur.fetchone()
    if not row:
        return None

    def _safe(text: str, fallback: Any) -> Any:
        try:
            return json.loads(text)
        except (ValueError, TypeError):
            return fallback

    # 检查源 md hash 是否一致 (用户重传后, hash 变化 → 提示重抽)
    docs = _read_strategic_docs(db, client_id)
    current_strategy_hash = _md_hash(docs["strategy"])
    current_methodology_hash = _md_hash(docs["methodology"])
    is_stale = (
        current_strategy_hash != str(row[5] or "")
        or current_methodology_hash != str(row[6] or "")
    )

    return {
        "clientId": client_id,
        "strategicObjective": row[0],
        "strategicObjectiveSources": _safe(row[1], []),
        "methodology": row[2],
        "methodologySources": _safe(row[3], []),
        "stakeholders": _safe(row[4], []),
        "sourceStrategyMdHash": row[5],
        "sourceMethodologyMdHash": row[6],
        "llmModel": row[7],
        "error": row[8],
        "extractedAt": row[9],
        "confirmedBy": row[10],
        "confirmedAt": row[11],
        "isStale": is_stale,
    }


__all__ = [
    "BrandStrategyExtract",
    "run_brand_strategy_extraction",
    "get_brand_strategy_extract",
    "DEFAULT_BUSINESS_METHODOLOGY",
]
