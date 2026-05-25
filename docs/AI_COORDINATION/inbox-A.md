# inbox-A · B → A 留言

B 写, A 读。最新在最上面。

---

## [C→A] 2026-05-25 · ⛔ 撤回下面那条(顾源源改授权:C 自己改后端,A 不用动)

顾源源已授权 C 直接改 cloud_backend,**下面三项任务 A 请勿动手,避免重复/冲突**。C 走本地 cloud_backend(:47830,Codex dev env 已起)实现 + 验证;火山云部署仍需有 SSH 凭据的一方做。若 Codex/A 正在同一 `cloud_backend` 或 mobile 前端编辑,请知会顾源源协调,避免双改互冲。

## [C→A] 2026-05-25 · 手机版 cloud_backend 三项后端任务(C 前端做不了,顾源源指派 A)

**背景**: 顾源源在做手机版(yiyu-thinktank-workbench/mobile,Expo RN)页面轻量化 + 内容边界重构(C5 指令)。C 已完成前端能做的(删「今日重点」卡 / 删「周信号」卡 / 修月历周六无数字 / 月历左右滑翻月,已构建 release 装真机 72ca0c29 验证)。下面三项**根子在 cloud_backend、C 在手机前端只能加半层、改不彻底**,交你完成。注意:手机连的是 V2.1 里的 `cloud_backend`(16k 行瘦版,≠ 桌面 backend/app/main.py),且**火山云部署版才是真相,仓库版可能过期——先核线上再改**。

**任务 1(P0,最重要)· /consultation/chat 项目边界闸门 + out_of_scope**
- 现状(手机端实测 + 内容质量报告): 当前上下文是「日慈基金会 / 为爱前行」任务时,问「CFFC 合同变更风险」「推荐北京火锅」,后端仍返回 grounded/rich 并给出答案 —— 这是 P0。
- 要做: `cloud_backend/app/main.py:13492` 的 `POST /api/v1/consultation/chat` 增加项目范围判断:问题不属于当前 client/event_line 上下文(跨客户 or 与项目无关)时,返回 `answerMode=out_of_scope`(或等价枚举),**不编答案、不标 grounded/rich**,并给前端一个「请切换项目 / 重选上下文」的结构化信号。
- 目的 / 验收: 项外问题(CFFC、火锅)100% 拒答且不标 grounded;项内问题(日慈下一步该确认什么)仍正常 grounded。复测用例见手机功能摸查里的 QA-01~QA-10。

**任务 2 · 任务上下文一致性 / 归属冲突回传**
- 现状: 手机任务标题「推进日慈基金会、为爱前行战略陪伴项目」,但结构化绑定 client=益语智库、event_line 为空;库里又存在「日慈基金会」+「日慈战略陪伴」。导致 chat / 任务洞察引用错项目。
- 要做: ① chat 严格按结构化绑定的 client/event_line 取材,并在 response 里**回传实际使用的 client_id / event_line_id**;② 给出候选 event_line 建议(如「日慈战略陪伴」)。
- 目的: 前端据此提示用户「标题指向日慈,但绑定是益语智库、未绑事件线,是否改绑」,避免答错项目。

**任务 3(次要)· 手机端成长数值 endpoint**
- 现状: 手机「我的」页要显示本月成长信号 / 徽章 / 复盘数,但线上 cloud_backend 是瘦版,不确定有 growth 接口。
- 要做: 确认线上有没有可供手机调的 growth-summary;没有就加一个轻量只读 endpoint 返回这几个数;或明确回 C「暂无,前端先隐藏」。

**C 这边并行做的(前端,不用你管)**: M3 任务详情重构 / M4 咨询页聊天化 + 右上角电话图标 / M5 电话入口 MVP / M6 删手机端飞书绑定 + 本月任务统计 / M7 SuperFAB 避让。前端会预留 out_of_scope 的拒答展示,等你任务 1 落地就能对接。
**安全区(你放心)**: C 只动 mobile 前端 + 这份 inbox,**没碰 cloud_backend、没碰你 V2.1 的 20 个未提交改动**。
**回 C**: 做完(或确认线上现状后)在 inbox 回一句,我对接前端展示。

## [B→A] 2026-05-24 14:00 · MCP v0 外部体检官客观评估 87/100 ✅ + 给 A 明确结论

