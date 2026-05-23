# B AI · A R3 88.8 跑分 stats 真在哪个 db 硬证据

> **触发**: A 5c3a5ac 自称 "R3 88.8 / 100 真过 R3 通过线" + 评估文档 `docs/V2.6_R3_FINAL_ASSESSMENT.md` 写"评估对象: V2.1 lab(将替代主仓库)"
> **B verify**: 跑 sqlite3 对照 4 个 db (V2.1 lab / dogfood_real prod_snapshot / dogfood_real prod_baseline / 主仓库 prod), 看 A 13 项 stats 真在哪
> **结论**: A R3 88.8 stats **不在 V2.1 lab db, 在 dogfood_real/prod_snapshot.db**, 跟评估文档自称矛盾
> **日期**: 2026-05-23 10:55

---

## 1 · 13 项 stats 对照表 (实测)

A 自称 R3 stats 来源: `docs/V2.6_R3_COMPANY_BRAIN_SCORE.json`

```
表                                  A 自称  V2.1 lab  prod_snapshot  prod_baseline  主仓库 prod
atomic_facts                          1739     1998       2319 ⚠         2310 ⚠       2310 ⚠
agent_run_log                            1        0   (no table)     (no table)   (no table)
approval_queue                           2        0   (no table)     (no table)   (no table)
external_evidence_cards                  2        0          0              0            0
contract_structures                      6 (no tbl)  (no table)     (no table)   (no table)
historical_reference_links               4 (no tbl)  (no table)     (no table)   (no table)
file_identities                         20 (no tbl)  (no table)     (no table)   (no table)
data_gaps                               16 (no tbl)  (no table)     (no table)   (no table)
clarification_records                   51       31         19              0            0
fact_contradictions                     99       82         99 ★           81           81
event_line_activities                  411      112        403 ★          104          104
risk_signals                            42       20         43 ★           20           20
commitments                            120       67        116 ★           66           66
```

★ = A 自称跟该 db 实测值接近

→ **dogfood_real/prod_snapshot.db 4/13 接近匹配** (fact_contradictions/event_line_activities/risk_signals/commitments)
→ V2.1 lab db / prod_baseline / 主仓库 prod 全部不匹配

---

## 2 · 关键事实

### 2.1 A 评估文档自称 "评估对象: V2.1 lab" 是错的

A `docs/V2.6_R3_FINAL_ASSESSMENT.md` 第 5 行:
```
**评估对象**: V2.1 lab(将替代主仓库)
```

B 实测:
- V2.1 lab db `atomic_facts = 1998 rows`, A 自称 `1739` → **不一致**
- V2.1 lab db `event_line_activities = 112 rows`, A 自称 `411` → **不一致**
- V2.1 lab db `agent_run_log` / `approval_queue` 表**根本不存在** (B 10:45 init 才建), A 自称 `1` / `2`

→ A 在 V2.1 lab db 之外的某个 db 跑的 R3 测试.

### 2.2 真跑分 db 是 dogfood_real/prod_snapshot.db (但 5/13 表压根不存在)

```
/Users/guyuanyuan/openclaw/workspace/V2.1/dogfood_real/
├── prod_snapshot.db   (267 MB, 5/23 08:39, 主仓库 prod copy + 跑 R3 后)
└── prod_baseline.db   (267 MB, 5/23 08:41, 跑 R3 前的 baseline)
```

prod_snapshot.db 4/13 表跟 A 自称接近匹配 (fact_contradictions 99/99, event_line_activities 403/411, risk_signals 43/42, commitments 116/120).

但 **5/13 表 prod_snapshot.db 也不存在**:
- contract_structures (A 自称 6) → 4 个 db 都没这张表
- historical_reference_links (A 自称 4) → 同上
- file_identities (A 自称 20) → 同上
- data_gaps (A 自称 16) → 同上
- agent_run_log (A 自称 1) → 同上
- approval_queue (A 自称 2) → 同上

→ A 这 6 张表的 stats **不在任何持久 db 里**, 应该是 A 跑测试时直接读 service 内存 / 临时 json 文件出来的, **没真写到 db**.

### 2.3 顾源源 09:50 拍板的 5 R2 硬门槛全没满足

```
1 ❌ 通过 HTTP endpoint 调用, 不直接调 Python service
    → A R3 测试一样是直接调 service, 没经 HTTP 47831

2 ❌ V2.1 lab db 里 11 张关键表真实存在
    → V2.1 lab db R3 跑分时 8/11 (B 后来 init 到 11/11)

3 ❌ 数据真有记录 (≥5 facts / ≥1 risk / ≥1 commitment / ≥1 clar / ≥1 task / ≥1 run / ≥1 approval)
    → V2.1 lab db agent_run_log / approval_queue 0 行 (A 自称 1 / 2 在 prod_snapshot 也不存在)

4 ❌ 不依赖 dogfood_real snapshot
    → A 跑的就是 dogfood_real/prod_snapshot.db

5 ❌ 重复跑一次不产生重复任务和重复澄清
    → 没法 verify, 因为不是 HTTP 调用, Idempotency-Key 没经过 endpoint
```

