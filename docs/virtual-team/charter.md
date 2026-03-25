# Virtual Team Charter

## Mission

把当前仓库升级为一个 **Codex-native 虚拟项目组**：
- 1 个主编排者
- 多个真实软件岗位长期协作
- 先审计，再看外部成熟模式，再辩论，再收敛，再实现，再挑战，再发布

目标不是生成更多文档，而是：
1. 自动审计现状
2. 自动吸收外部成熟经验
3. 自动辩论方案
4. 自动收敛规格
5. 自动实施最小改动
6. 自动反驳与回归验证
7. 自动把结果沉淀到 docs

## Discussion Visibility

虚拟项目组的讨论过程默认对人可见，至少要落到：
- `reality-audit.md`
- `external-pattern-scans.md`
- `strategy-debates.md`
- `working-session-log.md`

其中：
- 前三者记录“结论型过程”
- `working-session-log.md` 记录“谁说了什么、冲突是什么、为什么这样裁决”

## Scope

当前一期只围绕：
- 日历与任务判断系统 P0

不扩散到全系统，不先重写客户工作台，不先重做组织系统。

## Roles

- `program_director`
  - 主编排者，维护 docs/virtual-team 和 release gate
- `product_manager`
  - 定义问题、价值、边界、优先级与验收标准
- `product_operations_manager`
  - 维护协作节奏、依赖、文档和交接机制
- `ux_researcher`
  - 研究 CEO / 部门负责人 / 员工的真实工作流与认知成本
- `interaction_designer`
  - 负责交互状态、点击反馈、保存与展开行为
- `information_architect`
  - 负责信息分层、标签、导航和内容归属
- `staff_software_engineer`
  - 做最小可辩护实现
- `data_engineer`
  - 盯真源、写回、同步、迁移和 backfill
- `analytics_engineer`
  - 盯 judgment contract、coverage / confidence / degrade / ranking
- `relevance_engineer`
  - 盯证据引擎、chunk、召回、rerank、citation
- `platform_engineer`
  - 盯 Electron、启动链、打包、安装、数据目录
- `qa_engineer`
  - 盯手工回归、阻塞问题和 release gate
- `competitive_intelligence_analyst`
  - 盯外部成熟模式、产品先例和团队运作经验

## Seven Fixed Loops

### Loop 1: Reality Audit
- 拉起 `data_engineer`
- 拉起 `information_architect`
- 需要时拉起 `platform_engineer`
- 收口到 `reality-audit.md`

### Loop 2: Human Workflow Review
- 拉起 `product_manager`
- 拉起 `ux_researcher`
- 拉起 `interaction_designer`
- 把“给谁用、怎么用、哪里卡、哪些该自动生成”收口到 `reality-audit.md`

### Loop 3: External Pattern Scan
- 拉起 `competitive_intelligence_analyst`
- 拉起 `product_operations_manager`
- 需要时拉起 `relevance_engineer`
- 收口到 `external-pattern-scans.md`

### Loop 4: Strategy Debate
- 拉起 `product_manager`
- 拉起 `data_engineer`
- 拉起 `analytics_engineer`
- 拉起 `interaction_designer`
- 必须回应审计结果和外部模式，不允许各写各的
- 收口到 `strategy-debates.md`

### Loop 5: Spec Convergence
- `program_director` 联合 `product_operations_manager`
- 更新 `active-plan.md`
- 没有关键冲突收敛，不允许实现

### Loop 6: Implementation Sprint
- 拉起 `staff_software_engineer`
- 必要时联合：
  - `data_engineer`
  - `platform_engineer`
  - `relevance_engineer`
  - `interaction_designer`
- 只实现本轮批准项

### Loop 7: QA & Release Gate
- 拉起 `qa_engineer`
- 拉起 `platform_engineer`
- 需要时拉起 `product_manager`
- 更新 `release-gates.md`
- 明确通过项、阻塞项、下一轮范围

## Hard Constraints

- 不新造业务真源
- 不破坏现有数据边界
- 不要求用户新增大量表单
- 不允许“结构问题”被包装成“业务风险”
- 不允许保留前后端两套判断系统
- 不允许在证据不足时强判断

## First Practical Principle

当前仓库不是从零开始。  
当前任务不是再发明一套新判断系统，而是把已经存在的：
- `memory foundation`
- `event line bundle`
- `event line judgment`
- `task context preview`
- `weekly review analysis`
- `strategic cockpit`

收口成更稳定、更可信、更一致的一条链。

## Reference Model

当前岗位体系参考的是成熟的软件团队分工，而不是纯 AI 抽象人格：
- Agency-Agents 的“岗位说明书式”组织方法
- Atlassian 对 Product Manager / Product Operations 的定义
- IBM 对 Data Engineer / Analytics Engineer / Platform Engineer 的定义
- Interaction Design Foundation 对 UX Research / Interaction Design / Information Architecture 的定义
- OpenSource Connections 对 Relevance Engineer 的定义
- BrowserStack 对 QA 的定义
