"""[A] V2.6 R3-M1 · FileIdentityClassifier + ContractStructureParser

用户甲 5/23 钦定 R3 优先级 1:
> 系统必须从"文件导入"升级为"文件身份判定 + 合同结构理解 + 项目关系归属".

每份文件至少要识别:
  · 文件类型 (合同/协议/方案/会议纪要/年报/政策/对标/预算)
  · 文件角色 (客户官方/我方产出/外部参考/合作方提交/政策依据)
  · 适用客户 / 适用项目
  · 文件版本 / 文件时间 / 文件主体
  · 是否权威 / 是否仅参考
  · 是否与已有材料冲突
  · 是否产生新事实/承诺/风险/任务/澄清

合同类文件追加识别合同结构:
  · 合同类型 / 甲乙方 / 项目名称 / 签署时间 / 有效期 / 金额
  · 交付内容 / 双方责任 / 版本关系 / 关联项目

LLM: 本地 ollama qwen2.5:14b
"""
from __future__ import annotations

import json
import logging
import re
import urllib.request
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Protocol

logger = logging.getLogger(__name__)


class _DbLike(Protocol):
    def execute(self, sql: str, params: tuple = ...) -> Any: ...
    def fetchone(self, sql: str, params: tuple = ...) -> Any: ...
    def fetchall(self, sql: str, params: tuple = ...) -> Any: ...


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:14b"

FileType = Literal[
    "contract", "supplementary_agreement", "proposal", "meeting_minute",
    "annual_report", "policy", "benchmark_case", "budget_table",
    "feedback_doc", "publicity_doc", "other",
]

FileRole = Literal[
    "client_official", "yiyu_produced", "external_reference",
    "collaborator_submitted", "policy_basis", "unknown",
]


# ─── 文件身份分类 ────────────────────────────────────


@dataclass
class FileIdentity:
    file_name: str
    file_type: str = "other"
    file_role: str = "unknown"
    client_id: str | None = None
    client_name: str | None = None
    project_name: str | None = None
    version: str | None = None
    file_time: str | None = None  # ISO date
    main_subject: str | None = None
    is_authoritative: bool = False
    is_external_only: bool = False
    confidence: float = 0.5
    raw_extracted: dict = field(default_factory=dict)


_FILE_NAME_HINTS = {
    "contract": ["合同", "正式合同", "协议（不含补充）"],
    "supplementary_agreement": ["补充协议", "补充合同", "附件协议"],
    "proposal": ["方案", "试点方案", "项目方案"],
    "meeting_minute": ["会议纪要", "纪要", "会议记录"],
    "annual_report": ["年报", "年度报告", "年度总结"],
    "policy": ["政策", "通知", "管理办法", "条例"],
    "benchmark_case": ["对标", "案例", "标杆"],
    "budget_table": ["预算表", "费用表", "财务表"],
    "feedback_doc": ["反馈", "意见", "建议"],
    "publicity_doc": ["宣传", "对外稿", "宣传稿"],
}


def classify_by_filename(file_name: str) -> tuple[str, float]:
    """规则: 从文件名启发判文件类型. 返回 (type, confidence)."""
    fn = file_name.lower()
    for ft, hints in _FILE_NAME_HINTS.items():
        for h in hints:
            if h in file_name or h.lower() in fn:
                return ft, 0.7
    return "other", 0.3


# ─── 合同结构解析 ────────────────────────────────────


@dataclass
class ContractStructure:
    contract_type: str  # "service_agreement" / "supplementary" / "memorandum" / ...
    party_a: str | None = None
    party_b: str | None = None
    project_name: str | None = None
    signed_at: str | None = None
    effective_period: str | None = None
    amount: str | None = None
    deliverables: list[str] = field(default_factory=list)
    responsibilities: dict[str, str] = field(default_factory=dict)  # party → resp
    version: str | None = None
    supersedes: str | None = None  # 老合同 id (如果是补充协议)
    related_project_id: str | None = None
    confidence: float = 0.5
    raw_extracted: dict = field(default_factory=dict)


def _call_ollama(prompt: str, timeout: float = 90, max_tokens: int = 2000) -> str:
    data = json.dumps({
        "model": MODEL, "prompt": prompt, "stream": False,
        "options": {"temperature": 0.1, "num_predict": max_tokens},
    }).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_URL, data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8")).get("response", "")
    except Exception as exc:
        return f"__ERROR__: {exc}"


