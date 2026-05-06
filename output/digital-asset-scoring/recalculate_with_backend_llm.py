from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.db import Database  # noqa: E402
from app.services.ai import AiService  # noqa: E402
from app.services.digital_asset_center import build_client_digital_assets  # noqa: E402
from app.services.secrets import MacOSKeychainSecretStore  # noqa: E402


DEFAULT_DB = Path("/Users/guyuanyuan/Library/Application Support/YiyuThinkTankWorkbench2/app.db")


LABEL_KEYWORDS: dict[str, tuple[str, ...]] = {
    "组织/战略": ("战略", "使命", "愿景", "定位", "治理", "组织", "品牌", "价值观", "规划", "路线"),
    "项目/业务": ("项目", "业务", "计划", "工作坊", "课程", "活动", "交付", "服务", "年会", "论坛", "工具包"),
    "服务对象": ("儿童", "青少年", "教师", "学生", "学校", "家长", "社区", "志愿者", "伙伴", "资方", "机构", "对象", "受众"),
    "流程/过程": ("报名", "签到", "审核", "入群", "参与", "执行", "节点", "流程", "复盘", "结课", "会议纪要", "纪要"),
    "反馈/成效": ("反馈", "满意度", "评估", "前测", "后测", "变化", "成效", "成果", "影响力", "案例", "结果", "复盘"),
    "数据/系统": ("数据", "系统", "平台", "表单", "看板", "数据库", "自动化", "AI", "字段", "指标", "统计"),
    "生态/关系": ("合作", "伙伴", "资源", "网络", "生态", "协作", "资助", "基金会", "公益", "联盟"),
    "传播/筹款": ("传播", "筹款", "公募", "年报", "故事", "媒体", "品牌", "推文", "视频", "B站", "影响力"),
    "研究/内容": ("研究", "报告", "调研", "访谈", "文章", "章节", "文献", "案例", "观点", "分析", "报告"),
    "财务/合同": ("合同", "协议", "预算", "决算", "财务", "发票", "报销", "捐赠", "采购", "报价"),
}

PROFILE_HINTS: dict[str, tuple[str, ...]] = {
    "组织战略陪伴型": ("战略", "使命", "愿景", "定位", "治理", "规划", "判断", "会议纪要"),
    "公益项目运营型": ("项目", "活动", "工作坊", "报名", "教师", "儿童", "学校", "反馈", "成效", "前测", "后测"),
    "研究报告/田野型": ("研究", "报告", "调研", "访谈", "个案", "案例", "社区", "样本", "章节"),
    "平台/行业生态型": ("论坛", "年会", "行业", "生态", "平台", "机构", "工具包", "评估报告"),
    "产品/系统运营型": ("系统", "产品", "测试", "功能", "看板", "技术", "工作台", "自动化"),
    "内容/IP资产型": ("文章", "视频", "观点", "素材", "发布", "B站", "内容"),
}


def trim(value: object, limit: int = 480) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def rows(conn: sqlite3.Connection, sql: str, params: tuple[object, ...] = ()) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def safe_count(conn: sqlite3.Connection, sql: str, params: tuple[object, ...]) -> int:
    try:
        return int(conn.execute(sql, params).fetchone()[0])
    except Exception:
        return 0


def classify_text(text: str) -> list[str]:
    return [label for label, keywords in LABEL_KEYWORDS.items() if any(keyword.lower() in text.lower() for keyword in keywords)]


def infer_profile_scores(text: str) -> dict[str, int]:
    lowered = text.lower()
    scores = {}
    for profile, keywords in PROFILE_HINTS.items():
        scores[profile] = sum(lowered.count(keyword.lower()) for keyword in keywords)
    return scores