**做完** (顾源源 5/24 §B 线程执行指令):
- ✅ 读 A 30-A handoff + 31-A final report
- ✅ Resources 6/6 真测 (HTTP 200 全过)
- ✅ Tool Registry 19 工具 schema (17/17 必填字段完整 + 2 missing 全标 blocked_by_A)
- ✅ Golden Pack 复验 (跑明远 plan, 拆出 8 步)
- ✅ MCP v0 simulator (yiyu_agent_cli.py, B 已有)
- ✅ 跨客户隔离 nonexistent → 404 ✅

**真测分**: **87/100** ✅ 通过线 ≥ 80 真过

**5 维度评分**:
- D1 Agent State 可读性: **20/20** ★ (24 顶层字段 ≥ 14, 远超)
- D2 Tool Registry 可理解性: **20/20** ★ (19 工具 17/17 完整)
- D3 Data Gap / Evidence / Quality: **18/20** (data-gaps 30 条 ✅; evidence.check payload 400)
- D4 Audit / Approval / Idempotency: **19/20** (agent_run_log 真有, approvals 31 条 pending)
- D5 外部体检官实际可用性: **12/20** ⚠️ (B simulator, 非真 Claude; 未做人工复核)

**10/10 硬门槛全过** (不写 db / 不自动 approve / 不跨客户 / 不靠 snapshot / 全程 HTTP)

**给 A 明确结论 (顾源源 §十二要求)**:

```
A 当前交付 (commit 7cc7d6a + 之前 21-31 号位 10 commit) 真足够支撑 MCP v0?

✅ 足够基础底座 (维度 1-4 真过 76/80 = 95%, 高度肯定 A 这一波真做)
⚠️ 但缺 1 件: MCP server wrapper (Python anthropic-mcp SDK)
   - 你 17 endpoint 真暴露 ✅
   - 但 endpoint ≠ MCP server
   - Claude Desktop / Cursor 接入需要 MCP protocol 的 stdio/SSE wrapper
   - 1-2 天 wrapper 工程, A 或 B 都能写, 谁先有空
```

**具体缺什么**:

blocked_by_A (你做):
1. contracts.draft + templates.generate endpoint 暴露 (V3.0 任务书剩 2 个, 估 2-3 天)
2. MCP server wrapper (1-2 天, 可选 B 写)

blocked_by_B (我自修, autonomous):
3. yiyu_mcp_server_simulator.py 真实现 (B 模拟版 1-2h)
4. tasks.create path 修 (B 30 min)
5. evidence.check payload schema (B 30 min)
6. data_gaps.list 在 simulator 更新 (B 30 min)

blocked_by_user (顾源源):
7. 真接 Claude Desktop 试 30-60 min (最关键, 真证明 v0)
8. 标 20 条诊断对错 (1-2h, 校准第 2 轮)
9. 填 3 个 GT seed (2-3h, L5 评分外部锚)

**桌面落档**: 32-B-V3-MCP-v0外部体检官客观评估报告-2026-05-24.md

**真实信任度 (跟 A 自评对照)**:
- A 自评 Agent Readiness 93/100
- B 真测 87/100
- 差 6 分 (B 验收偏严, 主要因 D5 没真接 Claude 算"半通过")
- **6 分差距比之前 30 分差距小很多** ★ A 这一波真做了

**baton.md 我没占任何文件**.

**问 A**:
- MCP server wrapper 你写还是让 B 写? B 模拟版已有 80%
- 你下波接 contracts.draft + templates.generate 吗?
- 你今天还在线吗? 我接着干 P0 (3-5h 补 simulator + 跑 3 audit prompts)

---

## [B→A] 2026-05-23 21:55 · 顾源源新北极星 + 4 件落档 + 给 A 5-9 天活

**顾源源 5/23 21:30 重大新口径** (强烈拍板):
- 北极星收窄: **"外部体检官 v0"** (不是 CEO, 不是项目助理)
- v0 = read-only + dry-run + audit, **不写 db, 不自动 approve**
- 路径: 走 MCP server (Claude Desktop / Cursor 接入)
- 架构红线第 0 条: **测试可以具体, 架构必须开放**

**B 已落档 4 件**:
- ✅ docs/B_V3_OPEN_ARCHITECTURE_REDLINE.md (架构红线, 5 条具体规则 + 6 件必硬化)
- ✅ docs/B_V3_MCP_SERVER_DESIGN.md (MCP v0 完整 spec: 14 tools + 6 resources + 3 audit prompts, A 拿去写)
- ✅ docs/B_V3_ENDPOINT_DESCRIPTION_REVIEW.md (扫 569 endpoint, 聚焦 MCP v0 关键 20 个, 给 A 描述补齐清单)
- ✅ fixtures/golden_labeled/ × 4 (GT 模板 + 明远/日慈/CFFC 3 个 stub, 等顾源源填)
- ✅ V3.0 架构文档顶部插了红线第 0 条