def _parse_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text.strip())
    s, e = text.find("{"), text.rfind("}")
    if s < 0 or e <= s:
        return {}
    try:
        return json.loads(text[s:e + 1])
    except json.JSONDecodeError:
        return {}


_IDENTITY_PROMPT_TEMPLATE = """你是一个文件身份判定助手. 给你一个文件名和原文内容片段, 判定它的身份.

文件名: {file_name}
原文片段:
{text}

请输出 JSON:
{{
  "file_type": "contract | supplementary_agreement | proposal | meeting_minute | annual_report | policy | benchmark_case | budget_table | feedback_doc | publicity_doc | other",
  "file_role": "client_official | yiyu_produced | external_reference | collaborator_submitted | policy_basis | unknown",
  "client_name": "若能从文件内推断客户名, 否则 null",
  "project_name": "若能推断项目名, 否则 null",
  "version": "v1/v2/初版/修订版/null",
  "file_time": "ISO 日期或原文日期, 否则 null",
  "main_subject": "文件主体一句话",
  "is_authoritative": true|false,
  "is_external_only": true|false,
  "confidence": 0.0-1.0
}}

file_role 判定规则 (非常重要, 用户甲 5/23 R3 钦定):
  · client_official    — 客户(甲方)与益语(乙方)双方签字的合同/协议/补充协议, 客户自己出的方案/年报/章程/预算表/宣传稿, 客户内部会议纪要
  · yiyu_produced      — 益语单方产出的反馈意见/咨询建议/我方备忘录 (不是双方签的)
  · external_reference — 对标案例, 行业研究, 跟本客户无直接关系的外部文献
  · collaborator_submitted — 合作伙伴/供应商单方提交的材料 (例: 学校自报)
  · policy_basis       — 政府/部委/政策文件 (教育部通知/法规)
  · unknown            — 真判断不了

关键反例:
  · 'A组织-益语-战略陪伴合同' → file_role=client_official (双方签字合同, 不是益语产出)
  · 'A组织-心盛计划补充协议' → file_role=client_official (双方签字)
  · '益语-关于心盛计划扩张节奏的反馈' → file_role=yiyu_produced (益语单方反馈)
  · '教育部-某通知' → file_role=policy_basis
  · '对标-某基金会案例' → file_role=external_reference

直接输出 JSON, 不要解释."""


_CONTRACT_PROMPT_TEMPLATE = """你是一个合同结构解析助手. 给你一份合同文件的原文, 抽取关键结构.

文件名: {file_name}
原文:
{text}

请输出 JSON:
{{
  "contract_type": "service_agreement | supplementary | memorandum | partnership | other",
  "party_a": "甲方名称",
  "party_b": "乙方名称",
  "project_name": "项目名 (合同标的)",
  "signed_at": "签署时间 (ISO 或原文)",
  "effective_period": "有效期描述",
  "amount": "金额 (含币种和单位)",
  "deliverables": ["交付内容 1", "交付内容 2"],
  "responsibilities": {{"甲方": "责任描述", "乙方": "责任描述"}},
  "version": "v1/v2/初版/补充协议等",
  "supersedes": "如果是补充协议, 关联的主合同名/null",
  "related_project_name": "关联项目名",
  "confidence": 0.0-1.0
}}

直接输出 JSON, 不要解释."""


def classify_file_identity(
    file_name: str, text_excerpt: str, *,
    use_llm: bool = True,
) -> FileIdentity:
    """识别文件身份."""
    # 规则: 文件名启发
    rule_type, rule_conf = classify_by_filename(file_name)
    ident = FileIdentity(file_name=file_name, file_type=rule_type, confidence=rule_conf)

    if not use_llm or not text_excerpt:
        return ident

    # LLM 进一步
    prompt = _IDENTITY_PROMPT_TEMPLATE.format(
        file_name=file_name, text=text_excerpt[:3000],
    )
    raw = _call_ollama(prompt, timeout=60, max_tokens=600)
    if raw.startswith("__ERROR__"):
        return ident
    parsed = _parse_json(raw)
    if not parsed:
        return ident

    return FileIdentity(
        file_name=file_name,
        file_type=parsed.get("file_type", rule_type) or rule_type,
        file_role=parsed.get("file_role", "unknown") or "unknown",
        client_id=None,
        client_name=parsed.get("client_name"),
        project_name=parsed.get("project_name"),
        version=parsed.get("version"),
        file_time=parsed.get("file_time"),
        main_subject=parsed.get("main_subject"),
        is_authoritative=bool(parsed.get("is_authoritative", False)),
        is_external_only=bool(parsed.get("is_external_only", False)),
        confidence=float(parsed.get("confidence", rule_conf)),
        raw_extracted=parsed,
    )