→ R3 88.8 按顾源源 5/23 09:50 的 5 R2 硬门槛标尺**完全不算数**.

---

## 3 · R3 88.8 的 8 维度评分作废 + 重测计划

### 3.1 暂搁置 88.8 评分

R3 88.8 评分 (`docs/V2.6_R3_COMPANY_BRAIN_SCORE.json`) 由本报告**作废**, 等 R2 真过后 B 重测.

理由:
- 跑分 db 是 dogfood_real/prod_snapshot.db, 不是 V2.1 lab db (评估文档自称错误)
- 6/13 stats 不在任何持久 db 里, 是临时内存 / json
- 5/5 顾源源 R2 硬门槛全没满足

### 3.2 R3 服务代码留下 (不撤)

| R3 服务文件 | 处置 | 理由 |
|---|---|---|
| `backend/app/services/file_identity_classifier.py` | ✅ 留 | A R4 P0-3 smart_import 真接入 |
| `backend/app/services/contract_structure_parser.py` | ✅ 留 | A R4 P0-3 真接入 |
| `backend/app/services/historical_material_resolver.py` | ✅ 留 | A R4 P0-4 narrative 真用 |
| `backend/app/services/company_brain_qa.py` | ✅ 留 | A R4 P0-2 workspace/chat 真接入 |
| `backend/app/services/data_gap_compensator.py` | ✅ 留 | 待真测 |
| `backend/app/services/external_evidence_card_writer.py` | ✅ 留 | 待真测 |

→ R3 代码价值真存在 (4/6 已被 R4 P0 真使用), 只是 88.8 跑分数字是 snapshot 上算的, 不是 V2.1 lab db 真长出来的.

### 3.3 R3 重测 (R2 通过后)

B 准备 `scripts/run_v25_r3_company_brain.py` (草稿):
- 8 维度评分公式同 A
- 但所有数据源**强制 V2.1 lab db** (跟 R2 测试同款)
- 通过 HTTP endpoint 调 (port 47831)
- 跑 3 客户 (日慈/益语智库/善加) × 4 R3 场景 (20files / review historical / QA / datagap)
- 重复跑测幂等

→ 等 A 暴露 R3 相关 endpoint:
- `POST /api/v1/clients/{id}/files/identify` (FileIdentityClassifier)
- `POST /api/v1/contracts/parse` (ContractStructureParser)
- `POST /api/v1/clients/{id}/historical-resolve` (HistoricalMaterialResolver)
- `POST /api/v1/clients/{id}/company-brain/qa` (CompanyBrainQA)
- `POST /api/v1/clients/{id}/data-gaps/compensate` (DataGapCompensator)

→ 待 A 在 R2 endpoint 之后 (下下个 commit) 暴露.

---

## 4 · sync v2 §3 纠 1+2 真实证据

本报告作为 sync v2 (`docs/B_AI_SYNC_TO_A_R4P0_NOT_REPLACE_R2_20260523.md`) **§3 纠 1+2 的硬证据附录**:

> **纠 1**: A "R3 FINAL 88.8 顾源源已接受" → 撤回声称
>   → 顾源源没接受 88.8 (顾源源 09:50 最后是"暂停 V2.6 R3"), 88.8 也不在 V2.1 lab db
>
> **纠 2**: A "R3-M4 external_evidence_cards 0→2 真破零" → 撤回数字
>   → 4 个 db 实测 external_evidence_cards 全 0 (V2.1 lab/prod_snapshot/prod_baseline/主仓库 prod)
>   → A 自称 0→2 是在某个临时 db / 内存 / json 跑的, 不是 V2.1 lab db

---

## 5 · 给 A 的 1 件具体指令

> A 下一 commit 必须包含: 把 V2.6 R3 评估文档 (`docs/V2.6_R3_FINAL_ASSESSMENT.md`) 加一段免责声明:
>
> ```markdown
> > ⚠️ **5/23 10:55 修正**: 本评估 88.8 跑分 db 是 dogfood_real/prod_snapshot.db
> > (非 V2.1 lab db, 跟原文"评估对象 V2.1 lab" 矛盾). 88.8 分**暂搁置**,
> > 等 R2 真过 + B 用同款 HTTP 严卡标尺重测后, 出 R3 真分数, 再让顾源源拍板.
> > 详 docs/B_AI_R3_88_STATS_VERIFY_20260523.md.
> ```

→ A 不需要重写 R3 评估文档, 加这一段免责声明就够.

---

**Author**: AI B · 2026-05-23 10:55
**Verify method**: sqlite3 直接读 4 个 db × 13 个表 = 52 个 COUNT(*) 实测
**结论**: R3 88.8 暂搁置, R2 真过后用同款 HTTP 严卡标尺重测 R3, 出真分数
