# A 自检 · 数据库—功能接通报告

**时间**: 2026-05-23 17:40
**口径**: V2.1 lab backend HTTP + V2.1 lab db + 前端可见(不接受 snapshot 跑分)
**触发**: 顾源源 5/23 R4-P0 用户可见化新北极星 + B 16:46 sync

---

## 总分

```
数据库—功能接通自检得分: 41 / 100  (本次基线, 后面补完 P0 5 项再算)
14 功能 A 级:            1 / 14    (智能文件导入 prod 真接通)
14 功能 B 级:            5 / 14    (工作台问答 / 战略陪伴 / 事实澄清 / Approval / Agent 会议纪要)
14 功能 C 级:            5 / 14
14 功能 D 级:            3 / 14
14 功能 E 级:            0 / 14
```

R4-P0 通过线 14 功能 A 级 ≥5/14 — **差 4 个 A 级**。

---

## 14 功能评级表

| # | 功能 | 评级 | 调 R3 新服务 | 用新表 | 前端可见 evidence | 主要缺口 |
|---|---|---|---|---|---|---|
| 1 | 工作台问答 | **B** | ✅ build_company_brain_context | ✅ 14 类 | ⚠️ 仅子字段 badge | response 顶层字段缺;待澄清徽章无 |
| 2 | 智能文件导入 | **A** | ✅ file_identity + contract_parser | ✅ file_identities + contract_structures | ❌ 前端 badge 缺 | 前端文件身份 badge / 合同结构卡 |
| 3 | 战略陪伴 6 段 | **B** | ⚠️ bundle 加 R4 字段但 prompt 没用 | ✅ 5 字段加 | ❌ | narrative_generator prompt 没引用新字段 |
| 4 | 事实澄清 | **B** | ✅ clarification_records 写 | ✅ | ❌ 徽章无 | 工作台 / 战略陪伴 待澄清徽章 |
| 5 | Approval Queue | **B** | ✅ 4 endpoint 暴露 | ✅ approval_queue 写 | ❌ 前端徽章无 | 前端待审批徽章 + 操作按钮 |
| 6 | Agent 会议纪要处理 | **B** | ✅ HTTP endpoint 暴露 + R2 fix-2 | ✅ V2.1 lab db 真长 | ❌ 用户入口无 | 没暴露给前端用户 |
| 7 | 任务详情 | **C** | ❌ 不调 historical_resolver | ❌ 只 tasks 表 | ❌ | 不关联客户记忆 |
| 8 | AI 周复盘 | **C** | ❌ 不调 historical_resolver | ⚠️ event_lines + tasks 旧表 | ❌ | 不识别旧合同/会议 |
| 9 | 任务智能解析 | **C** | ❌ | ⚠️ | ❌ | 不识别客户/项目/承诺 |
| 10 | 资讯情报写为提案 | **B** | ⚠️ 部分接 external_evidence_cards | ⚠️ | ❌ | 不调 data_gap_compensator |
| 11 | 成长中心方法卡 | **C** | ❌ ai_learned_rules 仍 0 | ⚠️ growth_signal_events | ❌ | 不进生成上下文 |
| 12 | 组织计划工坊 | **D** | ❌ | ❌ task 挂接 0 | ❌ | 计划与客户项目未联 |
| 13 | 填写模板 | **C** | ❌ 不调 ContextBuilder | ⚠️ | ❌ | 字段不走权威值 → 合同 → atomic 链 |
| 14 | 粘贴生成文档 | **D** | ❌ | ❌ | ❌ | 只读当前粘贴 |

---

## 5 项 P0 缺口清单(对应顾源源/B 16:46 钦定)

### P0-1 · CompanyBrainContextBuilder 12 类 evidence + 4 summary

**已做**: ✅
- 14 类 evidence: `authoritative_facts / candidate_facts / contracts / files / historical_links / timeline / commitments / risks / clarifications / external_evidence / data_gaps / method_cards / plan_links / approvals`
- 4 summary: `evidence_summary / uncertainty_summary / recommended_actions / used_tables`

**自检结论**: 已满足。

### P0-2 · workspace/chat response 顶层字段扩

**已做** (R4 P0 commit `553d86c`): ✅ `companyBrainSummary` 子字段
**B/顾源源要求**:**顶层**扩 5 字段:`evidence_types`/`used_tables`/`single_file_only`/`uncertainty_items`/`proposed_clarifications`

**缺口**: 当前是子字段挂在 `companyBrainSummary`,B 测试脚本和前端不一定看到。需要顶层暴露。

### P0-3 · smart_import response 扩 file_identity / contract_structure

**已做** (R4 P0 commit `553d86c`): ⚠️ 只返回 `r4_file_identities_added` 计数
**B/顾源源要求**: response 实质返回 file_identity 详情列表 + contract_structure 详情列表

**缺口**: response 缺结构化详情(只有计数)。

### P0-4 · strategic narrative 扩入新表

**已做** (R4 P0 commit `553d86c`): ⚠️ `ClientFactBundle` 加 5 R4 字段
**B/顾源源要求**: narrative_generator 的 prompt **真用**新字段

**缺口**: prompt 没引用 `contracts_r4` / `historical_links_r4` / `data_gaps_r4` 等。

### P0-5 · 前端 4 UI

**已做** (R4 P0 commit `553d86c`): ✅ evidence 摘要 badge
**B/顾源源要求**: 4 个新 UI:
- ⚠️ 待澄清徽章(没做)
- ⚠️ 待审批徽章(没做)
- ⚠️ 文件身份 badge(没做)
- ⚠️ 合同结构卡片(没做)

**缺口**: 4 个 badge / card 全缺。

---

## 修复优先级

```
P0 高 (1h 内完成):
  P0-2 修 · workspace/chat 顶层 5 字段     [改 main.py + models.py]
  P0-3 修 · smart_import response 实质详情 [改 main.py]

P0 中 (1-2h):
  P0-4 修 · narrative prompt 真用新字段     [改 narrative_generator.py]
  P0-5 修 · 前端 4 UI badge/card           [改 App.tsx]

P0 低 (P1 阶段):
  P0-5 升级到 client 工作台头部全局徽章 (待澄清/待审批)
```

---

## 不再做的事(R3 88.8 暂停)

```
❌ R3 88.8 重测 (顾源源 5/23 拍板 R4-P0 吸收)
❌ V2.6 R5/R6
❌ 任何后端能力扩展
```

---

## 接下来 A 干

1. **补 P0-2/P0-3/P0-5** (后端 + 前端 3 件) — 立即做
2. **跑 SELF_CHECK 第二次** 看 14 功能 A 级提升到 5/14
3. **commit + 释放 baton** + inbox-B 告知 B 重跑评估
