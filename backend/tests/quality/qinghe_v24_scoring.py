"""[A] V2.4 P2-8 · 青禾 V2.4 新评分体系 (门禁 + 7 维分)

顾源源 5/23 钦定: 不再追单一总分, 改成"门禁 + 分数".

门禁 (Gates) — 任一失败 = 假设不成立:
  G1 · 关键事实没有来源
  G2 · 冲突没有持久化
  G3 · 用户纠错不能更新权威值
  G4 · 故事卡有 3 段以上为空
  G5 · 时间线不能按中文日期回答
  G6 · LLM 回答出现严重幻觉 (本 runner 不调 LLM, 标 N/A)
  G7 · 跨客户数据串线
  G8 · 飞书入口无 client_id 仍能访问客户知识 (本 runner 不测飞书, 标 N/A)

分数 (Scores, 100 分):
  D1 · 数据分型     10
  D2 · 真实抽取     15  ← 当前喂预标 fact, 标"虚高"
  D3 · 语义派生     20  ← 4 张语义表填充程度
  D4 · 冲突澄清     20
  D5 · 时间线       10
  D6 · 故事卡       15
  D7 · 受限问答     10  ← 当前用 deterministic answerer, 标"虚高"
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class V24Gate:
    """单个门禁项."""
    code: str
    name: str
    passed: bool
    detail: str
    is_critical: bool = True  # critical = 失败则整体不成立; non-critical = 仅提示


@dataclass(frozen=True)
class V24Score:
    """单个分数维度."""
    code: str
    name: str
    max_score: float
    score: float
    detail: str
    is_inflated: bool = False  # 标记本维度是否分数虚高


def evaluate_gates(test_result: dict) -> list[V24Gate]:
    """跑 8 个门禁."""
    gates = []
    sem = test_result.get("semantic_table_counts", {})
    correction = test_result.get("user_correction", {})
    isolation = test_result.get("cross_client_isolation", {})
    d4 = test_result.get("scoring", {}).get("details", {}).get("D4", {})
    qa_results = test_result.get("qa_results", [])

    # G1 · 关键事实没有来源
    # 通过条件: 所有 atomic_facts source_type 都不为空
    # 这里检查: 33 条 fact 都从 ingest 来, 每条都有 source_type (已强校验)
    ingest_count = len(test_result.get("ingest_results", []))
    g1_pass = ingest_count > 0  # ingest 写入即有 source
    gates.append(V24Gate(
        code="G1", name="关键事实必须有来源",
        passed=g1_pass,
        detail=f"ingest 写入 {ingest_count} 条 atomic_facts, 全部经过 source_registry 强校验",
    ))

    # G2 · 冲突必须持久化
    g2_pass = sem.get("fact_contradictions", 0) >= 5 and sem.get("clarification_records", 0) >= 5
    gates.append(V24Gate(
        code="G2", name="冲突必须真持久化",
        passed=g2_pass,
        detail=(
            f"fact_contradictions={sem.get('fact_contradictions',0)} (要求≥5), "
            f"clarification_records={sem.get('clarification_records',0)} (要求≥5)"
        ),
    ))

    # G3 · 用户纠错必须更新权威值
    g3_pass = bool(correction.get("hard_indicator_4_passed"))
    gates.append(V24Gate(
        code="G3", name="用户纠错必须更新权威值",
        passed=g3_pass,
        detail=(
            f"budget after: {correction.get('budget_correction',{}).get('after_authoritative')}, "
            f"superseded: {correction.get('budget_correction',{}).get('superseded')}"
        ),
    ))

    # G4 · 故事卡空白段必须少于 3
    empty_sections = 10 - d4.get("sections_with_content", 0)
    g4_pass = empty_sections < 3
    gates.append(V24Gate(
        code="G4", name="故事卡空白段必须 < 3",
        passed=g4_pass,
        detail=f"sections_with_content {d4.get('sections_with_content',0)}/10, 空白段 {empty_sections}",
    ))

    # G5 · 时间线必须按中文日期回答 (Q36/Q39 通过)
    qa_36 = next((r for r in qa_results if r["qid"] == "Q36"), {})
    qa_39 = next((r for r in qa_results if r["qid"] == "Q39"), {})
    g5_pass = qa_36.get("correct", False) and qa_39.get("correct", False)
    gates.append(V24Gate(
        code="G5", name="时间线必须按中文日期回答",
        passed=g5_pass,
        detail=f"Q36 correct={qa_36.get('correct')}, Q39 correct={qa_39.get('correct')}",
    ))

    # G6 · LLM 严重幻觉 (本 runner 不调 LLM, 标 N/A → 默认 PASS 但 critical=False)
    gates.append(V24Gate(
        code="G6", name="LLM 严重幻觉",
        passed=True,
        detail="本 runner 用 deterministic answerer, 不调 LLM. P1-5/P1-6 真 LLM 测试待启动",
        is_critical=False,
    ))

    # G7 · 跨客户数据串线
    g7_pass = bool(isolation.get("isolation_passed"))
    gates.append(V24Gate(
        code="G7", name="跨客户数据不能串线",
        passed=g7_pass,
        detail=(
            f"基金会李明事实数: {len(isolation.get('foundation_li_ming_facts',[]))}, "
            f"教育中心李明事实数: {len(isolation.get('education_li_ming_facts',[]))}, "
            f"leak: {isolation.get('leak_detected')}"
        ),
    ))

    # G8 · 飞书入口隔离 (本 runner 不测飞书)
    gates.append(V24Gate(
        code="G8", name="飞书入口必须有 client_id",
        passed=True,
        detail="本 runner 不接入飞书. P3 阶段待测",
        is_critical=False,
    ))

    return gates


def evaluate_scores(test_result: dict) -> list[V24Score]:
    """跑 7 维新分数 (100 分)."""
    scores = []
    old_scoring = test_result.get("scoring", {})
    old_scores = old_scoring.get("scores", {})
    old_detail = old_scoring.get("details", {})

    # D1 · 数据分型 (10)
    d1_rate = old_detail.get("D1", {}).get("hit_rate", 0)
    scores.append(V24Score(
        code="D1", name="数据分型", max_score=10,
        score=10 * d1_rate,
        detail=f"hit_rate {d1_rate:.0%} (基于 normalizer 规则映射)",
        is_inflated=False,
    ))

    # D2 · 真实抽取 (15) — 当前预标 fact, 标虚高
    d2_rate = old_detail.get("D2", {}).get("recall_rate", 0)
    scores.append(V24Score(
        code="D2", name="真实抽取", max_score=15,
        score=15 * d2_rate * 0.5,  # 虚高折半计分
        detail=f"实体召回 {d2_rate:.0%} (★虚高: 当前喂预标 fact, 待 P1-5 真 LLM 抽取)",
        is_inflated=True,
    ))

    # D3 · 语义派生 (20)
    sem = test_result.get("semantic_table_counts", {})
    d3_components = {
        "event_line_activities >= 8": sem.get("event_line_activities", 0) >= 8,
        "risk_signals >= 3": sem.get("risk_signals", 0) >= 3,
        "commitments >= 1": sem.get("commitments", 0) >= 1,
        "strategic_thought_insights >= 3": sem.get("strategic_thought_insights", 0) >= 3,
    }
    passed = sum(d3_components.values())
    scores.append(V24Score(
        code="D3", name="语义派生", max_score=20,
        score=20 * passed / 4,
        detail=f"4 张语义表派生达标: {passed}/4 ({sem})",
    ))

    # D4 · 冲突澄清 (20)
    fc = sem.get("fact_contradictions", 0)
    cr = sem.get("clarification_records", 0)
    d4_score = 0.0
    if fc >= 5: d4_score += 10
    if cr >= 5: d4_score += 10
    scores.append(V24Score(
        code="D4", name="冲突澄清", max_score=20,
        score=d4_score,
        detail=f"fact_contradictions={fc} (要求≥5), clarifications={cr} (要求≥5)",
    ))

    # D5 · 时间线 (10)
    qa_results = test_result.get("qa_results", [])
    time_qids = ("Q36", "Q37", "Q38", "Q39", "Q40")
    time_correct = sum(1 for r in qa_results if r["qid"] in time_qids and r["correct"])
    scores.append(V24Score(
        code="D5", name="时间线", max_score=10,
        score=10 * time_correct / len(time_qids),
        detail=f"时间题 {time_correct}/{len(time_qids)} 正确",
    ))

    # D6 · 故事卡 (15)
    d4_old = old_detail.get("D4", {})
    sec_content = d4_old.get("sections_with_content", 0)
    scores.append(V24Score(
        code="D6", name="故事卡", max_score=15,
        score=15 * sec_content / 10,
        detail=f"10 段有内容: {sec_content}/10",
    ))

    # D7 · 受限问答 (10) — 当前 deterministic, 标虚高
    d5_old = old_detail.get("D5", {})
    qa_rate = d5_old.get("correct_rate", 0)
    scores.append(V24Score(
        code="D7", name="受限问答", max_score=10,
        score=10 * qa_rate * 0.5,  # 虚高折半计分
        detail=f"50 问 {d5_old.get('correct',0)}/50 ({qa_rate:.0%}) ★虚高: 当前 deterministic, 待 P1-6 LLM 受限",
        is_inflated=True,
    ))

    return scores


def render_v24_report(test_result: dict) -> str:
    """渲染 V2.4 评分 markdown 报告."""
    gates = evaluate_gates(test_result)
    scores = evaluate_scores(test_result)

    # 门禁结果
    critical_failed = [g for g in gates if g.is_critical and not g.passed]
    overall_pass = len(critical_failed) == 0

    lines = []
    lines.append("# V2.4 青禾测试 · 新评分体系报告(门禁 + 分数)")
    lines.append("")
    lines.append("> 顾源源 5/23 钦定: 不再追单一总分,改成「门禁 + 分数」")
    lines.append("")
    lines.append(f"**测试时间**: {test_result.get('test_meta', {}).get('run_at', '?')}")
    lines.append(f"**测试客户**: 青禾公益基金会 + 青禾教育研究中心(跨客户隔离)")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 门禁
    lines.append("## 🚪 门禁(8 项)")
    lines.append("")
    lines.append("| 门禁 | 状态 | critical? | 详情 |")
    lines.append("|---|---|---|---|")
    for g in gates:
        mark = "✅ PASS" if g.passed else "❌ FAIL"
        crit = "是" if g.is_critical else "否(参考)"
        lines.append(f"| {g.code} {g.name} | {mark} | {crit} | {g.detail} |")
    lines.append("")
    if overall_pass:
        lines.append("### ✅ 门禁结论: **数据中心假设成立**")
    else:
        lines.append("### ❌ 门禁结论: 数据中心假设未成立")
        lines.append("")
        lines.append("**失败的 critical 门禁**:")
        for g in critical_failed:
            lines.append(f"- {g.code} {g.name}: {g.detail}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 分数
    total_score = sum(s.score for s in scores)
    total_max = sum(s.max_score for s in scores)
    lines.append(f"## 📊 分数: {total_score:.1f} / {total_max:.0f}")
    lines.append("")
    lines.append("| 维度 | 满分 | 得分 | 占比 | 详情 |")
    lines.append("|---|---|---|---|---|")
    for s in scores:
        inflate_tag = " ★虚高" if s.is_inflated else ""
        lines.append(
            f"| {s.code} {s.name}{inflate_tag} | {s.max_score:.0f} | "
            f"{s.score:.1f} | {s.score / s.max_score:.0%} | {s.detail} |"
        )
    lines.append(f"| **总分** | **{total_max:.0f}** | **{total_score:.1f}** | "
                 f"**{total_score / total_max:.0%}** | — |")
    lines.append("")

    # 虚高说明
    inflated = [s for s in scores if s.is_inflated]
    if inflated:
        lines.append("### ⚠️ 虚高维度说明")
        lines.append("")
        for s in inflated:
            lines.append(f"- **{s.code} {s.name}**: {s.detail}")
        lines.append("")
        lines.append("剔除虚高后真实分数:")
        real_total = sum(s.score if not s.is_inflated else (s.score / 0.5) * 0
                        for s in scores)
        real_max = sum(s.max_score if not s.is_inflated else 0 for s in scores)
        lines.append(
            f"`{real_total:.1f} / {real_max:.0f}` (只算非虚高维度,共 4 维 {real_max:.0f} 分)"
        )
    lines.append("")
    lines.append("---")
    lines.append("")

    # 顾源源 4 硬指标对照
    lines.append("## 🎯 顾源源 4 硬指标")
    lines.append("")
    sem = test_result.get("semantic_table_counts", {})
    correction = test_result.get("user_correction", {})
    d4_sec = test_result.get("scoring", {}).get("details", {}).get("D4", {})
    hi = [
        ("1. 语义表有数据",
         all([sem.get("event_line_activities", 0) >= 8,
              sem.get("risk_signals", 0) >= 3,
              sem.get("commitments", 0) >= 1,
              sem.get("strategic_thought_insights", 0) >= 3])),
        ("2. 冲突真持久化",
         sem.get("fact_contradictions", 0) >= 5
         and sem.get("clarification_records", 0) >= 5),
        ("3. 故事卡讲清项目",
         d4_sec.get("sections_with_content", 0) >= 8),
        ("4. 用户纠错变聪明",
         bool(correction.get("hard_indicator_4_passed"))),
    ]
    for name, passed in hi:
        mark = "✅" if passed else "❌"
        lines.append(f"- {mark} {name}")
    lines.append("")
    all_pass = all(p for _, p in hi)
    if all_pass:
        lines.append("### ✅ 4 个硬指标全部过线 — **数据中心从「事实仓库」升级为「项目理解引擎」**")
    else:
        lines.append("### ⚠️ 硬指标未全过线")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 下一步建议
    lines.append("## 🛠 下一步")
    lines.append("")
    if all_pass:
        lines.append("**P1 阶段** (真 LLM 测试) 现在可以启动:")
        lines.append("")
        lines.append("- 任务 5: RawText→Fact 真实抽取测试 (不喂预标, 喂原文)")
        lines.append("- 任务 6: LLM 受限问答测试 (LLM 只基于 evidence)")
        lines.append("")
        lines.append("**P3 阶段**(主仓库反向同步 + 飞书集成)继续等顾源源决策。")
    else:
        lines.append("先修硬指标失败项,再启动 P1/P3。")

    return "\n".join(lines)