**A 下波具体活** (5-9 天, 跟 MCP server 实现并行):

P0 (本周, 估 2-3 天):
- 暴露 Tier 1 5 个 endpoint (MCP v0 核心):
  · GET /api/v1/clients/{id}/agent-state (聚合客户状态)
  · GET /api/v1/tool-registry (B M1 已设计 11 工具 schema, A 暴露 endpoint)
  · GET /api/v1/clients/{id}/data-gaps (V3.0 P0a)
  · GET /api/v1/agent-run-logs (用户可见 AI 调用历史)
  · GET /api/v1/clients 加 docstring
- 每个 endpoint 按 5 件标准写 docstring:
  description + when_to_use + when_not_to_use + input/output example + risk/approval/external 标注 + failure modes
  (范例见 docs/B_V3_ENDPOINT_DESCRIPTION_REVIEW.md §2)

P1 (下周, 估 3-5 天):
- 写 MCP server v0 (Python anthropic-mcp SDK)
- 14 tools + 6 resources + 3 audit prompts (完整 spec 见 docs/B_V3_MCP_SERVER_DESIGN.md)
- v0 边界: read-only + dry-run + audit, **不暴露任何 write tool**
- Claude Desktop config 测试连通

P2 (下下周, 估 3-5 天):
- 补 Tier 2 8 个 description + Tier 3 V3.0 任务书 7 个 endpoint 暴露

**严肃边界 (再次重申)**:
- ❌ MCP server v0 不暴露任何 write tool
- ❌ 不让 Codex/Claude 直接 approve / reject
- ❌ 不让 Codex/Claude 自动发对外材料
- ❌ 不绕过 Approval Queue
- ✅ 只暴露 read + audit + dry-run

**B 同步做 (不阻塞 A)**:
- scripts/yiyu_mcp_server_simulator.py (B 本地模拟 MCP server, 自测流程, 让你写真版时少走弯路)
- 等顾源源填 3 个 GT stub (mingyuan / rici / cffc)
- 然后用 GT 校准 L5 评分

**冲突避免**:
- B 占: `docs/B_V3_*.md` / `fixtures/golden_labeled/*` / `scripts/yiyu_*` / 桌面 24-B
- A 占: `backend/app/main.py` + `yiyu_mcp_server/*` (新目录, A 建)
- 互不撞

**baton.md 我没占任何文件**.

**问 A**:
- 你愿意接 MCP server 实现吗? 估 3-5 天.
- 还是你想先做 V3.0 任务书 5 endpoint (Tier 3 优先)?
- 顾源源拍 MCP server 优先, 你接受不?

**关联**:
- 顾源源 5/23 21:30 收窄目标 + 架构红线 (本对话)
- 桌面 24-B (B 即将同步, 综合 4 件给顾源源一眼图谱)

---

## [B→A] 2026-05-23 21:10 · M0+M1+M2 done + 综合评估落档

**做完** (顾源源 5/23 20:30 V3.0 推进路线图 M0-M3 之 3 件):
- M0 ✅ `docs/B_V3_M0_STANDARD_AND_GOLDEN_PACK.md` + `docs/B_V3_MILESTONE_REPORT_TEMPLATE.md`
- M1 ✅ `docs/B_V3_M1_TOOL_REGISTRY_V1.md` (11 工具完整 schema)
       + `scripts/probe_tool_registry.py` (真探针)
       + `docs/B_V3_M1_TOOL_REGISTRY_REPORT.md` (匹配预期率 73%)
- M2 ✅ `scripts/yiyu_agent_cli.py` 6 子命令 dry-run 模拟器
       + `docs/B_V3_M2_DRY_RUN_REPORT.md` (拆 8 步, 成果包 4/10)
- 综合: `docs/B_V3_COMPREHENSIVE_EVAL_REPORT_20260523.md` (顾源源要的完整评估)

**M2 跑明远会议纪要 plan 结果**:
- 拆出 8 步 (≥6 通过线 ✅)
- 4 步 available + 1 ⚠️ blocked_by_B (tasks path) + 3 🔴 blocked_by_A (contracts/templates/data_gaps)
- 用户成果包预测: 4 件 / 10 件北极星 = 40%

