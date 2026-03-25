# Working Session Log

> 这份文档记录虚拟项目组的真实讨论过程，不只记录结论。
> 每一轮尽量写清：
> - 谁参与
> - 各自立场
> - 冲突点
> - 裁决
> - 下一步

---

## Session 001

### Topic

把虚拟项目组从抽象方法论角色，重构成真实软件岗位，并决定是否把“外部成熟模式扫描”纳入固定回路。

### Participants

- `program_director`
- `product_manager`
- `product_operations_manager`
- `ux_researcher`
- `interaction_designer`
- `information_architect`
- `data_engineer`
- `analytics_engineer`
- `relevance_engineer`
- `platform_engineer`
- `qa_engineer`
- `competitive_intelligence_analyst`

### Main Conflict

1. 继续使用抽象方法论角色，还是改成真实软件岗位。
2. 外部成熟模式扫描，应该是临时辅助动作，还是固定回路。

### Key Positions

- `product_manager`
  - 需要一个明确负责“这功能给谁用、为什么值得做、边界在哪”的岗位。
- `ux_researcher`
  - 需要固定有人回答“这一步是不是用户真的会做，能不能让系统先生成再让人确认”。
- `interaction_designer`
  - 任务卡展开、周复盘保存、状态切换等问题都不能靠抽象岗位顺手兼任。
- `information_architect`
  - 需要明确收口“背景 / 证据 / 记忆 / 判断 / 动作”的信息边界。
- `data_engineer`
  - 必须由真实数据岗位负责真源、写回、同步和 schema 演进。
- `analytics_engineer`
  - 不再用抽象 judgment 角色，改成统一 judgment contract 的真实分析岗位。
- `relevance_engineer`
  - 证据召回、citation 解释、背景 lane 与证据 lane 边界需要专岗。
- `platform_engineer`
  - 桌面软件启动、白屏、安装和数据目录稳定性必须有长期 owner。
- `qa_engineer`
  - 需要有人固定挑战“代码逻辑与实际点击体验不一致”的问题。
- `product_operations_manager`
  - 负责节奏、依赖、文档和 gate hygiene，而不是抽象讨论。
- `competitive_intelligence_analyst`
  - 固定扫描外部成熟模式，不再把“上网取经”当临时动作。

### Decision

- 保留 `program_director`。
- 其余长期角色改成真实软件岗位。
- 固定加入 `competitive_intelligence_analyst`。
- 把“外部成熟模式扫描”写入固定 loop。

### Artifacts Produced

- `.codex/config.toml`
- `.codex/agents/*.toml`
- `AGENTS.md`
- `docs/virtual-team/charter.md`
- `docs/virtual-team/reality-audit.md`
- `docs/virtual-team/external-pattern-scans.md`
- `docs/virtual-team/strategy-debates.md`
- `docs/virtual-team/active-plan.md`
- `docs/virtual-team/release-gates.md`

### Next Step

- 以“日历与任务判断系统”为主题进入 Session 002。
- 由 `product_manager + ux_researcher + interaction_designer` 先盘关键工作流与交互阻力。
- 由 `competitive_intelligence_analyst + product_operations_manager` 补第一轮外部模式对标。
- 再由 `program_director` 收口下一轮 P0 范围。

---

## Session 002

### Topic

日历与任务判断系统：关键人类工作流、交互阻力、外部成熟模式第一轮对标。

### Participants

- `program_director`
- `product_manager`
- `product_operations_manager`
- `ux_researcher`
- `interaction_designer`
- `competitive_intelligence_analyst`

### Inputs Reviewed

真实代码与页面：
- `src/renderer/App.tsx`
- `src/renderer/components/tasks/*`
- `src/shared/types.ts`
- `backend/app/models.py`
- `backend/app/main.py`
- `backend/app/services/review_analysis.py`
- `backend/app/services/review_rollup.py`
- `backend/app/services/memory_foundation.py`
- `cloud_backend/app/models.py`

外部模式：
- Linear
- Jira
- Asana
- Sunsama
- Akiflow
- Motion
- Fellow
- 15Five

### Workflow A Summary

`product_manager + ux_researcher + interaction_designer` 收口出的共识：
- 当前模块真实高价值工作流不是“看 AI 复盘”，而是：
  1. 收任务
  2. 确认结构归属
  3. 承接进日历
  4. 会后转动作
  5. 发起支持
  6. 单项复盘
  7. 部门介入
  8. 机构上提
- 当前最大页面问题不是美观，而是 collect 页把录入、判断、总结、动作混在一起。
- 当前最大信任问题不是措辞，而是任务卡 AI 面板和周判断没有稳定共用一条 judgment chain。

### Workflow B Summary

`competitive_intelligence_analyst + product_operations_manager` 收口出的共识：
- 最值得借的是模式，不是界面：
  - Linear：真正的优先级视图
  - Sunsama：weekly ritual
  - Akiflow：inbox -> planning -> calendar
  - Fellow：meeting -> action -> carry forward
  - 15Five：check-in -> manager intervention
- 最不能误抄的是：
  - 普通任务软件
  - 单纯仪表盘
  - 长篇 AI 报告页
  - 重流程管理后台

### Round 1 Cross-Questioning

#### Challenge A
发起：`competitive_intelligence_analyst`

质疑：
- Workflow A 是否只看到了现状页面，没有看到外部成熟产品里最关键的 ritual 和 adoption 设计？

回应：
- 接受这个质疑。
- 因此 Session 002 的结论不只写页面问题，还把：
  - 日历承接 ritual
  - 周复盘 ritual
  - meeting-to-action closure
  一并纳入 P0/P1 视角。

