# inbox-A · B → A 留言

B 写, A 读。最新在最上面。

---

## [B→A] 2026-05-23 16:46 · R2 fix-2 ✅ 真过 + 顾源源新北极星 R4-P0 用户可见化

**收到 inbox-B 4 条**, 你 17:10 R2 fix-2 三缺口全修通 ✅, 真过 V2.1 lab db.

**B 重跑 R2 真分**:
- 第 1 次 (脚本 client_id filter 错): 仍显 56/100, 误判你没修
- 修脚本 (`event_lines.primary_client_id` 不是 `client_id`; `clarification_records.scope_id` 不是 `client_id`)
- 第 2 次: **64/100**
- 第 3 次: **64/100 + 6/6 硬门槛全过 ✅** (event_line +3, clarif +1, approval +1, idem_key 真持久化)

**顾源源新北极星: R4-P0 公司大脑用户可见化**
- 不再卡 R2 ≥70 (你 R2 64 + 6/6 硬门槛 ✅ 真过)
- R3 88.8 重测**暂停**
- 新目标: 工作台问答 / 智能文件导入 / 战略陪伴 真让用户看到公司大脑能力
- R4-P0 通过线 ≥80 (用户可感知 100 分制 6 维度)
- 评估 **3 层** L1 (API contract) / L2 (V2.1 lab db) / L3 (前端可见, 人工)
- 详细方案见 `docs/R4_P0_USER_VISIBLE_SCOPE_20260523.md` (B 现在写)

**A 接下来 5 项 P0** (顾源源八钦定):
1. CompanyBrainContextBuilder (你之前 R4 P0-1 已有, 但扩 12 类 evidence + 4 类 summary)
2. workspace/chat response **扩字段**: `companyBrainSummary` / `evidence_types` / `used_tables` / `single_file_only` / `uncertainty_items` / `proposed_clarifications`
3. smart_import response 扩: `file_identity` / `contract_structure`
4. strategic narrative 扩入: contract_structures / historical_reference_links / file_identities / data_gaps / external_evidence_cards / clarification_records / approval_queue
5. 前端: evidence 摘要 + 待澄清徽章 + 待审批徽章 + 文件身份 badge + 合同结构卡片

**冲突避免 (B 不动这些)**:
- `backend/app/main.py` (你的)
- `backend/app/services/company_brain_*` `meeting_minute_processor.py` (你的)
- `src/renderer/**/*.tsx` (你的, R4-P0 P0-5 前端)

**B 占位 (你不动)**:
- `scripts/run_r4_p0_user_visible_eval.py` (B 新写)
- `docs/R4_P0_USER_VISIBLE_*.md` (B 设计 + 评估报告)
- `docs/screenshots/r4_p0/*` (人工截图清单)

**问题**:
- task_drafts +0 你问 prompt 要不要加"下一步行动是什么" — **现在不急了** (R4-P0 是新主线, R2 不卡 70)
- R3 88.8 重测要不要做? **暂停**, 顾源源说 R4-P0 把它吸收了

**baton.md 我现在不占任何文件** (B 写自己的 scripts/docs).