def parse_contract_structure(
    file_name: str, text: str, *,
    use_llm: bool = True,
) -> ContractStructure | None:
    """合同类文件 → 合同结构. 非合同返回 None."""
    if not use_llm or not text:
        return None
    prompt = _CONTRACT_PROMPT_TEMPLATE.format(file_name=file_name, text=text[:5000])
    raw = _call_ollama(prompt, timeout=90, max_tokens=1200)
    if raw.startswith("__ERROR__"):
        return None
    parsed = _parse_json(raw)
    if not parsed:
        return None

    return ContractStructure(
        contract_type=parsed.get("contract_type", "other") or "other",
        party_a=parsed.get("party_a"),
        party_b=parsed.get("party_b"),
        project_name=parsed.get("project_name"),
        signed_at=parsed.get("signed_at"),
        effective_period=parsed.get("effective_period"),
        amount=parsed.get("amount"),
        deliverables=parsed.get("deliverables") or [],
        responsibilities=parsed.get("responsibilities") or {},
        version=parsed.get("version"),
        supersedes=parsed.get("supersedes"),
        confidence=float(parsed.get("confidence", 0.5)),
        raw_extracted=parsed,
    )


# ─── schema ensure ─────────────────────────────────────


def ensure_file_identity_schema(db: _DbLike) -> None:
    """V2.6 R3-M1 加 file_identities + contract_structures 表."""
    for sql in [
        """CREATE TABLE IF NOT EXISTS file_identities (
            id TEXT PRIMARY KEY,
            client_id TEXT,
            file_name TEXT NOT NULL,
            file_path TEXT,
            v2_document_id TEXT,
            file_type TEXT NOT NULL DEFAULT 'other',
            file_role TEXT NOT NULL DEFAULT 'unknown',
            project_name TEXT,
            version TEXT,
            file_time TEXT,
            main_subject TEXT,
            is_authoritative INTEGER NOT NULL DEFAULT 0,
            is_external_only INTEGER NOT NULL DEFAULT 0,
            confidence REAL NOT NULL DEFAULT 0.5,
            raw_extracted_json TEXT NOT NULL DEFAULT '{}',
            classified_at TEXT NOT NULL,
            classifier_version TEXT DEFAULT 'r3-m1-v1'
        )""",
        """CREATE INDEX IF NOT EXISTS idx_file_identities_client
           ON file_identities(client_id, file_type, classified_at DESC)""",
        """CREATE TABLE IF NOT EXISTS contract_structures (
            id TEXT PRIMARY KEY,
            client_id TEXT,
            file_identity_id TEXT,
            contract_type TEXT NOT NULL,
            party_a TEXT,
            party_b TEXT,
            project_name TEXT,
            signed_at TEXT,
            effective_period TEXT,
            amount TEXT,
            deliverables_json TEXT NOT NULL DEFAULT '[]',
            responsibilities_json TEXT NOT NULL DEFAULT '{}',
            version TEXT,
            supersedes_contract_id TEXT,
            related_project_id TEXT,
            confidence REAL NOT NULL DEFAULT 0.5,
            raw_extracted_json TEXT NOT NULL DEFAULT '{}',
            parsed_at TEXT NOT NULL
        )""",
        """CREATE INDEX IF NOT EXISTS idx_contract_structures_client
           ON contract_structures(client_id, signed_at DESC)""",
    ]:
        try:
            db.execute(sql)
        except Exception as exc:
            logger.warning("ensure_file_identity_schema sql failed: %s", exc)