#### Challenge B
发起：`product_operations_manager`

质疑：
- 当前交互即使分析更强，也不代表人会形成更好的工作习惯。真正妨碍 adoption 的是什么？

回应：
- 当前 adoption 最大阻力不是功能少，而是：
  - 首屏不是“现在该做什么”
  - 会后动作不是自然闭环
  - 日历不是 judgment system 的组成部分
  - “未纳入判断 / 降级处理”不可见

### Decision

本轮裁决：
- 日历与任务系统当前最需要修的，不是继续做更长的 AI 报告页。
- 先修：
  1. 共享 judgment chain
  2. judgment state visibility
  3. action closure
  4. calendar gap signals

### Artifacts Produced

- `docs/session-002/task-calendar-human-workflows-and-frictions.md`
- `docs/session-002/task-calendar-benchmark-round1.md`
- `docs/session-002/task-calendar-synthesis.md`

### Next Step

下一轮进入 Session 003 前，需要先围绕以下 P0 收口：
1. 顶部判断状态条
2. 未纳入判断 / 降级处理区
3. 收件 / 承接 / 上历 分层
4. 单项复盘优先、长文后置
5. 动作卡前置闭环

---

## Session 003

### Topic

日历与任务判断系统：P0 实现前规格收口。

### Participants

- `program_director`
- `data_engineer`
- `analytics_engineer`
- `relevance_engineer`
- `product_manager`
- `ux_researcher`
- `interaction_designer`
- `information_architect`
- `qa_engineer`
- `product_operations_manager`

### Inputs Reviewed

- Session 002 三份文档
- 当前 `active-plan.md`
- 真实 judgment chain 对象与任务页面实现
- 关键代码：
  - `backend/app/main.py`
  - `backend/app/models.py`
  - `backend/app/services/memory_foundation.py`
  - `backend/app/services/review_analysis.py`
  - `backend/app/services/review_rollup.py`
  - `src/renderer/components/tasks/TaskOrgContextPanel.tsx`
  - `src/renderer/components/tasks/WeeklyReviewAnalysisPanel.tsx`
  - `src/renderer/components/tasks/WeeklyReviewSummaryPanel.tsx`

### Main Conflict

1. P0 该不该再引入一个新的 judgment 聚合对象。
2. 任务详情 AI 面板是否继续允许前端 heuristics 主导。
3. 首屏应先改页面骨架还是先收 contract。

### Key Positions

- `data_engineer`
  - 不能再包新的持久化 judgment 真源；应继续以当前后端对象为主真源。
- `analytics_engineer`
  - 必须统一 `coverageScore / confidenceScore / safeOutputMode / judgmentVersion / bundleFingerprint` 这套合同。
- `relevance_engineer`
  - 证据不足时必须显式降级，不能继续让前端拼出看似完整的业务判断。
- `product_manager`
  - P0 不是继续扩分析，而是把首屏改成判断操作台。
- `ux_researcher`
  - 个人与 leader 看到的排序必须不同，否则 manager 仍然要自己从全量任务里找异常。
- `interaction_designer`
  - 首屏必须前置状态条、信号卡、动作卡和降级区，不能再以长解释为主。
- `qa_engineer`
  - 任何 P0 实现都必须证明不是“更会说”，而是真能形成动作闭环。
- `product_operations_manager`
  - P0 范围必须压住，只处理：状态条、角色排序、降级区、日历信号、动作卡闭环。

### Decision

- 不新增 judgment 真源。
- 先收 contract，再收首屏骨架。
- 前端 heuristics 只能保留为 fallback。
- P0 只允许处理：
  1. 首屏判断状态条
  2. 个人 / leader 排序分离
  3. 未纳入判断 / 降级处理区
  4. 日历信号条
  5. 动作卡闭环

### Artifacts Produced

- `docs/session-003/task-calendar-p0-implementation-spec.md`
- `docs/session-003/task-calendar-judgment-contract.md`
- `docs/session-003/task-calendar-release-gates.md`

### Release Gate Judgment

本轮结论是：
- Session 003 的 docs-first 规格已经齐。
- 允许进入“最小可辩护改动”的实现阶段。
- 但实现必须满足：
  - 不新造真源
- 任务详情 AI 面板与周判断共享同一条 judgment chain
- `TaskOrgContextPanel` heuristics 退为 fallback
- 首屏先做状态条 / 降级区 / 动作卡 / 日历信号

### User Clarification Added After Session

用户进一步明确：
- 不希望系统一打开先展示大量“缺失项”
- 不希望因为少了若干增强资料就“无法干活”
- 任务与日历判断系统必须优先发挥 AI 的综合计算能力

用户明确的最小必需输入集是：
1. `整个项目 / 业务的资料与核心介绍`
2. `整个部门 / 整个机构的季度主要计划`
3. `任务标题`
4. `任务说明`
5. `任务复盘资料`

裁决补充：
- Session 003 的 P0 继续保留“边界可见”，但不再把“未纳入判断 / 降级处理”做成首屏主角。
- 以后端和前端的共同口径为准：
  - 先基于最小必需输入集给出保守判断
  - 可选增强输入缺失时，默认不阻塞结果
  - 缺口只在当前判断明显不可信或当前动作无法闭环时前置

### Next Step

下一轮进入实现批次，顺序固定为：
1. 抽出任务详情与周判断共用的 judgment 装配入口
2. 统一降级字段映射
3. 把 `TaskOrgContextPanel` 旧 heuristics 降为 fallback
4. 在任务与周判断 UI 上接首屏状态条 / 降级区 / 动作卡
5. 增加 calendar signal bar 的最小计算与展示
