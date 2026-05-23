# B AI 下一阶段工作报告 · 自动验收官就位

> **生成**: 2026-05-23 19:55
> **阶段**: 顾源源 5/23 19:00 角色钦定 → B 7 件交付完成
> **作用**: 给顾源源 5 分钟一眼图谱, 不写感受

---

## 1 · 本阶段 B 做了什么

### 文档 (6 份)

| 文件 | 含义 |
|---|---|
| `docs/B_AI_EVAL_STANDARD_V1.md` | 评估标准 v1 (3 层证据 / R2/R4-P0/V3.0 评分公式 / 14 功能 ABCDE / 硬门槛 / 通过 vs 实验能力 / 必带 6 件 / blocked_by_X 规则) |
| `docs/B_AI_GOLDEN_TEST_PACK.md` | 7 类样本规格 + 期望调用模块 + 期望 evidence + 期望成果包 |
| `docs/B_AI_EVAL_BASELINE_REPORT.md` | B2 跑出的基线报告 (覆盖最新) |
| `docs/B_AI_V3_DRYRUN_REPORT.md` | B3 V3.0 L1-L4 dry-run 报告 (覆盖最新) |
| `docs/B_AI_EXTERNAL_AGENT_DRYRUN_CONTRACT.md` | 6 命令外置 Agent 契约 (dry-run only) |
| `docs/B_AI_PROGRESS_RADAR.md` | 进展雷达图 (持续追踪, 30 min 更新一次) |

### 脚本 (2 个, 4 模式)

| 文件 | 模式 |
|---|---|
| `scripts/run_b_eval_baseline.py` | 4 模式: `capability-probe` (L1 endpoint smoke) / `api-contract` (L1 response 字段) / `db-diff` (L2 V2.1 lab db) / `ui-checklist` (L3 人工) |
| `scripts/run_v3_ai_driven_dryrun_eval.py` | L1-L4 分层 dry-run (L1 单链路 / L2 多模块 / L3 主动缺口 / L4 Goal-Plan-Run), blocked_by_A 时不挂死 |

### 测试样本 (7 类, fixtures/golden/)

`meeting_mingyuan.txt` / `qa_10.txt` / `files_20.txt` / `weekly_review.txt` / `task_create.txt` / `intelligence_brand.txt` / `method_card.txt` + `README.md`.

### 总结 (本文)

`docs/B_AI_NEXT_STAGE_WORK_REPORT.md`

### npm 命令 (集成, 顾源源可一键跑)

```
npm run db:init:lab          16 张表 ensure
npm run db:check:lab         只看不建
npm run eval:r2              R2 真测试 (日慈 + CFFC)
npm run eval:v30:ai-driven   V3.0 100 分制 + 7 维度 + 10 硬门槛
```

(B `run_b_eval_baseline.py` / `run_v3_ai_driven_dryrun_eval.py` 待加 npm alias, 下一 commit)

---

## 2 · 当前 3 大分数

| 指标 | 分 / 状态 | 数据来源 | 备注 |
|---|---|---|---|
| **R4 用户可感知分** | **90 / 100 (A 自评)** | A 285e185 R4 复测报告 | ⚠️ 待 B 用 Golden Pack 独立复验 |
| **数据库—功能深度联动分** | **90 / 100 (A 自评)** | A 5fefcf3 → 285e185 | ⚠️ 待 B 用 Golden Pack 独立复验 |
| **V3.0 AI 驱动软件做事分** | **56.5 / 100 (B 真测)** | B 748c833 V2.1 lab db | 🔴 差 23.5 |

→ A 自评跟 B 独立分**差 33.5 分**. B 独立复验是下阶段重点.

---

## 3 · L1-L4 当前状态

| 层 | 状态 | 关键证据 | 阻塞 |
|---|---|---|---|
| **L1 单链路处理** | ✅ **通** | facts +5 / risks +2 / commit +2 / clarif +1 / approval +2 (V2.1 lab db 真涨) | - |
| **L2 多模块调度** | 🔴 **不通** | 调用 1 模块 (目标 ≥ 4) | 5 endpoint 缺 (合同/模板/品牌/会谈提纲权限/品牌建议) |
| **L3 主动缺口发现** | 🔴 **不通** | GET /data-gaps endpoint 404 + 无 data_gaps 派生 | data-gaps endpoint + DataGapCompensator endpoint |
| **L4 Goal-Plan-Run** | 🔴 **不通** | 0/3 endpoint 通 | POST /agent/plan + /agent/run + GET /agent/status 全缺 |

→ **通过层数 1/4**. 距离 "AI 全面操控软件" 还差 3 层.

---

## 4 · 当前能不等 A 做的事 是否完成

| 任务 | 完成 | 输出 |
|---|---|---|
| **B0 评估标准 v1** | ✅ | `docs/B_AI_EVAL_STANDARD_V1.md` |
| **B1 Golden Test Pack** | ✅ | `fixtures/golden/* × 7` + `docs/B_AI_GOLDEN_TEST_PACK.md` |
| **B2 总入口脚本 (4 模式)** | ✅ | `scripts/run_b_eval_baseline.py` |
| **B3 V3.0 dry-run (L1-L4)** | ✅ | `scripts/run_v3_ai_driven_dryrun_eval.py` |
| **B4 外置 Agent 契约** | ✅ | `docs/B_AI_EXTERNAL_AGENT_DRYRUN_CONTRACT.md` |
| **B5 进展雷达** | ✅ | `docs/B_AI_PROGRESS_RADAR.md` |
| **总结报告** | ✅ | `docs/B_AI_NEXT_STAGE_WORK_REPORT.md` (本文) |