def get_material_rows(conn: sqlite3.Connection, client_id: str) -> list[dict[str, Any]]:
    v2 = rows(
        conn,
        """
        SELECT id, document_id, file_name AS title, kind, original_path, visible_category,
               secondary_category, parse_status,
               COALESCE(NULLIF(markdown_content,''), NULLIF(doc_index_text,''), NULLIF(preview_text,''), '') AS text,
               updated_at
        FROM v2_documents
        WHERE client_id = ?
        """,
        (client_id,),
    )
    if v2:
        return v2
    return rows(
        conn,
        """
        SELECT id, id AS document_id, title, kind, path AS original_path, '' AS visible_category,
               '' AS secondary_category, 'legacy' AS parse_status, excerpt AS text, created_at AS updated_at
        FROM documents
        WHERE client_id = ?
        """,
        (client_id,),
    )


def build_client_pack(conn: sqlite3.Connection, db: Database, client: dict[str, Any]) -> dict[str, Any]:
    client_id = str(client["id"])
    materials = get_material_rows(conn, client_id)
    label_counts: Counter[str] = Counter()
    profile_scores: Counter[str] = Counter()
    label_examples: dict[str, list[str]] = defaultdict(list)
    ext_counts: Counter[str] = Counter()
    parse_counts: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    high_signal: list[dict[str, str]] = []

    for item in materials:
        title = str(item.get("title") or "")
        path = str(item.get("original_path") or "")
        text = trim(item.get("text"), 1200)
        haystack = f"{title} {path} {text}"
        labels = classify_text(haystack)
        for label in labels:
            label_counts[label] += 1
            if len(label_examples[label]) < 8:
                label_examples[label].append(title)
        profile_scores.update(infer_profile_scores(haystack))
        ext = Path(title).suffix.lower() or str(item.get("kind") or "unknown")
        ext_counts[ext] += 1
        parse_counts[str(item.get("parse_status") or "unknown")] += 1
        category = str(item.get("visible_category") or "未分类")
        category_counts[category] += 1
        signal = len(labels) + len(text) / 1800
        if signal >= 3 and len(high_signal) < 80:
            high_signal.append(
                {
                    "title": title,
                    "labels": "、".join(labels[:5]),
                    "excerpt": trim(text, 220),
                }
            )

    detail = build_client_digital_assets(db, client_id)
    metric_map = {metric.key: int(metric.value) for metric in detail.metrics}
    asset_nodes = [
        {
            "name": node.label,
            "maturityPercent": node.maturityPercent,
            "currentStage": node.currentStage,
            "seenSummary": node.seenSummary,
            "missingSummary": node.missingSummary,
            "unlockedAnalysisValue": node.unlockedAnalysisValue,
            "sourceHighlights": [source.title for source in node.representativeSources[:5]],
        }
        for node in detail.assetMapNodes[:10]
    ]
    evidence_examples = rows(
        conn,
        """
        SELECT normalized_claim, quote, evidence_type, confidence, quality_tier, updated_at
        FROM evidence_cards
        WHERE client_id = ?
        ORDER BY updated_at DESC
        LIMIT 8
        """,
        (client_id,),
    )
    judgment_examples = rows(
        conn,
        """
        SELECT topic, summary, confidence, quality_tier, updated_at
        FROM judgment_versions
        WHERE client_id = ?
        ORDER BY updated_at DESC
        LIMIT 6
        """,
        (client_id,),
    )
    event_examples = rows(
        conn,
        """
        SELECT name, stage, summary, current_blocker, recent_decision, next_step, evidence_count, updated_at
        FROM event_lines
        WHERE primary_client_id = ?
        ORDER BY updated_at DESC
        LIMIT 6
        """,
        (client_id,),
    )
    counts = {
        "documents": metric_map.get("documents", safe_count(conn, "SELECT COUNT(1) FROM documents WHERE client_id = ?", (client_id,))),
        "v2Documents": safe_count(conn, "SELECT COUNT(1) FROM v2_documents WHERE client_id = ?", (client_id,)),
        "memoryFacts": metric_map.get("memoryFacts", 0),
        "eventLines": metric_map.get("eventLines", safe_count(conn, "SELECT COUNT(1) FROM event_lines WHERE primary_client_id = ?", (client_id,))),
        "meetings": metric_map.get("meetings", safe_count(conn, "SELECT COUNT(1) FROM meetings WHERE client_id = ?", (client_id,))),
        "tasks": safe_count(
            conn,
            """
            SELECT COUNT(1)
            FROM tasks t
            LEFT JOIN event_lines e ON t.event_line_id = e.id
            WHERE (e.primary_client_id = ? OR (t.source_type = 'client' AND t.source_id = ?))
              AND COALESCE(t.scope_mode, 'COLLAB_SHARED') != 'PERSONAL_ONLY'
            """,
            (client_id, client_id),
        ),
        "evidenceCards": metric_map.get("evidenceCards", safe_count(conn, "SELECT COUNT(1) FROM evidence_cards WHERE client_id = ?", (client_id,))),
        "themeClusters": metric_map.get("themeClusters", safe_count(conn, "SELECT COUNT(1) FROM theme_clusters WHERE client_id = ?", (client_id,))),
        "openQuestions": metric_map.get("openQuestions", safe_count(conn, "SELECT COUNT(1) FROM open_questions WHERE client_id = ?", (client_id,))),
        "judgmentVersions": metric_map.get("judgments", safe_count(conn, "SELECT COUNT(1) FROM judgment_versions WHERE client_id = ?", (client_id,))),
    }
    return {
        "client": {
            "id": client_id,
            "name": str(client.get("name") or ""),
            "stage": str(client.get("stage") or ""),
            "intro": trim(client.get("intro"), 260),
        },
        "counts": counts,
        "currentRuleScoreForReference": {
            "assetStage": detail.assetStage,
            "assetTrackTitle": detail.assetTrackTitle,
            "stageProgress": detail.stageProgress,
            "depositXp": detail.depositXp,
        },
        "fileInventory": {
            "extensionsTop": ext_counts.most_common(12),
            "parseStatus": parse_counts.most_common(),
            "visibleCategoriesTop": category_counts.most_common(10),
            "keywordLabelCounts": label_counts.most_common(),
            "profileSignalCounts": profile_scores.most_common(),
            "labelExamples": {label: examples for label, examples in label_examples.items()},
            "highSignalMaterials": high_signal[:24],
        },
        "existingAssetNodes": asset_nodes,
        "evidenceExamples": [
            {
                "claim": trim(item.get("normalized_claim") or item.get("quote"), 220),
                "type": str(item.get("evidence_type") or ""),
                "quality": str(item.get("quality_tier") or ""),
            }
            for item in evidence_examples
        ],
        "judgmentExamples": [
            {
                "topic": str(item.get("topic") or ""),
                "summary": trim(item.get("summary"), 260),
                "quality": str(item.get("quality_tier") or ""),
            }
            for item in judgment_examples
        ],
        "eventExamples": [
            {
                "name": str(item.get("name") or ""),
                "stage": str(item.get("stage") or ""),
                "summary": trim(item.get("summary"), 260),
                "blocker": trim(item.get("current_blocker"), 160),
                "nextStep": trim(item.get("next_step"), 160),
                "evidenceCount": int(item.get("evidence_count") or 0),
            }
            for item in event_examples
        ],
    }


OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "clientName": {"type": "string"},
        "projectType": {"type": "string"},
        "secondaryTypes": {"type": "array", "items": {"type": "string"}},
        "whatFilesAreDoing": {"type": "array", "items": {"type": "string"}},
        "currentLevel": {
            "type": "object",
            "properties": {
                "level": {"type": "string"},
                "name": {"type": "string"},
                "reason": {"type": "string"},
            },
        },
        "scores": {
            "type": "object",
            "properties": {
                "depositThickness": {"type": "integer"},
                "structuralCompleteness": {"type": "integer"},
                "computability": {"type": "integer"},
                "evidenceChain": {"type": "integer"},
                "timeContinuity": {"type": "integer"},
                "resultFeedbackLoop": {"type": "integer"},
                "totalMaturity": {"type": "integer"},
            },
        },
        "scoreRationale": {"type": "array", "items": {"type": "string"}},
        "highValueMaterials": {"type": "array", "items": {"type": "string"}},
        "missingMaterials": {"type": "array", "items": {"type": "string"}},
        "nextGuidance": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "why": {"type": "string"},
                    "unlocks": {"type": "string"},
                },
            },
        },
        "scoreDisplay": {
            "type": "object",
            "properties": {
                "headline": {"type": "string"},
                "progressLine": {"type": "string"},
                "warning": {"type": "string"},
            },
        },
    },
}