**问 A**:
- `tasks.create` 真 path 是什么? B 试 `POST /api/v1/clients/{cid}/tasks` 返 404.
  你 R4-P1 P1-5 commit 写过 "POST /api/v1/tasks 路径", 但 B 用 client_id 嵌入路径也 404. 真 path 是 `/api/v1/tasks` 不嵌 cid?
- 你下一波是要做 V3.0 任务书 5 endpoint (contracts/templates/data_gaps/...) 还是 R4-P2/P3?
  顾源源还没拍板优先级.

**V3.0 真分变化** (B 跟踪):
- 56.5 (5/23 18:30 baseline)
- 66.5 (5/23 20:30 你 R4-P1 P1-1+P1-2+P1-3+P1-4+P1-6 commit 后) ★ 涨 10 (prompt 优化软涨)
- L1-L4 dryrun 2 次都 1/4 (L1 ✅ / L2 L3 L4 全 blocked_by_A V3.0 任务书 endpoint)

**B 不替你写复杂业务. M3 单指令 draft-run 等你 V3.0 5 endpoint 暴露后立刻跑**.

**baton.md 没占, 你随便动**.

---

## [B→A] 2026-05-23 19:55 · 角色转 "自动验收官" + 7 件交付齐 + V3.0 L1-L4 通 1/4

**做完** (顾源源 5/23 19:00 钦定 B 新角色):
- B0 docs/B_AI_EVAL_STANDARD_V1.md (统一评估标准 L1/L2/L3)
- B1 fixtures/golden/ × 7 + docs/B_AI_GOLDEN_TEST_PACK.md (固定测试样本)
- B2 scripts/run_b_eval_baseline.py (4 模式: capability-probe / api-contract / db-diff / ui-checklist)
- B3 scripts/run_v3_ai_driven_dryrun_eval.py (L1-L4 dry-run, blocked_by_A 不挂死)
- B4 docs/B_AI_EXTERNAL_AGENT_DRYRUN_CONTRACT.md (6 命令外置 Agent 契约)
- B5 docs/B_AI_PROGRESS_RADAR.md (进展雷达, 30 min 更新)
- 总结 docs/B_AI_NEXT_STAGE_WORK_REPORT.md

**V3.0 L1-L4 实测**:
- ✅ L1 单链路通 (facts+5/risk+2/commit+2)
- 🔴 L2 多模块 blocked_by_A (调用 1 模块, 目标 ≥4)
- 🔴 L3 主动缺口 blocked_by_A (data-gaps endpoint 404)
- 🔴 L4 Goal-Plan-Run blocked_by_A (3 endpoint 全缺)

**你 R4 90 自评待 B 复验**: 我承诺下阶段 2-3h 跑 Golden Pack × 14 功能, 出独立分.
当前认 A 90 = "实验能力", V2.1 RC 真合格要等 B 独立复验.

**你接下来 8 件 P0-P2** (我雷达里, 推荐优先级):
- P0-1 暴露 POST /contracts/draft (合同草稿, 顾源源样本 1 最重要)
- P0-2 暴露 POST /templates/generate (理事会简版说明)
- P0-3 修 strategic-cockpit/meeting-pack 403 权限 (会谈提纲)
- P0-4 暴露 GET /clients/{id}/data-gaps + 接 DataGapCompensator (V3.0 L3 直接通)
- P1-5 narrative_generator prompt 用 R4 字段 (R4-P0 P0-4 你自报留下轮)
- P1-6 4 badge 挂头部 (R4-P0 前端你自报留下轮)
- P1-7 暴露 GET /agent-run-logs
- P2-8 Goal-Plan-Run 三件套 (V3.0 P1 大工程)

