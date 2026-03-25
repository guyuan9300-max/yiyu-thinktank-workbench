# Strategy Debates v2

## Debate Scope

本轮辩论有两层：
1. 任务与周判断 P0 仍应走哪条技术路线
2. 虚拟项目组应采用抽象方法论角色，还是现实软件岗位

## Debate A: Judgment System Route

### Route A1: 保守增量路线

保留现有对象：
- `EventLineContextBundleRecord`
- `EventLineJudgmentRecord`
- `TaskContextPreviewRecord`
- `WeeklyReviewAnalysisRecord`
- `EventLineSummaryCardRecord`
- `ManagementSignalCardRecord`

核心做法：
- 不新建第二套 judgment schema
- 新增一个窄的后端“统一判断装配层”，把任务详情和周判断都改成先取同一 bundle/judgment，再分发到各页面
- 把低完整度输出统一收口到：
  - `safeOutputMode`
  - `predictionReadiness`
  - `missingSlots / missingReasons`
  - `backgroundSources`
- 对附件、会议只补最小摘要预处理，不重做知识引擎

优点：
- 最小改动
- 双真源风险最低
- 易于在现有仓库快速验证

风险：
- 需要忍受一段时间的旧字段共存

### Route A2: 稍进取路线

核心做法：
- 在现有对象之上再引入一个新的 `JudgmentEnvelope / SignalBoard` 统一读模型
- 让任务详情、周判断、战略陪伴都只吃这个 envelope
- 旧对象退居构建层

优点：
- 表面统一更强

风险：
- 极易形成新双真源
- 当前没有足够证据证明现有 objects 无法承载 P0

### 技术路线裁决

推荐 **Route A1：保守增量路线**。

理由：
1. 当前仓库已存在足够完整的 objects  
2. P0 目标是收口可信判断，不是做一套更漂亮的新架构  
3. Route A2 在当前阶段极易制造新双真源  

## Debate B: Team Role Model

### Route B1: 继续使用抽象方法论角色

保留：
- `reality_auditor`
- `source_of_truth_guard`
- `strategy_debater`
- `judgment_architect`
- `ui_workbench_designer`
- `implementation_worker`
- `challenge_reviewer`

优点：
- 方法论表达清楚
- 与第一版 docs 一致

缺点：
- 岗位不够真实，容易变成“观点角色”
- 人类工作流、信息结构、平台稳定性、外部模式研究都没有明确 owner
- 不利于长期积累与训练

### Route B2: 改成真实软件团队岗位

保留：
- `program_director`

替换为：
- `product_manager`
- `product_operations_manager`
- `ux_researcher`
- `interaction_designer`
- `information_architect`
- `staff_software_engineer`
- `data_engineer`
- `analytics_engineer`
- `relevance_engineer`
- `platform_engineer`
- `qa_engineer`
- `competitive_intelligence_analyst`

优点：
- 职责贴近真实软件团队
- 对“人 / 数据 / 判断 / 运行 / 外部模式”都有明确 owner
- 更容易把外部成熟经验吸收到当前仓库
- 与 Agency-Agents 的启发一致：角色是岗位，不是人格

缺点：
- 需要迁移现有 agent 配置和章程
- 早期会多一个“角色重构”的过渡轮次

### 角色路线裁决

推荐 **Route B2：真实软件岗位**。

理由：
1. 当前软件已经是长期演进的桌面工作系统  
2. 真实岗位比抽象角色更利于长期分工、回路协作和训练数据积累  
3. 用户明确要求增加“外部成熟模式扫描”能力，抽象角色体系里没有明确 owner  

### 放弃 Route B1 的理由

- 角色不够具体
- 无法明确回答“谁该为这类问题负责”
- 不利于把外部模式研究变成固定回路

## Combined Recommendation

当前虚拟项目组应采用以下组合：
- 技术路线：**保守增量路线**
- 团队角色：**真实软件岗位**

也就是：
- 不新造第二 judgment 真源
- 不继续沿用抽象方法论角色
- 用真实岗位围绕现有对象、现有页面和现有后端链继续收口

## Milestones

### M0. Team Model Refactor
- 角色迁移到真实软件岗位
- 外部模式扫描文档落地
- 新 loops 写入 charter

### M1. Truth & Contract
- 明确现有 truth table / truth object
- 固定 judgment contract 字段
- 标记旧 heuristics 清单

### M2. Unified Task/Review Pipe
- 任务详情 AI 面板与周判断共用同一 bundle + judgment 生成链
- 统一降级规则

### M3. First Screen Refit
- 顶部判断状态条
- 降级处理区
- 信号卡前置
- 证据抽屉与动作卡

### M4. QA & Release Gate
- 逐项检查：
  - 是否仍双真源
  - 是否仍旧 heuristics 主导
  - 是否证据不足强判断
  - 是否角色分工已真正落地