def generate_for_client(ai: AiService, pack: dict[str, Any]) -> dict[str, Any]:
    system_instruction = (
        "你是益语智库的数据资产产品诊断模型。"
        "你要基于真实文件清单、资料类型、证据链和事件线，为一个客户/项目重新计算数字资产成熟度。"
        "不要按文件数量直接打高分；文件多只代表资料厚度。"
        "必须先判断项目类型，再按该类型真正需要的资料结构评分。"
        "所有分数都是0-100的整数，用来指导下一步沉淀动作，不是绝对客观评级。"
        "请使用普通业务语言，不要使用项目ID、字段口径、对象流程结果联动等抽象术语。"
    )
    prompt = (
        "请按下面的新评分系统重新计算。只返回一个 JSON 对象，不要 Markdown，不要解释，不要返回多个对象。\n\n"
        "评分系统：\n"
        "1. 先识别路径：组织战略陪伴型、公益项目运营型、研究报告/田野型、平台/行业生态型、产品/系统运营型、内容/IP资产型，可混合。\n"
        "2. 主路径只能选一个，辅路径最多选两个；不要因为资料里出现关键词就把所有路径都列上。\n"
        "3. 资料厚度 depositThickness：上传与沉淀努力，受文件量、来源量、事件/证据/判断影响，但不直接等于成熟。\n"
        "4. 结构完整度 structuralCompleteness：该类型项目的关键资料是否齐。\n"
        "5. 可计算度 computability：是否有表格、名单、时间、批次、状态、反馈、结果等可以比较的资料。\n"
        "6. 证据链强度 evidenceChain：是否从原始资料沉淀到证据、主题、问题、判断。\n"
        "7. 时间连续性 timeContinuity：是否能跨阶段、跨年度、跨批次观察变化。\n"
        "8. 结果反馈闭环 resultFeedbackLoop：是否能看见投入、过程、反馈、结果和复盘之间的关系。\n"
        "9. 总成熟度 totalMaturity = 结构完整度30% + 可计算度20% + 证据链15% + 时间连续性15% + 结果反馈闭环20%。资料厚度不进入总成熟度，只作为鼓励与解释。\n"
        "10. 等级：L1资料归档期、L2项目画像期、L3结构计算期、L4机制洞察期、L5机会生成期。允许偏科，但缺少可计算资料不能进入L4，缺少长期变化和机会信号不能进入L5。\n\n"
        "输出要求：\n"
        "- whatFilesAreDoing 要具体说明这些文件实际在做什么。\n"
        "- missingMaterials 必须是用户听得懂的资料缺口，比如“还缺能比较不同项目年度结果的资料”“还缺参与者反馈整理”“还缺年会参与机构变化记录”，不要写抽象字段词。\n"
        "- 少用“表、台账、验证表、补齐、底座、闭环”这些系统词，优先说清楚缺哪类真实资料。\n"
        "- nextGuidance 要告诉用户补什么、为什么、补完能解锁什么。\n"
        "- 分数必须拉开差异，不能因为都有几十上百个文件就相近。\n\n"
        f"真实资料包：\n{json.dumps(pack, ensure_ascii=False, default=str)}"
    )
    raw = ai._qwen_generate(  # type: ignore[attr-defined]
        prompt=prompt,
        system_instruction=system_instruction,
        response_schema=None,
        timeout_seconds=180.0,
        max_tokens=2600,
        temperature=0.18,
        top_p=0.86,
        enable_thinking=False,
    )
    if isinstance(raw, dict):
        return dict(raw)
    return parse_first_json_object(str(raw))