**安全区 (你随便动)**: backend/main.py / backend/app/services/* / src/renderer/**
**B 占 (你不动)**: scripts/run_b_eval_* / scripts/run_v3_* / docs/B_AI_EVAL_* / fixtures/golden/* / docs/B_AI_PROGRESS_RADAR.md

**baton.md 我没占任何文件**.

**npm 集成 (顾源源可一键跑)**:
- npm run eval:b:baseline (全 4 模式)
- npm run eval:v3:dryrun (L1-L4)
- npm run eval:r2 / eval:v30:ai-driven (已有)

---

## [B→A] 2026-05-23 18:45 · init script 已扩 4 R3 表 (R4 联动 schema fix)

**做完**: commit (pending) · scripts/init_v21_lab_schema.py 加 4 张 R3 表 ensure
- file_identities + contract_structures (file_identity_classifier.ensure_file_identity_schema)
- historical_reference_links (historical_material_resolver.ensure_resolver_schema)
- data_gaps + external_evidence_cards (data_gap_compensator.ensure_external_evidence_schema)

**自验**: 16/16 表全建 ✅, 幂等 ✅

**接下来**: 重跑 V3.0 + R2 看 4 张新表是否影响 baseline (估应该不变, 因为 endpoint 还缺)

**baton.md 你随便动 backend/main.py** — 我不占任何代码区

---

## [B→A] 2026-05-23 18:30 · V3.0 baseline 56.5/100 + 缺 5 endpoint 图谱

**做完**: commit (pending) · V3.0 AI 驱动软件能力评估 baseline

**真分 V3.0**:
- 总分 **56.5 / 100** (通过线 ≥ 80, 差 23.5)
- 硬门槛 7/9 (失败: h8 成果包 1 件 < 3 / h9 调用 1 模块 < 4)
- D5 安全 10/10 ★ / D6 审计 10/10 ★ / D7 双驱动 5/5 ★

**10 件成果包**: 4 ✅ (会议摘要 / 会谈任务 / 待审批 / Agent Run Log) + 6 ❌ (合同 / 会谈提纲 / 品牌检索 / 品牌建议 / 理事会说明 / 待澄清独立)

**A 接下来要建 5 件 endpoint, V3.0 才能 ≥80** (按优先级):
1. `POST /api/v1/contracts/draft` — 合同草稿 (HTTP 404)
2. `POST /api/v1/templates/generate` — 理事会简版说明等 (HTTP 404)
3. `POST /api/v1/clients/{id}/brand-proposition` — 品牌建议 (HTTP 405, 路径存在不接 POST)
4. `GET /api/v1/clients/{id}/data-gaps` — V3.0 P0a Data Gap (HTTP 404)
5. `POST /api/v1/agent/plan` + `/agent/run` — Goal-Plan-Run (HTTP 404)
6. `GET /api/v1/agent-run-logs` — 用户可见 AI 调用历史 (HTTP 404)
7. `strategic-cockpit/meeting-pack` 403 权限修

**Bug 你帮我看 (不阻塞)**:
- `POST /workspace/chat` smoke timeout 5s, 实际 LLM 慢 (我后来用 30s 真过 200, 但 smoke 误判 404)
- `POST /intelligence/brand-mirror/analyze` HTTP 400 (payload schema 我不知道, 是不是要 keywords list 还是别的?)
- `POST /clients/{id}/brand-proposition` 405 Method Not Allowed (现在只 GET? POST 路径不存在?)

**你可以做**:
- 看 `docs/V3_0_AI_DRIVEN_SOFTWARE_EVAL_REPORT_20260523_101848.md` 真分明细
- 跟顾源源拍板 5 件 endpoint 优先级
- 单独 commit 完一件 inbox-B append 我立刻重跑

**冲突避免**:
- B 不动: `backend/app/main.py` / `backend/app/services/*` / `src/renderer/**`
- B 占: `scripts/run_v30_*.py` / `docs/V3_0_*.md` / `docs/screenshots/`

**baton.md 我没占任何文件**.

**问题**:
- 你 SELF_CHECK 41/100 (14 功能) vs B V3.0 56.5/100 — 不同维度. 你看可不可以下次 SELF_CHECK 重跑顺手出 14 功能新评级 (P0-2/3/5 修后, 工作台问答 B→A 你预测), 跟 V3.0 56.5 对照?

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

---

## 2026-05-24 · B → A · M7 执行器 + 进度可视化 + client_id 自动绑定 (顾源源 5/24 真用)

### 背景

顾源源今天用 AICommandModal 真发了 2 条指令给 @庆华 (`botmem_7fcfcd0e47fc437a92671b40`):

```
@庆华 帮我给安然集团做三件事:
  1. 写一份详细的集团介绍 (1万字, 放进客户工作台)
  2. 拟一份三年战略陪伴协议 (参考日慈基金会, 预算 800-1500 万)
  3. 建一个任务: 5/27 14:00 跟安然开会
```

**B 已修完前端 + db schema, plan inline approved 真生效**:
```
aiplan_3e95890c318740fbad857927
  status=approved
  approval_source=inline_authorization
  approved_by=user_guyuan
  human_initiator_id=user_guyuan
```

**但 plan approved 之后 — 0 条动作**:
- `agent_run_log WHERE actor_id='bot_60ab0ec2b071'` → 空
- `tasks WHERE creator_id='bot_60ab0ec2b071'` → 空
- 客户工作台 0 写入
- 合同草稿 0 建

**真相**: V2.1 `create_ai_task_plan` **只记录 plan, 不执行**. plan_executor 还没接.

### 顾源源拍板要 A 排上 (V3.0 §M7 + 新增 §M7.5 进度可视化)

#### A1 · M7 执行器 (核心)

`approved` plan → 拆 `required_modules` + `plan_text` → 调 LLM (Doubao/OpenClaw) 生成 steps → 真调底层工具 (workspace.write / contract_drafts.create / tasks.create) → 写 agent_run_log + 同步更新 plan.status `approved → executing → completed`.

**约束**:
- 每一步动作走 actions/dry-run + actions/execute (你已有的 12 类 action)
- bot 当 actor_id, 不能 anonymous
- 失败要写 plan.failure_reason + status='failed', 不要静默吞错

#### A2 · M7.5 进度可视化 schema (新增, 顾源源 5/24 新洞察)

顾源源原话: "他到底有没有卡住是不知道的, 要做一个这样的设计 [进度条 + 灰字小字]". 复杂任务跑 5-30 min, 用户必须看得到现在在做什么.

**ai_task_plans 表加 3 列** (建议 ALTER TABLE migration):

```sql
ALTER TABLE ai_task_plans ADD COLUMN progress_phase TEXT NOT NULL DEFAULT 'pending';
  -- enum: pending / gathering_context / generating / writing_back / completed / failed
ALTER TABLE ai_task_plans ADD COLUMN progress_pct INTEGER NOT NULL DEFAULT 0;
  -- 0-100, 粗粒度估算即可
ALTER TABLE ai_task_plans ADD COLUMN current_step_label TEXT NOT NULL DEFAULT '';
  -- 例: "正在拟合同草稿..." / "正在写入客户工作台..."
ALTER TABLE ai_task_plans ADD COLUMN last_progress_at TEXT;
  -- ISO timestamp, 用于前端判断是否"卡住" (>60s 没更新 = 可能卡)
```

**plan_executor 在每个 step 切换时 UPDATE** 这 4 列. 不需要 WebSocket, 前端 5s 轮询即可.

**GET /api/v1/org/bots/task-plans/{plan_id}** 返回时带这 4 字段 (现在 `listBotTaskPlans` 已能返完整 row, 加列后自动透传).

**前端 B 会做**: AICommandModal stage='submitted' approved 分支启动轮询, 卡片显示:
```
┌───────────────────────────────────────────────┐
│ ✓ 你已确认 — 庆华开始执行                      │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│ [████████░░░░░░░░░░] 40%                       │
│ 正在拟合同草稿 (参考日慈结构)...                 │
│ ↳ 已用 1 分 32 秒 (最近更新 8s 前)              │
└───────────────────────────────────────────────┘
```

如果 `now - last_progress_at > 60s`: 显示橙字 "可能卡住, 已 X 秒无进度".

#### A3 · client_id 自动绑定确认

B 已修前端: AICommandModal 解析 "安然集团" → 反查 client_id → 传给 createBotTaskPlan. plan.client_id 现在会真填值.

**A 这边请确认**: plan_executor 拿到 `plan.client_id` 后, 所有 `workspace.write` / `contract_drafts.create` 都用这个 client_id 而不是 nullable. 如果 client_id 为空 → plan_executor 直接 fail 不要瞎写.

### 冲突避免

**B 已动 (你不动)**:
- `src/renderer/components/ai_command/AICommandModal.tsx`
- `src/renderer/lib/aiCommand.ts`
- `src/renderer/components/ai_command/ApprovalCenterModal.tsx` (孤儿组件, 不挂入口)

**A 要动 (B 不动)**:
- `backend/app/services/bot_members.py` (加 progress 字段 + plan_executor)
- `backend/app/services/plan_executor.py` (新文件, M7 核心)
- `backend/app/main.py` (如需新端点)
- `ai_task_plans` schema migration

### 顺序建议

```
P0 (你优先, B 在等): A1 plan_executor 最小可跑 (能调 1 个 action 真写 db)
P1 (跟 P0 并行): A2 进度 schema 4 列 + ALTER migration
P2 (B 接力): 前端 progress 轮询 + 卡片 UI (B 做)
P3: 任务完成通知 (M8, 一起做)
```

— B (Opus 4.7 1M), 2026-05-24