def record_file_identity(
    db: _DbLike, identity: FileIdentity, *,
    client_id: str | None = None, v2_document_id: str | None = None,
    file_path: str | None = None,
) -> str:
    """持久化文件身份."""
    ensure_file_identity_schema(db)
    fid = f"fid_{uuid.uuid4().hex[:24]}"
    db.execute(
        """INSERT INTO file_identities (
            id, client_id, file_name, file_path, v2_document_id,
            file_type, file_role, project_name, version, file_time,
            main_subject, is_authoritative, is_external_only, confidence,
            raw_extracted_json, classified_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            fid, client_id, identity.file_name, file_path, v2_document_id,
            identity.file_type, identity.file_role, identity.project_name,
            identity.version, identity.file_time, identity.main_subject,
            1 if identity.is_authoritative else 0,
            1 if identity.is_external_only else 0,
            identity.confidence,
            json.dumps(identity.raw_extracted, ensure_ascii=False),
            _now_iso(),
        ),
    )
    return fid


def record_contract_structure(
    db: _DbLike, contract: ContractStructure, *,
    client_id: str | None = None, file_identity_id: str | None = None,
) -> str:
    """持久化合同结构."""
    ensure_file_identity_schema(db)
    cid = f"cs_{uuid.uuid4().hex[:24]}"
    db.execute(
        """INSERT INTO contract_structures (
            id, client_id, file_identity_id, contract_type,
            party_a, party_b, project_name, signed_at, effective_period,
            amount, deliverables_json, responsibilities_json,
            version, supersedes_contract_id, related_project_id,
            confidence, raw_extracted_json, parsed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            cid, client_id, file_identity_id, contract.contract_type,
            contract.party_a, contract.party_b, contract.project_name,
            contract.signed_at, contract.effective_period, contract.amount,
            json.dumps(contract.deliverables, ensure_ascii=False),
            json.dumps(contract.responsibilities, ensure_ascii=False),
            contract.version, contract.supersedes, None,
            contract.confidence,
            json.dumps(contract.raw_extracted, ensure_ascii=False),
            _now_iso(),
        ),
    )
    return cid


def batch_classify_files(
    db: _DbLike, *,
    client_id: str,
    files: list[dict],  # [{file_name, text_excerpt, file_path?, v2_document_id?}]
    use_llm: bool = True,
) -> dict:
    """批量处理一批文件 (例: 20 文件场景), 返回统计."""
    stats = {
        "total": len(files),
        "classified": 0,
        "contracts_parsed": 0,
        "by_type": {},
        "by_role": {},
        "errors": [],
        "identities": [],
        "contracts": [],
    }
    for f in files:
        try:
            ident = classify_file_identity(
                f["file_name"], f.get("text_excerpt", ""), use_llm=use_llm,
            )
            fid_id = record_file_identity(
                db, ident, client_id=client_id,
                v2_document_id=f.get("v2_document_id"),
                file_path=f.get("file_path"),
            )
            stats["classified"] += 1
            stats["by_type"][ident.file_type] = stats["by_type"].get(ident.file_type, 0) + 1
            stats["by_role"][ident.file_role] = stats["by_role"].get(ident.file_role, 0) + 1
            stats["identities"].append({
                "id": fid_id, "name": ident.file_name,
                "type": ident.file_type, "role": ident.file_role,
                "project": ident.project_name, "version": ident.version,
                "confidence": ident.confidence,
            })

            # 如果是合同, 进一步解析结构
            if ident.file_type in ("contract", "supplementary_agreement") and use_llm:
                contract = parse_contract_structure(
                    f["file_name"], f.get("text_excerpt", ""), use_llm=True,
                )
                if contract:
                    cs_id = record_contract_structure(
                        db, contract, client_id=client_id, file_identity_id=fid_id,
                    )
                    stats["contracts_parsed"] += 1
                    stats["contracts"].append({
                        "id": cs_id, "file": ident.file_name,
                        "type": contract.contract_type,
                        "party_a": contract.party_a, "party_b": contract.party_b,
                        "project": contract.project_name,
                        "amount": contract.amount, "signed_at": contract.signed_at,
                        "version": contract.version,
                    })
        except Exception as exc:
            stats["errors"].append({"file": f.get("file_name"), "error": str(exc)[:200]})
    return stats