def parse_first_json_object(raw: str) -> dict[str, Any]:
    text = str(raw or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    if start < 0:
        return {"raw": text}
    decoder = json.JSONDecoder()
    try:
        value, _ = decoder.raw_decode(text[start:])
    except json.JSONDecodeError:
        end = text.rfind("}")
        if end <= start:
            return {"raw": text}
        value = json.loads(text[start : end + 1])
    return dict(value) if isinstance(value, dict) else {"raw": text}


def as_list(value: object) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        parts = re.split(r"[；;]\s*", text)
        return [part.strip() for part in parts if part.strip()] or [text]
    return [value]


def normalize_result(result: dict[str, Any], pack: dict[str, Any]) -> dict[str, Any]:
    scores = result.get("scores") if isinstance(result.get("scores"), dict) else {}
    if not scores:
        scores = {
            "depositThickness": result.get("depositThickness"),
            "structuralCompleteness": result.get("structuralCompleteness"),
            "computability": result.get("computability"),
            "evidenceChain": result.get("evidenceChain"),
            "timeContinuity": result.get("timeContinuity"),
            "resultFeedbackLoop": result.get("resultFeedbackLoop"),
            "totalMaturity": result.get("totalMaturity"),
        }
    current_level = result.get("currentLevel") if isinstance(result.get("currentLevel"), dict) else {}
    if not current_level:
        level_text = str(result.get("level") or "").strip()
        match = re.match(r"^(L\d)\s*(.*)$", level_text)
        current_level = {
            "level": match.group(1) if match else level_text,
            "name": match.group(2) if match else "",
            "reason": str(result.get("levelReason") or result.get("reason") or ""),
        }
    fallback_materials = [
        str(item.get("title") or "")
        for item in (pack.get("fileInventory", {}).get("highSignalMaterials", []) if isinstance(pack.get("fileInventory"), dict) else [])
        if isinstance(item, dict) and str(item.get("title") or "").strip()
    ][:6]
    return {
        **result,
        "clientName": str(result.get("clientName") or pack.get("client", {}).get("name") or ""),
        "projectType": str(result.get("projectType") or result.get("mainPath") or ""),
        "secondaryTypes": [str(item) for item in as_list(result.get("secondaryTypes") or result.get("auxiliaryPaths"))][:2],
        "whatFilesAreDoing": [str(item) for item in as_list(result.get("whatFilesAreDoing"))],
        "currentLevel": current_level,
        "scores": scores,
        "highValueMaterials": [str(item) for item in as_list(result.get("highValueMaterials"))] or fallback_materials,
        "missingMaterials": [str(item) for item in as_list(result.get("missingMaterials"))],
        "nextGuidance": as_list(result.get("nextGuidance")),
        "scoreDisplay": result.get("scoreDisplay") if isinstance(result.get("scoreDisplay"), dict) else {},
    }


def markdown_report(results: list[dict[str, Any]], packs: list[dict[str, Any]]) -> str:
    pack_by_name = {pack["client"]["name"]: pack for pack in packs}
    lines = [
        "# 数字资产中心：后端大模型重算实验",
        "",
        f"- 生成时间：{datetime.now().replace(microsecond=0).isoformat()}",
        "- 说明：本报告未写入正式接口，只用于校验新的类型化评分方法。",
        "- 口径：资料厚度只代表沉淀努力，不进入总成熟度；总成熟度由结构、可计算、证据链、连续性和结果反馈构成。",
        "",
    ]
    for result in results:
        name = str(result.get("clientName") or "")
        pack = pack_by_name.get(name, {})
        counts = pack.get("counts", {}) if isinstance(pack, dict) else {}
        scores = result.get("scores", {}) if isinstance(result.get("scores"), dict) else {}
        level = result.get("currentLevel", {}) if isinstance(result.get("currentLevel"), dict) else {}
        lines.extend(
            [
                f"## {name}",
                "",
                f"- 类型：{result.get('projectType', '')}；辅路径：{'、'.join(result.get('secondaryTypes') or [])}",
                f"- 等级：{level.get('level', '')} {level.get('name', '')}",
                f"- 判断：{level.get('reason', '')}",
                f"- 文件/沉淀：资料 {counts.get('documents', 0)}，记忆 {counts.get('memoryFacts', 0)}，证据卡 {counts.get('evidenceCards', 0)}，主题 {counts.get('themeClusters', 0)}，判断 {counts.get('judgmentVersions', 0)}，事件线 {counts.get('eventLines', 0)}",
                "",
                "| 指标 | 分数 |",
                "|---|---:|",
                f"| 资料厚度 | {scores.get('depositThickness', '')} |",
                f"| 结构完整度 | {scores.get('structuralCompleteness', '')} |",
                f"| 可计算度 | {scores.get('computability', '')} |",
                f"| 证据链强度 | {scores.get('evidenceChain', '')} |",
                f"| 时间连续性 | {scores.get('timeContinuity', '')} |",
                f"| 结果反馈闭环 | {scores.get('resultFeedbackLoop', '')} |",
                f"| 总成熟度 | {scores.get('totalMaturity', '')} |",
                "",
                "文件实际在做什么：",
            ]
        )
        for item in result.get("whatFilesAreDoing") or []:
            lines.append(f"- {item}")
        lines.append("")
        lines.append("高价值资料：")
        for item in result.get("highValueMaterials") or []:
            lines.append(f"- {item}")
        lines.append("")
        lines.append("还缺什么：")
        for item in result.get("missingMaterials") or []:
            lines.append(f"- {item}")
        lines.append("")
        lines.append("下一步指引：")
        for item in result.get("nextGuidance") or []:
            if isinstance(item, dict):
                lines.append(f"- {item.get('action', '')}：{item.get('why', '')}；解锁：{item.get('unlocks', '')}")
            else:
                lines.append(f"- {item}")
        lines.append("")
        display = result.get("scoreDisplay", {}) if isinstance(result.get("scoreDisplay"), dict) else {}
        if display:
            lines.extend(
                [
                    "页面展示建议：",
                    f"- {display.get('headline', '')}",
                    f"- {display.get('progressLine', '')}",
                    f"- {display.get('warning', '')}",
                    "",
                ]
            )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    db_path = Path(args.db)
    conn = sqlite3.connect(db_path)
    db = Database(db_path)
    ai = AiService(
        db,
        {
            "qwen": MacOSKeychainSecretStore("com.yiyu.self-workbench.qwen"),
            "doubao": MacOSKeychainSecretStore("com.yiyu.self-workbench.doubao"),
        },
    )
    health = ai.get_health()
    if not health.ready:
        raise RuntimeError(f"AI not ready: {health.detail}")

    clients = rows(
        conn,
        """
        SELECT id, name, stage, intro, updated_at
        FROM clients
        WHERE COALESCE(alias, '') != 'workspace-smoke'
          AND COALESCE(name, '') != '安装态冒烟客户'
        ORDER BY updated_at DESC
        """,
    )
    if args.limit:
        clients = clients[: args.limit]

    packs: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    for idx, client in enumerate(clients, start=1):
        name = str(client.get("name") or client.get("id"))
        print(f"[{idx}/{len(clients)}] building pack: {name}", flush=True)
        pack = build_client_pack(conn, db, client)
        packs.append(pack)
        print(f"[{idx}/{len(clients)}] calling backend LLM: {name}", flush=True)
        result = normalize_result(generate_for_client(ai, pack), pack)
        if not result.get("clientName"):
            result["clientName"] = name
        results.append(result)

    out_dir = Path(__file__).resolve().parent
    raw_path = out_dir / "llm_recalculated_scores.json"
    md_path = out_dir / "llm_recalculated_scores.md"
    raw_path.write_text(json.dumps({"health": {"provider": health.provider, "model": health.model}, "packs": packs, "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(markdown_report(results, packs), encoding="utf-8")
    print(f"wrote {raw_path}")
    print(f"wrote {md_path}")


if __name__ == "__main__":
    main()