→ **7/7 ✅**. 当前不依赖 A 的任务全部完成. blocked_by_B = 0.

---

## 5 · 等 A 的清单 (按优先级)

| # | A 要补什么 | 用户影响 | 不补会怎样 |
|---|---|---|---|
| P0-1 | 暴露 `POST /api/v1/contracts/draft` | 用户不能让 AI 写合同草稿 | V3.0 D3 永远缺合同, 不可能 ≥ 80 |
| P0-2 | 暴露 `POST /api/v1/templates/generate` (理事会说明等) | 用户不能让 AI 生成理事会简版 | V3.0 D3 永远缺模板 |
| P0-3 | 修 `strategic-cockpit/meeting-pack` 403 权限 | 用户不能让 AI 生成会谈提纲 | V3.0 D3 永远缺会谈提纲 |
| P0-4 | 暴露 `GET /api/v1/clients/{id}/data-gaps` + 接 DataGapCompensator | 用户看不到"我还缺什么" | V3.0 L3 永远不通 |
| P1-5 | narrative_generator prompt 真用 R4 字段 (战略陪伴 R4-P0 P0-4) | 战略陪伴看不到合同/历史/data_gap | R4 90 真分含水分 |
| P1-6 | 4 badge 挂客户工作台头部 + smart_import + 战略陪伴 (R4-P0 前端) | 用户看不到 待澄清/待审批/文件身份/合同结构 | R4 90 用户层面感知不到 |
| P1-7 | 暴露 `GET /api/v1/agent-run-logs` | 用户看不到 AI 调用历史 | 透明度不够 |
| P2-8 | 暴露 `POST /api/v1/agent/plan` + `/run` + `/status` (Goal-Plan-Run V3.0 P1) | 用户不能给 AI 复杂目标自主拆解 | V3.0 L4 永远不通 |

---

## 6 · 下一轮建议 (前 3)

```
1 (顾源源拍) 接受 A 90 自评当 V2.1 RC 真合格证明? 还是等 B Golden Pack 独立复验?
   B 推荐: 接受 A 90 为 "实验能力", V2.1 RC 真合格要等 B 14 功能逐项复验
   工作量: B 2-3h (跑 Golden Pack × 14 功能, 出独立分)

2 (A 干) P0-1 暴露 contracts/draft (B 推荐第一个)
   原因: 顾源源 V3.0 样本 1 最重要的成果, 用户感知最强
   工作量: A 1-2h (复用 templates/generate 内部模板系统也行)

3 (顾源源截) 截图 4 项 L3 verify
   - 工作台 evidence 摘要框 (A 自报 P0-5 挂了)
   - proposed_clarifications 列表 + 用户能点击采纳
   - 待审批列表 + 用户能点击通过/拒绝
   - smart_import 文件身份 badge (待 A 挂)
   存到 `docs/screenshots/r4_p0/<timestamp>/<id>.png`
   工作量: 顾源源 10-15 min 截图
```

---

## 7 · 角色转变总结

```
旧: B = 评估官 (R2/R3/R4-P0/V3.0 跑分)
新: B = 自动验收官 (持续告诉顾源源 "车跑到哪一层")

不变:
  - 不替 A 写复杂业务
  - 数据源强制 V2.1 lab db (拒绝 dogfood_real)
  - 报告必带 commit / 端口 / db / 客户 / 输入 / 输出

新增:
  - 3 层证据分清 (L1 API / L2 DB / L3 UI)
  - L1-L4 能力分层
  - blocked_by_A / blocked_by_B / blocked_by_user 明确标
  - Golden Test Pack 固定输入, 保证可重复
  - 不为过线改标准
  - dry-run 评估器: 缺 endpoint 不挂死, 标 blocked_by_A
  - 进展雷达持续更新, 不再只输出"最终完成"
```

---

## 8 · B 不做的事 (再次重申, 防漂移)

```
不做 1: 复杂 endpoint (contracts/draft / templates/generate / agent/plan / ... 全 A 做)
不做 2: 真实写入版外置 Agent (只 dry-run)
不做 3: 把 API 字段当用户可见
不做 4: 不用 snapshot 宣告通过
不做 5: 不输出"终极通过" 报告
```

---

## 9 · B 待办 (下阶段, 不阻塞)

```
T+0     B5 进展雷达 + 总结 commit (本批)
T+1-2h  Golden Pack × 14 功能独立复验 (跟 A 41/100 / 90/100 对照)
T+0.5h  api-contract LLM 慢 timeout 修 (5s → 60s)
T+0.5h  跨客户隔离加进 V3.0 dryrun L1 (R2 沿用规则)
T+1h    桌面 17 V3.0 + 18 R4 报告同步 (顾源源拷桌面)
```

---

**Author**: AI B · 2026-05-23 19:55
**关联**:
- 顾源源 5/23 19:00 任务书 (B 角色钦定)
- A 285e185 R4 复测 90/100 (A 自评待 B 复验)
- B 748c833 V3.0 baseline 56.5/100 (B 独立)
- inbox-A.md 通知 A (下一 commit)
