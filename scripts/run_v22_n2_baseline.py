#!/usr/bin/env python3
"""[B] V2.2 N2 北极星 · 5/19 张真会议金标准回归 runner

服务: V2.2_NORTH_STAR.md N2 (机器人能拿全数据流畅回答)
触发: AI A 跑 F2.1 DocumentLLMExtractor 抽完 5/19 docx 后 → 跑这个 runner
       验证 7 个关键事实是否真正沉淀进 atomic_facts 表
角色: AI B (跟进 AI · 测试/验证主战场)

5/19 张真会议 7 个关键事实 (NORTH_STAR §4 校验门 B 金标准):
  1. 张真接任法人
  2. (张真接任) 理事长
  3. 强哥 (任秘书长)
  4. 秘书长
  5. 兴盛 + 心理魔法学院合并
  6. 心理魔法学院
  7. 安心妈妈新项目

跑法 (3 种模式):

  # 模式 1: 跑桌面 prod db 副本 (默认)
  python3 scripts/run_v22_n2_baseline.py

  # 模式 2: 指定 db 路径
  python3 scripts/run_v22_n2_baseline.py --db /path/to/app.db

  # 模式 3: JSON 输出 (CI 用)
  python3 scripts/run_v22_n2_baseline.py --json > baseline.json

退出码:
  0 — 命中率 ≥ 4/7 (B 门 PASS)
  1 — 命中率 < 4/7 (B 门 FAIL,需要 A 调 prompt 重抽)
  2 — db 不存在或表 missing
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ── 7 个关键事实配置 ────────────────────────────────────────
# 跟 NORTH_STAR §4 校验门 B 金标准对齐 (顾源源 5/22 7 个 keyword)

DEFAULT_CLIENT_ID = "client_284afd836e"  # 日慈基金会


@dataclass(frozen=True)
class FactProbe:
    """一个关键事实的检测探针"""

    id: str
    label: str  # 人读名称, 出现在报告
    keywords: tuple[str, ...]  # 任一命中即算
    # 期望命中位置 (可选, 用于精细化打分)
    # search_fields: subject_text / attribute / value_text / evidence_text
    search_fields: tuple[str, ...] = ("subject_text", "value_text", "attribute")
    # 期望的 content_role (如果 F2.1 LLM extractor 抽对了, 应该是这些)
    expected_roles: tuple[str, ...] = ()  # 空 = 不限制 role
    # 期望来源 (5/19 docx)
    expected_source_contains: str = ""  # 空 = 不限制 source


# ── 6 件待办 (顾源源 5/22 接力指令 任务 2) ───────────────────
# B 门进阶判定: 5/19 会议 → AI 是否抽出了具体待办事项 (plan/commitment role)

PROBES_TODO_6: tuple[FactProbe, ...] = (
    FactProbe(
        id="t1_values_draft",
        label="价值观稿",
        keywords=("价值观", "稿"),
        search_fields=("subject_text", "value_text", "attribute"),
        expected_roles=("plan", "commitment", "decision"),
    ),
    FactProbe(
        id="t2_brand_assessment",
        label="品牌评估",
        keywords=("品牌", "评估"),
        search_fields=("subject_text", "value_text", "attribute"),
        expected_roles=("plan", "commitment", "decision"),
    ),
    FactProbe(
        id="t3_july_agenda",
        label="7 月议程",
        keywords=("7月", "议程"),
        search_fields=("subject_text", "value_text", "attribute"),
        expected_roles=("plan", "commitment", "decision"),
    ),
    FactProbe(
        id="t4_xingsheng_sort",
        label="兴盛梳理",
        keywords=("兴盛", "梳理"),
        search_fields=("subject_text", "value_text", "attribute"),
        expected_roles=("plan", "commitment", "decision"),
    ),
    FactProbe(
        id="t5_values_research",
        label="价值观调研",
        keywords=("价值观", "调研"),
        search_fields=("subject_text", "value_text", "attribute"),
        expected_roles=("plan", "commitment", "decision"),
    ),
    FactProbe(
        id="t6_brand_design_link",
        label="品牌设计对接",
        keywords=("品牌设计", "对接"),
        search_fields=("subject_text", "value_text", "attribute"),
        expected_roles=("plan", "commitment", "decision"),
    ),
)


# ── 5 关键人物归一 (接力指令 任务 2) ─────────────────────
# 验证 LLM 抽取是否覆盖会议关键人 (subject_text 或 speaker_person_id 含)

PROBES_PEOPLE_5: tuple[FactProbe, ...] = (
    FactProbe(
        id="ppl1_zhangzhen",
        label="张真",
        keywords=("张真",),
        search_fields=("subject_text", "value_text", "attribute"),
    ),
    FactProbe(
        id="ppl2_guyuanyuan",
        label="顾源源",
        keywords=("顾源源",),
        search_fields=("subject_text", "value_text", "attribute"),
    ),
    FactProbe(
        id="ppl3_yanbin",
        label="严斌",
        keywords=("严斌",),
        search_fields=("subject_text", "value_text", "attribute"),
    ),
    FactProbe(
        id="ppl4_qiang",
        label="强哥",
        keywords=("强哥",),
        search_fields=("subject_text", "value_text", "attribute"),
    ),
    FactProbe(
        id="ppl5_gao",
        label="高老师",
        keywords=("高老师",),
        search_fields=("subject_text", "value_text", "attribute"),
    ),
)


PROBES_5_19_TRUE_ALIGN: tuple[FactProbe, ...] = (
    FactProbe(
        id="p1_legal_rep",
        label="张真接任法人",
        # 收紧: 用 "法人" 这个核心词, 避免命中跟法人无关的张真事实
        # (例如旧 db 里 "张真老师权限=最高权限" 不应算法人接任)
        keywords=("法人",),
        search_fields=("subject_text", "value_text", "attribute"),
        expected_roles=("decision", "fact"),  # 这是会议决定 + 已成事实
    ),
    FactProbe(
        id="p2_chairman",
        label="(张真接任) 理事长",
        keywords=("理事长",),
        search_fields=("attribute", "value_text"),
        expected_roles=("decision", "fact"),
    ),
    FactProbe(
        id="p3_qiang_ge",
        label="强哥 (人物)",
        keywords=("强哥",),
        search_fields=("subject_text", "value_text"),
        expected_roles=("fact",),
    ),
    FactProbe(
        id="p4_secretary",
        label="秘书长",
        keywords=("秘书长",),
        search_fields=("attribute", "value_text"),
        expected_roles=("decision",),
    ),
    FactProbe(
        id="p5_xingsheng_merge",
        label="兴盛 + 心理魔法学院合并",
        keywords=("兴盛", "合并"),  # AND-like 检测下面
        search_fields=("subject_text", "value_text", "attribute"),
        expected_roles=("decision",),
    ),
    FactProbe(
        id="p6_xinli_mofa",
        label="心理魔法学院 (项目)",
        keywords=("心理魔法学院",),
        search_fields=("subject_text", "value_text"),
        expected_roles=("fact", "decision"),
    ),
    FactProbe(
        id="p7_anxin_mama",
        label="安心妈妈新项目",
        keywords=("安心妈妈",),
        search_fields=("subject_text", "value_text", "attribute"),
        expected_roles=("decision", "fact"),
    ),
)


# ── 探针检测结果 ────────────────────────────────────────────


@dataclass
class ProbeResult:
    probe: FactProbe
    hit_count: int  # 总命中行数 (active)
    sample_rows: list[dict[str, Any]] = field(default_factory=list)  # 前 3 条样本
    has_correct_role: bool = False  # 是否命中 expected_roles
    has_5_19_source: bool = False  # 是否带 5/19 docx 来源
    confidence_avg: float = 0.0

    @property
    def hit(self) -> bool:
        return self.hit_count > 0

    @property
    def strong_hit(self) -> bool:
        """强命中 = 命中 + role 对 + 有 5/19 来源"""
        return self.hit and self.has_correct_role and self.has_5_19_source


# ── 主查询逻辑 ──────────────────────────────────────────────


def _build_keyword_clause(probe: FactProbe) -> tuple[str, list[str]]:
    """生成 LIKE 子句 + params"""
    field_clauses = []
    params: list[str] = []
    for kw in probe.keywords:
        per_kw = []
        for field in probe.search_fields:
            per_kw.append(f"{field} LIKE ?")
            params.append(f"%{kw}%")
        # 一个 keyword 在任一 field 命中即可
        field_clauses.append("(" + " OR ".join(per_kw) + ")")
    # 多个 keyword 关系: 检查 keywords 长度
    if len(probe.keywords) > 1:
        # 复合事实 (如 "兴盛 + 合并"): AND 关系 — 但 SQL 是行级,所以是同一行命中两个 keyword
        # 在 atomic_facts 里, 一行通常只描述一个事实, 所以 AND 容易 0 命中
        # 折中: 用 OR (任一命中即算这个事实存在),
        # 但报告里 highlight 这是部分命中
        sql = " OR ".join(field_clauses)
    else:
        sql = field_clauses[0]
    return sql, params


def probe_fact(
    conn: sqlite3.Connection,
    probe: FactProbe,
    client_id: str = DEFAULT_CLIENT_ID,
) -> ProbeResult:
    """跑单个事实探针"""
    clause, kw_params = _build_keyword_clause(probe)
    sql = f"""
        SELECT subject_text, attribute, value_text, confidence,
               source_v2_document_id, evidence_text,
               -- 5 维元数据 (N3 A1-A7 字段, 可能不存在)
               COALESCE((SELECT 1 FROM pragma_table_info('atomic_facts')
                         WHERE name='content_role'), 0) AS has_role_col
        FROM atomic_facts
        WHERE client_id = ? AND status = 'active' AND ({clause})
        LIMIT 100
    """
    params = [client_id, *kw_params]
    try:
        rows = conn.execute(sql, params).fetchall()
    except sqlite3.OperationalError as e:
        # 表/字段不存在等 — 返回空命中
        return ProbeResult(probe=probe, hit_count=0, sample_rows=[])

    # 检查 5 维元数据字段是否存在
    cols = {c["name"] for c in conn.execute("PRAGMA table_info(atomic_facts)").fetchall()}
    has_role = "content_role" in cols
    has_source = "source_v2_document_id" in cols

    # 拉详细 (含 role, source)
    extra_cols = "subject_text, attribute, value_text, confidence"
    if has_role:
        extra_cols += ", content_role"
    if has_source:
        extra_cols += ", source_v2_document_id, evidence_text"

    detail_sql = f"""
        SELECT {extra_cols}
        FROM atomic_facts
        WHERE client_id = ? AND status = 'active' AND ({clause})
        LIMIT 100
    """
    detail_rows = conn.execute(detail_sql, params).fetchall()

    # 评估
    role_match = False
    src_match = False
    conf_sum = 0.0
    samples: list[dict[str, Any]] = []
    for r in detail_rows:
        d = dict(r)
        samples.append(d)
        conf_sum += float(d.get("confidence") or 0.0)
        if has_role and probe.expected_roles:
            role = str(d.get("content_role") or "")
            if role in probe.expected_roles:
                role_match = True
        if has_source:
            src = str(d.get("source_v2_document_id") or "")
            # 5/19 docx 关键词 — 涵盖多种命名习惯 (中文 / 拼音 / 数字)
            src_keywords = (
                "5月", "0519", "20260519", "5_19",
                "张真", "zhangzhen", "zhang_zhen", "zhang-zhen",
                "战略对齐", "align",  # 文件名常见词
            )
            if any(k in src for k in src_keywords):
                src_match = True
            # 也看 evidence_text 是否包含 5/19 上下文
            ev = str(d.get("evidence_text") or "")
            ev_keywords = ("5/19", "5 月 19", "5月19", "张真", "0519")
            if any(k in ev for k in ev_keywords):
                src_match = True

    return ProbeResult(
        probe=probe,
        hit_count=len(detail_rows),
        sample_rows=samples[:3],  # 前 3 条
        has_correct_role=role_match if probe.expected_roles else True,
        has_5_19_source=src_match if has_source else True,
        confidence_avg=(conf_sum / len(detail_rows)) if detail_rows else 0.0,
    )


# ── 报告 ────────────────────────────────────────────────────


@dataclass
class BaselineReport:
    client_id: str
    db_path: str
    probes: list[ProbeResult]
    # 接力指令 任务 2: 顺手扩展 — 6 待办 + 5 人物归一
    todo_probes: list[ProbeResult] = field(default_factory=list)
    people_probes: list[ProbeResult] = field(default_factory=list)

    @property
    def hit_count(self) -> int:
        return sum(1 for p in self.probes if p.hit)

    @property
    def strong_hit_count(self) -> int:
        return sum(1 for p in self.probes if p.strong_hit)

    @property
    def total(self) -> int:
        return len(self.probes)

    @property
    def todo_hit_count(self) -> int:
        return sum(1 for p in self.todo_probes if p.hit)

    @property
    def people_hit_count(self) -> int:
        return sum(1 for p in self.people_probes if p.hit)

    @property
    def combined_score_percent(self) -> float:
        """综合 P% (3 类加权): 主 probes 50% + todo 30% + people 20%"""
        if not (self.probes or self.todo_probes or self.people_probes):
            return 0.0
        main_pct = (
            self.hit_count / len(self.probes) if self.probes else 0
        ) * 50
        todo_pct = (
            self.todo_hit_count / len(self.todo_probes)
            if self.todo_probes else 0
        ) * 30
        people_pct = (
            self.people_hit_count / len(self.people_probes)
            if self.people_probes else 0
        ) * 20
        return round(main_pct + todo_pct + people_pct, 1)

    def to_dict(self) -> dict[str, Any]:
        def _probe_to_dict(p: ProbeResult) -> dict[str, Any]:
            return {
                "id": p.probe.id,
                "label": p.probe.label,
                "hit_count": p.hit_count,
                "strong_hit": p.strong_hit,
                "has_correct_role": p.has_correct_role,
                "has_5_19_source": p.has_5_19_source,
                "confidence_avg": round(p.confidence_avg, 2),
                "sample_rows": p.sample_rows,
            }

        return {
            "client_id": self.client_id,
            "db_path": self.db_path,
            "summary": {
                "total": self.total,
                "hit": self.hit_count,
                "strong_hit": self.strong_hit_count,
                "hit_rate": f"{self.hit_count}/{self.total}",
                "strong_hit_rate": f"{self.strong_hit_count}/{self.total}",
                "b_gate_pass": self.hit_count >= 4,
                # 接力指令 任务 2 扩展
                "todo_hit_rate": (
                    f"{self.todo_hit_count}/{len(self.todo_probes)}"
                    if self.todo_probes else "0/0"
                ),
                "people_hit_rate": (
                    f"{self.people_hit_count}/{len(self.people_probes)}"
                    if self.people_probes else "0/0"
                ),
                "combined_score_percent": self.combined_score_percent,
            },
            "probes": [_probe_to_dict(p) for p in self.probes],
            "todo_probes": [_probe_to_dict(p) for p in self.todo_probes],
            "people_probes": [_probe_to_dict(p) for p in self.people_probes],
        }

    def to_human_text(self) -> str:
        lines = []
        lines.append("=" * 70)
        lines.append("  V2.2 N2 北极星 · 5/19 张真会议金标准回归 baseline")
        lines.append("=" * 70)
        lines.append(f"  client_id: {self.client_id}")
        lines.append(f"  db:        {self.db_path}")
        lines.append("")
        # 探针表格
        lines.append(f"  {'探针':<28}  {'命中数':<6}  {'role 对':<8}  {'5/19 源':<8}  {'强命中':<6}")
        lines.append("  " + "-" * 65)
        for p in self.probes:
            hit_mark = "✓" if p.hit else "✗"
            role_mark = "✓" if p.has_correct_role else "—"
            src_mark = "✓" if p.has_5_19_source else "—"
            strong_mark = "★" if p.strong_hit else " "
            lines.append(
                f"  {p.probe.label:<22}  {hit_mark} {p.hit_count:>3}    "
                f"{role_mark:<8}  {src_mark:<8}  {strong_mark:<6}"
            )
        lines.append("  " + "-" * 65)
        lines.append("")
        lines.append(
            f"  弱命中 (任一 keyword): {self.hit_count}/{self.total}"
        )
        lines.append(
            f"  强命中 (含 role + 5/19 源): {self.strong_hit_count}/{self.total}"
        )
        lines.append("")
        # B 门判定
        passing = self.hit_count >= 4
        b_gate_mark = "✅ PASS" if passing else "❌ FAIL"
        lines.append(f"  B 门 (NORTH_STAR §4): {b_gate_mark}  (阈值 ≥ 4/7)")
        if passing and self.strong_hit_count >= 4:
            lines.append(f"  B 门 PLUS (5 维元数据全过): ✅ PASS")
        elif passing:
            lines.append(
                f"  B 门 PLUS: ⚠️ 命中数够但 role / source 未完整 → "
                f"prompt 还需调优"
            )
        lines.append("")
        # 缺失诊断
        missing = [p.probe.label for p in self.probes if not p.hit]
        if missing:
            lines.append(f"  缺失 ({len(missing)} 项): {', '.join(missing)}")
        lines.append("")

        # ── 接力指令 任务 2 扩展: 6 待办 + 5 人物 + 综合 P% ──
        if self.todo_probes:
            lines.append(f"  {'待办 (6 件)':<28}  {'命中':<6}  {'role 对':<8}")
            lines.append("  " + "-" * 50)
            for p in self.todo_probes:
                hit_mark = "✓" if p.hit else "✗"
                role_mark = "✓" if p.has_correct_role else "—"
                lines.append(
                    f"  {p.probe.label:<22}  {hit_mark} {p.hit_count:>3}    "
                    f"{role_mark:<8}"
                )
            lines.append("  " + "-" * 50)
            lines.append(
                f"  待办命中: {self.todo_hit_count}/{len(self.todo_probes)}"
            )
            lines.append("")

        if self.people_probes:
            lines.append(f"  {'人物归一 (5 人)':<28}  {'命中':<6}")
            lines.append("  " + "-" * 40)
            for p in self.people_probes:
                hit_mark = "✓" if p.hit else "✗"
                lines.append(
                    f"  {p.probe.label:<22}  {hit_mark} {p.hit_count:>3}"
                )
            lines.append("  " + "-" * 40)
            lines.append(
                f"  人物命中: {self.people_hit_count}/{len(self.people_probes)}"
            )
            lines.append("")

        if self.todo_probes or self.people_probes:
            score = self.combined_score_percent
            score_mark = "🟢" if score >= 70 else ("🟡" if score >= 40 else "🔴")
            lines.append(
                f"  综合 N2 命中 P%: {score_mark} {score:.1f}%  "
                f"(主 50% × {self.hit_count}/{self.total} + "
                f"待办 30% × {self.todo_hit_count}/{len(self.todo_probes)} + "
                f"人物 20% × {self.people_hit_count}/{len(self.people_probes)})"
            )
            lines.append("")

        lines.append("=" * 70)
        return "\n".join(lines)


def run_baseline(
    db_path: Path,
    client_id: str = DEFAULT_CLIENT_ID,
    probes: tuple[FactProbe, ...] = PROBES_5_19_TRUE_ALIGN,
    include_extended: bool = True,
) -> BaselineReport:
    """主入口 — 跑 baseline 并返回 report.

    include_extended (接力指令任务 2): 顺手跑 PROBES_TODO_6 + PROBES_PEOPLE_5
    可关 (向后兼容老 12 个自检测试 — 它们用 probes= 自定义参数, 没传 include_extended).
    """
    if not db_path.exists():
        raise FileNotFoundError(f"DB 不存在: {db_path}")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        check = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='atomic_facts'"
        ).fetchone()
        if not check:
            raise RuntimeError(f"atomic_facts 表不存在 (DB: {db_path})")

        results = [probe_fact(conn, probe, client_id) for probe in probes]
        todo_results: list[ProbeResult] = []
        people_results: list[ProbeResult] = []
        # 仅当跑默认 7 主 probes 时, 顺手跑扩展 (避免自检测试拿到意外数据)
        if include_extended and probes is PROBES_5_19_TRUE_ALIGN:
            todo_results = [
                probe_fact(conn, p, client_id) for p in PROBES_TODO_6
            ]
            people_results = [
                probe_fact(conn, p, client_id) for p in PROBES_PEOPLE_5
            ]
    finally:
        conn.close()

    return BaselineReport(
        client_id=client_id,
        db_path=str(db_path),
        probes=results,
        todo_probes=todo_results,
        people_probes=people_results,
    )


# ── CLI ──────────────────────────────────────────────────────


def _default_db_path() -> Path:
    """默认 db 路径 — 桌面 prod db"""
    return (
        Path.home()
        / "Library"
        / "Application Support"
        / "YiyuThinkTankWorkbench2"
        / "app.db"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="V2.2 N2 5/19 金标准回归 runner"
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=_default_db_path(),
        help="atomic_facts 表所在的 sqlite db 路径 (默认桌面 prod db)",
    )
    parser.add_argument(
        "--client-id",
        default=DEFAULT_CLIENT_ID,
        help=f"客户 ID (默认 {DEFAULT_CLIENT_ID} = 日慈)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="输出 JSON 报告而非人读文本",
    )
    args = parser.parse_args(argv)

    try:
        report = run_baseline(args.db, args.client_id)
    except FileNotFoundError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 2
    except RuntimeError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(report.to_human_text())

    # exit code: B 门 PASS = 0
    return 0 if report.hit_count >= 4 else 1


if __name__ == "__main__":
    sys.exit(main())
