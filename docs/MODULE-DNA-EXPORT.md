# 益语智库 · 软件 DNA 沉淀

> **来源**: Claude Code 主线 `claude-code:data-center-relationship-graph`
> **生成时间**: 2026-05-16 12:22
> **模块数**: 20
> **entries 总数**: 116
> **其中用户原话引用 ⭐**: 22

本文档是 module DNA 数据库的完整 dump。
⭐ = 顾源源原话引用 (confidence=1.0)。  ◯ = AI 整理 (confidence 0.7-0.95)。

---

# L1 软件级

## 益语智库
**模块 id**: `software:root`
**一句话定位**: 给公益咨询机构用的'超级员工'，站在战略层面陪伴组织发展
**entries 数**: 27

### 目的 / 北极星
- ⭐ 这一个软件就像一个超级员工，他是站在战略层面的高度和完整度去陪伴这个组织发展

### 服务谁
- ◯ 公益咨询机构。当前实际组织 = 益语智库 (3 部门: 合作发展部 / 战略发展部 / 技术创新部)，由顾源源任 CEO/admin，同时也是战略发展部部门负责人。服务对象包括 (a) 益语智库自身的顾问+CEO+部门领导+员工，(b) 益语智库陪伴的公益客户 (如日慈基金会、为爱黔行公益服务中心等)。

### 设计原则
- ⭐ 「用户能感受到的功能价值」优先原则 (顾源源原话): '本周客户脉搏不要显示出来, 对于人类用户来讲意义并不是很大'。→ 所有功能必须问: 这是不是用户**做事时**能感受到的价值? 如果是'AI 后台知道很多东西的可见化', 那它属于澄清页 / 健康度页 / 二级入口, 不属于用户主操作面板。
- ⭐ 长程跟踪原则 (顾源源原话强调): 数据中心从第一天起按 3 年时间窗设计。snapshot 表不做'季度归档', 而是无限累积 + 分区索引优化; thread 状态不做'completed 后隐藏', 支持已完成态的可查询、可复盘; 长寿命主线(>1 年)触发'阶段性滚动摘要'接口 (留接口, Phase 3 实施)。
- ⭐ 事实澄清模块的产品哲学 (顾源源原话): '事实澄清应该是基于一条主线 (commitment) 来澄清。之前事实澄清这个模块我没有继续往下做的原因就是因为他不是在澄清一条主线，而是在澄清所有的信息混杂在一起。这第一是没法澄清，第二是澄清也没有意义。如果在澄清一条主线，它就很像是这一个项目是我在负责的，然后有一个同事向我问这个项目周期是几月几号到几月几号啊? 我跟他澄清，这才有意义。'
- ⭐ 数据中心定位 (顾源源原话): '你做的东西就是所有判断的背景'。工作台模块 = '问什么找什么' (用户主动搜文档); 数据中心 = 'AI 心里清楚整个客户的来龙去脉' (背景知识引擎，被动驱动一切判断)。当战略陪伴/周复盘/任务智能简报说出业务判断时，它是从数据中心读的背景，不是它现场推理。
- ⭐ 客户 DNA 重新定义 (顾源源原话): '我觉得现在不是有一个 DNA 吗? 那个 DNA 其实是把一些客户的资料放进 AI，让 AI 来写的。但是实际上我们现在做的就是在数据中心形成一个客户的 DNA，非常详尽的资料大全'。→ DNA = 数据中心持续沉淀的、详尽的、可追溯的资料大全; 不是临时 AI 摘要。
- ⭐ 优化方向公式: 场景优化价值 = 场景需求频次 × 用户对价值的感知。频次档: 每天=5 / 每周 1-2 次=4 / 每月 1-2 次=3 / 季度=2 / 偶尔=1。价值感知档: 强(无可替代)=5 / 中(有用比之前好)=3 / 弱(看起来还行)=1。总分 1-25。**硬约束: 总分 ≥ 12 的场景才进硬交付范围**。
  - tags: formula
- ◯ 客户字典 vs 业务主线 - 两层抽象 (顾源源原话整理): **实体层 (客户字典)** = 名字/时间/金额/机构等碎片 (例: '5/15', '庆华', '100w'); **关系层 (业务主线)** = 多个实体串成一件完整的事 (例: '庆华向日慈承诺 5/15 前交付教师赋能报告')。两者都是从信息里抓结构化片段, 但层级不同。**事实澄清模块的产品错误**: 之前在实体层做澄清, 必然混乱; 应改为'围绕一条主线逐维度澄清'。
- ◯ 30B 模型必须跨功能复用 (来自 user memory): qwen3-vl:32b 覆盖所有图→文需求 (OCR / 截图说明 / 图表理解), 禁止为单一功能新装模型。由此推论: 凡是 LLM 调用应优先考虑能否复用已有的 30B 模型。
  - tags: from-memory, constraint
- ◯ Karpathy LLM Wiki 三层架构 (整次改造灵感): Layer 1 Raw Evidence (原始证据 - 不可改) / Layer 2 Compiled Knowledge (压缩知识 - LLM 解读的中间产物, 可重生成) / Layer 3 Audit (审计 - 知识来源可钻取回 Layer 1)。对应到益语智库 = 原文档/任务/对话 (L1) → 关系网 + 模块 DNA (L2) → 每个 AI 输出可钻取到原始证据 (L3)。Karpathy 启示 #11 '固定知识页模板' 直接对应'客户关系书 8 段' 设计。
  - tags: architecture, philosophy
- ◯ 表面平等设计 (来自 user memory): 界面对所有用户视觉一致，但后台算法可给 CEO/leader 加权 (leader 权重隐式生效)。
- ◯ 无感学习 (来自 user memory): 沉淀/学习不能给用户加动作，全自动; 用户控制权放在'事后删'，不放在'事前选'。
- ◯ AI 视角 vs 用户视角翻转 (顾源源原话整理): **功能价值 = AI 视角** (我[AI]能做什么、我卡在哪里、我有什么数据); **业务价值 = 用户视角** (你[用户]的事卡在哪里、为什么卡、下一步往哪走)。中间的支点 = AI 知不知道'你在做的这件事是什么' (业务主线/项目主线)。**所有 AI 表达都必须从用户视角说话**，禁止'我[AI]卡在没数据上'这类句式。

### 反模式 (不做什么)
- ⭐ 造车比喻 (顾源源原话): '我们不需要造出能 3 个轮子跑的汽车，我们需要让用户更加安全和更加舒适地驾驶汽车。我这辆车，过山坡、过草地、过石子路都如履平地，这是实用价值，因为舒适感是大家的需求。所以我们考虑的场景都应该是: 功能价值 × 替客户解决的问题 × 这个问题出现的频次 × 这个问题给客户造成的困扰程度。'
  - tags: metaphor
- ◯ 不允许的写法 (基于顾源源多次反馈): (a) AI 视角废话 - '当前没有特别突出的阻塞, 但仍需盯住推进收束' (本周概览 next_step 字段曾大量出现); (b) 模板化 next_step - '下一步动作: 根据最近会议飞书会议按钮联调形成明确后续安排' (机器人语气, 跟实际业务无关); (c) 炫耀后台 - 把后台知道的所有指标都堆在前台 hero 区。**所有 AI 文本生成必须在用户视角 + 业务语言**, 没真实业务数据时**留空**, 不生成废话。
  - tags: anti-pattern

### 工作流 / 用户判断方式
- ⭐ **实施节奏铁律 (顾源源多次强调)**: 功能反推 → UI 真实呈现 → 用户判断方向 → 然后再讨论细节。不允许停留在'纸上反推方案'阶段; 用户原话: '在你写的功能正在软件上通过判断呈现出文字给用户提供价值之前, 我都没有办法判断你的功能到底对不对, 我只能判断这个方向是对的'。→ 每次重大设计文档审到 v0.3 后, **必须立刻做出 UI demo** 让用户判断实际呈现。
  - tags: principle, process
- ⭐ 前后台分离 (顾源源原话): '你有很多东西它是在后台的，它不需要把你后台知道的所有东西都吐在前台'。→ **以客户可以感受到的功能价值优先**，不炫耀后台知道多少。详细数据通过二级入口/澄清页查看，主页面只放 3 区块或核心数字。
- ⭐ 用户判断模式 (顾源源原话): '用户只能判断方向，不能判断功能细节。必须用 UI 真实呈现才能判断对错。在你写的功能正在软件上通过判断呈现出文字给用户提供价值，到这一步之前，我都没有办法判断你的这个功能到底对不对，我只能判断这个方向是对的'。→ **设计文档审到方向层就行，细节必须做出 UI 后再让用户判断**。
- ◯ 前后台分离实例 (战略陪伴客户主页 v1): **前台 (用户主操作面板) 只放 3 个区块**: 本周新动态 / 你接下来要做 / 当前卡点。**后台还知道的事** (治理结构 / 战略定位 / 业务结构 / 花名册全员 / 风险信号汇总 / 主线全景 / 合作合同细节 等) → 全部塞到底部 [查看完整 DNA] 和 [澄清面板] 入口里。
  - tags: concrete-example

### 做出的设计决策
- ◯ Phase 1.5 软件 DNA - 跨 session 长期记忆 (2026/5/16 用户提议): 数据库表 module_definitions + module_definition_entries, 多线程联合写作不互覆盖。每个 AI 线程: ① 启动时 GET 一遍背景 ② 每轮结束 POST 沉淀 ③ 不重复问用户已澄清过的事。本机 SQLite, 未来升级云端同步。
- ◯ 数据剔除 / 纠错机制: documents 表加 misattribution_status (''/disputed/removed) + removed_reason + removed_at 字段。澄清面板内置'这份文档真的属于这个客户吗?' 操作。应用场景: 敦和基金会报告误归类到黔行 → 用户一键标 removed → 软件后续过滤掉。
- ◯ 测试数据 / AI 模拟数据治理机制 (v0.3 新增): 所有承担'生产业务'的表加 is_test_data + is_simulated 字段 (tasks / event_lines / meetings / documents / external_persons / operators)。UI 默认过滤 is_test_data=1 和 is_simulated=1, 提供'包含测试数据'切换。**当前已知脏数据**: 庆华(operator op_qh) = AI 模拟角色 / 黔行教室改造 3 个 task 是模板测试 / 90% event_line_activities 是测试附件 (smoke_att.txt / final_test.txt 等) / 敦和基金会研究报告误归类到黔行库 (应为研究素材而非合作方)。
  - tags: data-hygiene
- ◯ 三段流水线分工 (顾源源确认): 上游 = 文档分解线程 (工作台 R11.x: 解构每份文档为结构化字段 + 16 字段浅解构 + FTS 召回); 中游 = 关系网编织线程 (数据中心: 锁定关键细节 + 串成关系网 + 发现困惑 + 前台问澄清); 下游 = 业务判断模块 (战略陪伴 + 成长中心 + 任务与日程 + 客户工作台问答 + 周复盘 - 读关系网作为判断背景)。
  - tags: architecture
- ◯ 关系网 5 层结构 (顾源源确认): Layer 1 花名册 (人物 + 别名归一 + 关系) → Layer 2 事实卡片 (业务语义: 承诺/决策/风险/事实/教训/进展 + 时间锚 + 置信度) → Layer 3 项目台账 (业务主线: 5 颗粒度 + 起止 + 里程碑 + 交付物) → Layer 4 客户关系书 (自动生成的 DNA 文档 8 段) → Layer 5 引擎层 (多维投影 / 事件流 / 提醒触发 / 关系书生成 / 澄清问题生成 5 个引擎)。
  - tags: architecture

### 架构详述
- ◯ 关系网四种切面投影 (跨模块复用基础): (1) **按客户切** - 战略陪伴客户主页 / 客户关系书 / AI 问答; (2) **按部门切** - 任务与日程的本周概览 / 部门信号 / 部门周复盘; (3) **按个人切** - 成长中心能力快照 / 个人周复盘; (4) **按任务切** - 任务详情智能简报。**关系网不是单一形态, 是可被多视角投影的图**。这是 v0.3 的 5 层引擎层中 「多维投影引擎」要支撑的核心能力。
  - tags: architecture

### 历史背景 / 演化
- ◯ 数据中心改造 Phase 节奏 (v0.3 确认): **Phase 0 对齐定义** (现在): 反推 20 个场景 + 定 5 层结构 + 5 项工作台协同需求 / **Phase 1 骨架** (4-5 周): 花名册 + 主线 + 投影引擎 + 提醒引擎 / **Phase 2 血肉** (3-4 周): 事实卡片 4 标签 + 关系书 + 数据卫生清理 / **Phase 3 叙事** (3-4 周): 关系书自动生成 + 澄清面板 + 个人快照 / **Phase 4 自治** (2-3 周+): 闭环 + 每周快照 + 主动澄清。**Phase 1.5 软件 DNA** (本任务): 跨 session 长期记忆 - 与上述 Phase 并行。
  - tags: roadmap

---

# L2 模块级

## 任务与日程
**模块 id**: `module:tasks_calendar`
**父模块**: `software:root`
**一句话定位**: 任务概览中心 - 看本周做了什么、卡在哪、接下来做什么
**entries 数**: 8

### 目的 / 北极星
- ⭐ 本周的这个概览，它主要是关于任务的概览

### 边界 (做什么 / 不做什么)
- ⭐ **不显示数据中心动态/文件录入等非任务信息**。用户曾让 Claude 撤回'本周客户脉搏'区块，理由: '对于人类用户来讲意义并不是很大。我们直接可以在战略陪伴那里设计文件录入或数据中心更新的东西。'

### 做出的设计决策
- ◯ 任务智能简报 (Phase 1 规划中的子功能): 任务详情页打开时, 自动加载这条 task 的关系网背景: (a) 挂在哪条主线 + 主线推进到哪 / (b) 这条任务的客户最近发生了什么 / (c) 相关人物状态 / (d) 相关文档列表。数据源 = task → event_line → relationship_graph 投影。
  - tags: roadmap
- ◯ AI 主线聚合卡片 (weeklyMainlineCards): 由后端 AI 把本周 workItems 聚合成 3-5 条主线, 每条卡片含: 标题 + 纳入数 / 完成数 / 未完成数 + 'progressText' (本周推进) + 'nextGoalText' (下一步目标)。**已知缺陷**: 卡片不显示 owner 分布 - admin 看不出 7 项里谁完成了几项。

### 数据流
- ◯ 本周概览数据流详述: 前端调 getReviews(weekLabel) → 后端 list_reviews / → 优先调云端 GET /api/v1/reviews/dashboard?weekLabel=...&perspective=... / → reconcile_cloud_review_response_with_local_tasks (用 local_base 覆盖 workItems, 保留云端的 review note) / → augment_review_response (按 perspective 过滤 + AI 生成主线卡片)。**关键参数**: weekLabel 必须传 (不传时云端默认上一周, 是个隐藏坑)。
  - tags: architecture

### 与其他模块的协同
- ◯ 跟其他模块的具体协同: **周复盘** (任务进周复盘 workItems) / **战略陪伴** (任务挂客户主线, 显示在客户主页待办区) / **客户工作台** (任务上的附件进客户文档库) / **成长中心** (任务的 owner / 完成情况进个人能力证据)
- ◯ 数据中心 (任务关联到主线) / 周复盘 (本周任务) / 客户工作台 (任务挂客户)

### 历史背景 / 演化
- ◯ 「本周客户脉搏」区块撤回经历 (2026/5/16): Phase 1 第 2 屏曾在本周概览顶部加 ClientsPulseSection - 列出每个有动态客户的卡片(显示文档/任务/事实/卡点/逾期 5 个计数 + topSignal 一句话)。实现后用户立刻撤回, 原话: '我觉得这个对于人类用户来讲意义并不是很大。我们直接可以在战略陪伴那里设计文件录入或数据中心更新的东西。而本周的这个概览, 它主要是关于任务的概览'。**关键学习**: 本周概览 = 任务概览, 非数据中心动态; 数据中心动态归战略陪伴。组件文件 ClientsPulseSection.tsx 保留在 src/renderer/components/weekly_review/, 后端 service compute_pulse_summary_for_clients 保留, 未来给战略陪伴用。

---

## 周复盘
**模块 id**: `module:weekly_review`
**父模块**: `software:root`
**一句话定位**: 个人/部门/组织三视角的任务+主线复盘
**entries 数**: 8

### 目的 / 北极星
- ◯ 个人/部门/组织三视角的任务+主线复盘

### 边界 (做什么 / 不做什么)
- ◯ **视角切换器 3 种角色行为详述** (顾源源原话定义, 已验证代码符合): **普通员工 (employee)** - 切换器**整体隐藏**, 只显示内容 (`shouldShowReviewPerspectiveSwitch = availableReviewPerspectives.length > 1` 为 false 时); **部门领导 (department_lead)** - 显示 2 个按钮 (部门视角 + 我的视角), 部门按钮**纯按钮无下拉** (因 reviewDepartmentOptions.length <= 1); **CEO (admin)** - 显示 3 个按钮 (我的 + 部门▾ + 组织), 部门按钮**带下拉**列出所有部门, 可切换。**重合处理**: CEO 同时是某部门负责人时, admin 优先 (`_resolve_review_viewer_role` 先判 primaryRole='admin')。
  - tags: spec, verified
- ◯ Tab: 本周概览 / 事件复盘 / 部门信号。组织视角实际包含全组织成员任务 (前提是前端传 weekLabel=2026-W20 等正确参数名)。AI 主线聚合卡片当前不显示 owner 分布 (待优化)。

### 做出的设计决策
- ◯ **AI 主线聚合卡片要加 owner 分布显示** (待做, Phase 1 推荐): 当前卡片只显 标题 + 纳入数 + 完成数 + 未完成数 + AI 散文 progressText/nextGoalText。需要加 'participantBreakdown[]' = [{ownerName, completed, total}], 让 CEO 一眼看到团队分工。前端展开任务列表才能看到 owner, 一级卡片应直接暴露。
  - tags: roadmap

### 数据流
- ◯ **完整数据流** (4 步, 任一步出错都会让组织视角看起来异常): Step 1 - 前端 getReviews(weekLabel) 调本机 backend /api/v1/reviews; Step 2 - 本机调云端 GET /api/v1/reviews/dashboard?weekLabel=...&perspective=... 拿 cloud_response (含 workItems + reviewNotes); Step 3 - reconcile_cloud_review_response_with_local_tasks: 用 local_base.workItems (本机 fetch_tasks + _task_in_week) **覆盖** cloud workItems, 但保留云端的 review note (apply_overlay); Step 4 - augment_review_response: 按 perspective 调 _filter_review_items_for_perspective, organization 不过滤 / department 按部门匹配 / mine 按用户匹配。
  - tags: architecture

### 历史背景 / 演化
- ◯ **'组织视角看不到林佳维'bug 排查过程** (2026/5/16 完整记录, 第一次错判 → 真相): (1) 初判断 - 调 reviews API 返回 19 项全顾源源, 怀疑云端有 bug 把别人任务过滤; (2) 加 debug endpoint /api/v1/_debug/reviews-trace 同时看 cloud / local_base / reconciled / final 四阶段; (3) 第一次跑 - cloud (8 项) → reconcile (19 项) → final (19 项), **但 ownerName 全 None**; (4) 发现 log 代码自己 bug - taskSnapshot 是 Pydantic 不是 dict, 修复后看到真实 owner; (5) 第二次跑 不传 weekLabel - cloud 默认 W19 (上周), 林佳维任务本周才有, 自然 0; (6) 第二次跑 传 weekLabel=2026-W20 - cloud 29 项含林 3 / local_base 32 项含林 3 / final 32 项含林 3 ✅; (7) **真相**: 之前用 curl 错的参数名 ?week= (backend 接收的是 ?weekLabel=), 导致 backend 用 default current_review_week_label() 算 W20, 但云端不传时默认 W19。(8) **修正结论**: 数据没丢, 林佳维任务正确汇入组织视角; 真实问题是 'AI 主线聚合卡片不显示 owner 分布' - admin 看不出团队分工。
  - tags: debugging, narrative
- ◯ 曾验证: organization 视角下，所有组员任务 (顾源源/林佳维/乐乐/佳乐 等) 都进 workItems，但 AI 把它们聚合成 3 条主线 (益语智库平台 2.0 / 云南儿童资助报告 / 为爱黔行) 时owner 分布丢失。不是数据丢，是 UI 没暴露。

### 已知 bug 模式
- ◯ **常见参数名陷阱**: 周复盘相关 API 的周参数前端用 `weekLabel`, 后端 Query 参数也是 `weekLabel`。**不要用** `week` 这个简写, backend 收不到, 会默认 current_review_week_label()。但云端 dashboard 接口在不收到 weekLabel 时返回**上一周** (W-1) 数据, 不是当前周, 这是 by-design 还是 bug 未确认。
  - tags: pitfall

---

## 客户工作台
**模块 id**: `module:client_workspace`
**父模块**: `software:root`
**一句话定位**: 单客户的资料库 + AI 问答 - 围绕这家客户的全部信息聚合
**entries 数**: 3

### 目的 / 北极星
- ◯ 围绕单个客户的资料库 + AI 问答，搜索式入口

### 边界 (做什么 / 不做什么)
- ◯ 工作台 = '问什么找什么' (用户主动搜文档); 跟数据中心的'背景知识引擎'互补。工作台是搜索引擎; 数据中心是背景知识引擎。

### 与其他模块的协同
- ◯ 数据中心 (背景知识) / 战略陪伴 (客户主页是工作台的战略视角延伸)

---

## 成长中心
**模块 id**: `module:growth_center`
**父模块**: `software:root`
**一句话定位**: 员工能力快照 + 岗位锚点 (基于真实证据反推)
**entries 数**: 8

### 目的 / 北极星
- ◯ 员工能力快照 + 岗位锚点反推

### 服务谁
- ◯ 员工自己 (看能力快照 + 成长路径) + 部门领导/CEO (看岗位锚点)

### 设计原则
- ⭐ 卷起来 + 清晰秩序 = 安全感，不是温暖陪伴; 排行/积分是核心玩法不是装饰
  - tags: from-memory
- ◯ **所有标注必须可追溯到原始证据** (顾源源关于成长中心的边界要求): 成长中心展示'你的客户洞察能力 78 分'时, 要能反向钻取到: (a) 这个分数由哪 N 条证据贡献; (b) 每条证据的原始来源 (task / document / meeting); (c) 当时 LLM 的标注是什么, 置信度多高。**不能是黑盒**, 这一点保证成长中心给的反馈是有事实依据的, 不是凭空打分。
  - tags: edge-rule
- ◯ **岗位画像反推算法** (从被认可样本反推, 不预设): (1) 拉这个岗位过去 90 天所有产出; (2) 按 delivery_quality=accepted/reused 过滤'被认可的产出'; (3) 这些产出涉及的能力维度, 按频次+难度加权 = 岗位的能力分布; (4) 取 P50 (中位数) 作为'达标线', P80 作为'优秀线' → 这就是黄色锚点。**关键约束**: 标杆从样本反推, **不要预设'咨询师应该 6 维能力'**, 看实际'被认可的咨询师'在做什么。
- ◯ 黄色锚点 = 反推标杆，不预设标准。不预设'咨询师应该有 6 维能力'; 看现在岗位上'被认可的人'在做什么，反推岗位锚点 (P50 / P80)。评估个人能力跟岗位 P80 比，可钻取到原始证据。

### 做出的设计决策
- ◯ **work_evidence_annotations 标注体系核心字段**: source_type (task/meeting/document/...) + source_object_id + operator_id + ability_dimensions[] (锻炼了哪些能力, 多选: 执行/协作/分析/洞察/风险/写作) + difficulty_level (1-5 基于复杂度/跨域程度/是否新方法) + delivery_quality (accepted/reused/rejected/neutral/pending) + contribution_role (lead/major/minor/observer) + annotator (llm/human) + confidence (0-1)。**关键**: 异步标注, 走 Phase 0-3 governor 队列, 不阻塞主流程。
  - tags: spec

### 架构详述
- ◯ **6 层数据需求** (用户用'反向优化'思路写的需求清单): Layer 1 · 人员身份 (operator_id, name, employee_no, hire_date, manager_id, 多源归一); Layer 2 · 岗位与契约 (role_taxonomy 标准岗位字典, contract 抽取 KPI 和职责); Layer 3 · 工作产出 (task / document / meeting / chat / structured_table 的产出, **最核心**: 能力分的全部客观证据都来自这层); Layer 4 · 知识沉淀 (经验墙金句 / 成长手册 / memory_facts / 文档贡献 / 解答帮助); Layer 5 · 协作网络 (高频协作伙伴 / 跨部门协作 / 主导 vs 参与比例 / 上下游对接); Layer 6 · 时间序列 (周/月/季度快照, 看变化)。
  - tags: spec

---

## 战略陪伴
**模块 id**: `module:strategic_accompaniment`
**父模块**: `software:root`
**一句话定位**: 客户的'超级员工'视图 - 主线/卡点/澄清/关系书
**entries 数**: 11

### 目的 / 北极星
- ◯ 客户的战略陪伴视图: 主线推进 / 卡点 / 澄清 / 关系书

### 边界 (做什么 / 不做什么)
- ◯ **当前 5 Tab 各自功能详述** (StrategicBrainView.tsx): ① **clients (客户档案)** - DigitalAssetsTab + OrganizationDnaPanel + 客户卡片网格; 点击客户进 DigitalAssetDetailView (单客户详情); ② **thoughts (判断 & 思考)** - StrategicThoughts 列表 + 评审 (confirm/dismiss/create_task); ③ **contradictions (矛盾 & 待确认)** - ContradictionsTab (fact_contradictions); **将改名为'事实澄清'**, 跟客户字典融合, 含'重复文件页' (DuplicateDocumentsSection); ④ **health (资料健康)** - KnowledgeHealthTab + 客户脉冲 + 数字资产指标; **澄清面板规划放这里**; ⑤ **outputs (输出沉淀)** - OutputsTab (proposal_drafts + 已采纳判断)。
- ◯ 当前 5 Tab: 客户档案 / 判断 & 思考 / 矛盾 & 待确认 / 资料健康 / 输出沉淀。'矛盾 & 待确认' 计划改名为 '事实澄清'，跟客户字典融合。

### 做出的设计决策
- ⭐ 所有关于澄清的部分全部放在澄清页，而澄清页就放在战略陪伴的知识健康度的那个 tab
- ◯ **Phase 1 首屏「客户主页」3 区块字段定义** (已实现, 2026/5/15): 组件 ClientStrategicPulseSection 在 DigitalAssetDetailView 顶部。**本周新动态**: 读 evidence_cards 近 7 天 + 过滤测试垃圾 + 6 个轴 (impact: advance/neutral/block); **你接下来要做**: 读 tasks 未完成 + 按 urgency 排 (overdue/today/this_week/later); **当前卡点**: 读 event_lines status=active + 最近 30+ 天无活动, 或 current_blocker 有真内容。前端用 dedupePulseTodos 去重 (相同 title + dueDate)。后端 endpoint: GET /api/v1/clients/{client_id}/strategic-pulse, service: backend/app/services/client_strategic_pulse.py (290 行 + 25/25 单测)。
  - tags: implemented
- ◯ Phase 1 首屏「客户主页」克制版 3 区块设计 (顾源源确认): 1. 本周新动态 (近 7 天关键事实，过滤测试垃圾); 2. 你接下来要做 (未完成任务，按到期紧迫度排); 3. 当前卡点 (主线 30+ 天无活动或有真实 blocker)。后台知道的其他信息 (治理结构/战略定位/花名册全员/业务结构) 全部塞到底部 [查看完整 DNA] 和 [澄清面板] 入口里。

### 架构详述
- ◯ **Clarification Quality Score 评分系统** (顾源源原话标准: '达到今天问日慈 10 问的水平'): 针对性 30 (引用 doc_id / evidence_id) + 矛盾揭示 25 (指出材料间矛盾如 ASR 不同写法) + 触发深度 20 (用户答能引出 ≥1 新疑问) + 业务价值 15 (能影响决策) + 可执行性 10 (提供清晰回答路径)。总分 1-100。**目标**: AI 平均得分 ≥ 80 才上线。**评分员**: 先用 GPT, 用户校准, 沉淀为 classifier。**黄金样本**: Claude Code 主线问日慈 10 问 + 黔行 10 问 (在 STEP-0-DATA-CENTER-UPGRADE.v0.1.md 和 v0.2 文档附录里完整保留)。
  - tags: spec, kpi
- ◯ **澄清面板 6 个核心能力** (Phase 3 规划, 顾源源详细 spec): (1) AI 提问 - 基于 DNA 完整度自动生成针对性问题 (达到 Claude 问日慈 10 问的水平); (2) 引文支撑 - 每问下方显示'基于以下材料问的', 列引用 evidence/document, 带 quote 高亮; (3) 一键打开文档 - 引用旁有 📂 按钮, 调 window.yiyuWorkbench.openPath(); (4) 版本核对 - 问'是不是最新版本'时, 自动对比 documents 表同主题最近上传时间, 标记'已是最新'或'X 天前还有更新'; (5) 澄清后自动沉淀 - 答案 patch 到对应字段 + 新矛盾自动 raise + 新文档自动入库提示 + Q/A 写 clarification_records 表 audit trail; (6) 跟客户字典融合 - 实体澄清和事实澄清合并入口。
  - tags: spec

### 历史背景 / 演化
- ◯ DigitalAssetDetailView 原 hero 区 6 数字遗产: 已确认事实 (KnowledgeStatus.confirmedFacts) / 待确认思考 (pendingThoughts) / 矛盾点 (activeContradictions) / 信息缺口 (knowledgeGaps) / 下一阶段 / 已学资料。这是 Karpathy 4 数字 + 2 辅助指标的设计。用户判定为'炫耀后台知道多少', 应隐藏到二级入口。Phase 1 已在它上方加 ClientStrategicPulseSection 3 区块, 原 6 数字保留下移, 未来作'知识健康度指标'用。
- ◯ 原 hero 区有 6 个 Karpathy 语义数字 (已确认事实/待确认思考/矛盾/缺口/下一阶段/已学资料)。用户认为这是'炫耀后台知道多少'，应隐藏到二级入口。Phase 1 已在客户主页顶部加 ClientStrategicPulseSection 3 区块，原 hero 区下移。

### 已知 bug 模式
- ◯ **修复过的 endpoint mismatch bug** (2026/5/15): 前端 getClientKnowledgeStatus 之前调 /api/v1/clients/{id}/knowledge/status, 但 backend 这个 endpoint 返回 KnowledgeStatusRecord (totalDocuments / totalChunks 等), **没有** confirmedFacts / pendingThoughts / weeklyDelta 字段。代码却写 knowledgeStatus.confirmedFacts.toLocaleString() → undefined.toLocaleString() 爆炸。**修复**: 改前端 helper 调正确 endpoint /api/v1/clients/{id}/knowledge-status (连字符不是斜杠), 返回 ClientKnowledgeStatusRecord (含完整字段)。**教训**: 两个相似命名的 endpoint 容易混淆 (knowledge-status vs knowledge/status)。
  - tags: fixed-bug

---

## 数据中心
**模块 id**: `module:data_center`
**父模块**: `software:root`
**一句话定位**: 所有 AI 业务判断的背景知识引擎 - 关系网编织线程
**entries 数**: 10

### 目的 / 北极星
- ⭐ 你做的东西就是所有判断的背景

### 边界 (做什么 / 不做什么)
- ◯ 从'对象存储 + LLM 临时调用'升级到'业务事实层 / 关系网'。关系网 4+1 层架构 (见 software:root 的 architecture entry)。工作台供应每份文档解析好的结构化字段; 数据中心负责把细节串成关系网; 下游模块消费关系网作为业务判断背景。

### 做出的设计决策
- ◯ **不新建 business_thread 表, 升级 event_lines 体系** (v0.3 关键结构决策): 理由 - 系统已有 event_lines (41 行, 70% 字段重合) / event_line_activities (70 行) / event_line_weekly_snapshots (0 但字段完美) / event_line_memory_snapshots (36 行) 四层结构。再造新表 = 结构性冗余 + 现有代码大改 + 数据迁移痛苦。正确方向: 在 event_lines 上加 9 个新字段 (thread_level / parent_thread_id / committed_at / expected_completion_at / deliverable_spec_json / clarification_status_json / is_test_data / name_history_json / derivation_from_id)。
  - tags: architecture-decision
- ◯ Phase 节奏 (顾源源确认 v0.3): Phase 0 对齐定义 (now) → Phase 1 骨架 (花名册 + 主线 + 关键引擎 4-5 周) → Phase 2 血肉 (事实卡片 + 关系书 + 数据卫生 3-4 周) → Phase 3 叙事 (澄清面板 + 个人快照 3-4 周) → Phase 4 自治 (闭环 + 持续运转 2-3 周)
- ◯ 5 项底层能力: ① 实体身份解析 (花名册 + 多源归一 + ASR 错误识别) / ② 证据标注网络 (业务语义 + 时间锚 + 影响 + 置信度) / ③ 时间锚 + 周期快照 (人/主线/客户 三种快照模板，长程 3 年) / ④ 横向锚点 / 分群标杆 (从被认可样本反推，不预设) / ⑤ 血缘 + 置信度 (任何 AI 输出可钻取到原始证据)。

### 架构详述
- ◯ **5 个引擎层详述** (v0.3 新增): ① **多维投影引擎** - 按 部门/人物/任务/时间 4 种切面投影关系网; ② **事件流引擎** - 主线状态变化序列化 (active→blocked→resolved 等), 含触发时间/原因/证据; ③ **提醒/触发引擎** - 日扫承诺到期/客户冷却/主线超期, 事件触发人物状态变更等; ④ **关系书生成引擎** - 8 段自动生成 + 段落级独立更新 + 钻取链路; ⑤ **澄清问题生成引擎** - 扫描关系网缺口生成针对性问题 (Clarification Quality Score ≥80)。
  - tags: architecture
- ◯ **5 项底层能力详述** (v0.3 文档定稿): ① **实体身份解析** - 所有主体 (人/客户/主线/部门) 多源 ID 归一; 支持别名 + 优先级合并 (HR > 飞书 > 自定义) + 冲突标记; ② **证据标注网络** - 每条原始事件被解释 (业务语义/时间锚/置信度/影响 4 个轴); ③ **时间锚 + 周期快照** - 多种时间锚 (created/承诺/交付/失效/复盘) + 周/月/季快照; ④ **横向锚点/分群标杆** - 从被认可样本反推标杆 (人 vs 岗位 P80 / 客户 vs 客户分群); ⑤ **血缘 + 置信度** - 任何派生数据带 source_evidence_ids[] + confidence + annotator_type。
  - tags: architecture

### 与其他模块的协同
- ◯ **跟工作台 R11.x 的 5 项新协同需求** (v0.3 加, 待同步给工作台线程): (1) 文档涉及部门识别 - 部门切面投影必需; (2) 文档涉及主线识别 - 任务智能简报 / 关系书必需; (3) 状态变更事件识别 (如'老高离职') - 资方风险信号触发; (4) 关键时间承诺识别 (如'5/1 前发') - 承诺到期提醒; (5) 实体提及自动检测 - 任务相关文档自动关联。

### 历史背景 / 演化
- ◯ 数据中心改造文档演化: v0.1 (`STEP-0-DATA-CENTER-UPGRADE.md`, 已归档) → v0.2 (`DATA-CENTER-RELATIONSHIP-GRAPH-PLAN.md` 含三段流水线 + 端到端高老师离职案例) → v0.3 (含 5 层结构 + 引擎层 + 部门维度 + 5 项工作台协同新需求, 基于 20 场景反推)。v0.2 归档在 docs/archive/, v0.3 是当前正在用的。

### 黄金样本 / 真实数据快照
- ◯ **当前数据中心健康度盘点** (2026/5/15 真实查询结果): ✅ 活的表: documents (1764), v2_documents (1313), chat_messages (1292), memory_facts (3010), evidence_cards (168 但 polarity 全 neutral), tasks (136), event_lines (41, 颗粒度混乱), judgment_versions (21, 全 candidate); 🔴 死表: event_line_weekly_snapshots (0, 字段完美但无人写) / atomic_facts (0) / entities (0) / fact_contradictions (0) / action_items (4 严重不足) / meetings (7 严重不足) / client_strategic_profiles (日慈+黔行均空) / cooperation_relationships (日慈+黔行均空); 🟡 半活: event_line_memory_snapshots (36 但 70% 字段空) / event_line_activities (70 条但 90% 是测试附件); ❌ 缺失: plan_items 表根本不存在 (周复盘 related_plan_ids_json 是死链)。
  - tags: diagnosis, real-data

---

## 系统设置
**模块 id**: `module:settings`
**父模块**: `software:root`
**一句话定位**: 组织治理 + 部门 + 权限 + 软件 DNA
**entries 数**: 10

### 目的 / 北极星
- ◯ 组织治理 + 部门 + 权限管理 + 软件 DNA (Phase 1.5 新加)

### 边界 (做什么 / 不做什么)
- ◯ **当前系统设置已有的子页面**: 组织与权限 (OrganizationSetupCenter) / 员工审批 (EmployeeReviewPanel, admin only) / 组织底盘 (org-model: 部门/岗位/邀请码/飞书集成) / AI 模型配置 / 数据中心 / 系统日志 等。**软件 DNA tab 规划加在这里** (Phase 1.5 现已建好后端, 待加 UI)。
- ◯ **三种角色的完整行为表**: (角色) → (在周复盘看什么) → (在战略陪伴看什么): **employee** → 只我的视角 (切换器隐藏) → 所有客户档案 (跟自己负责的); **department_lead** → 我的视角 + 部门视角 (无下拉) → 所有客户档案 + 部门资源; **admin** → 我的 + 部门下拉 + 组织视角 → 全部 + 组织 DNA + 跨客户洞察。**身份重合规则**: admin > department_lead > employee, 取最高。
- ◯ 3 种角色: CEO (admin) / 部门领导 (department_lead) / 普通员工 (employee)。视角切换器: 普通员工隐藏; 部门领导 2 按钮无下拉; CEO 3 按钮 + 部门下拉。CEO + 部门负责人重合时，admin 身份优先。

### 做出的设计决策
- ⭐ 组织负责人那里写的是顾源源的账号，他就是组织的负责人; 合作发展部、战略发展部、技术发展部分别都绑定了三个账号，他们就是这个部门的负责人
- ◯ **双保险设计**: 判定一个用户是不是部门负责人有两条路径, 两条**任一通过**即认定: (a) session_user.isDepartmentLead === true && departmentId === X → 在 X 部门; (b) user_id / fullName 出现在 governance.departments[].leaders[] 列表里。理论上云端会自动同步两个字段, 但万一同步失败, 双保险防止 leader 身份丢失。**反向风险**: 撤销某人部门负责人身份时, **两个地方都要清空**才彻底, 否则可能仍被识别为 leader。
- ◯ 组织/部门治理在云端 SoT，60 秒缓存。本机 backend 读写都透传云端 /api/v1/settings/org-model/profile。其他同事在其他电脑登录同一组织 → 拿到同样的配置。

### 数据流
- ◯ **部门治理云端 SoT 数据流** (60 秒缓存): **写**: 用户在 OrganizationSetupCenter 编辑 → POST /api/v1/settings/org-model/profile → 云端 set_setting('settings.org_model_profile', ...) → 同步; **读**: backend `_review_governance_with_members()` → Step 1 拉本地缓存 settings.review_governance → Step 2 调云端 /org-model/profile 拿真实部门列表 → Step 3 调云端 /employees/directory 拿员工目录 → Step 4 按 departmentId 自动分配 members 到对应部门 leaders 列表。**缓存**: 60 秒 TTL, 减少云端调用; 但意味着改组织设置后, 其他同事最多等 60 秒看到生效 (设计 trade-off, 非 bug)。

### 历史背景 / 演化
- ◯ 组织治理实际数据 (2026/5/16, 云端 org_yiyu_default): 组织负责人 = 顾源源 (leaderUserId 是 None, leaderName='顾源源', 是个轻微问题但不影响 admin 视角); 部门 3 个: 合作发展部 (leader: 乐乐 emp_efdd076c31) / 战略发展部 (leader: 顾源源 user_guyuan) / 技术创新部 (leader: 林佳维 emp_ebf2ea94ed)。林佳维在云端有员工档案但尚无登录账号 (emp_* 不是 user_*)。
  - tags: real-data
- ◯ 顾源源 = admin + 战略发展部 + isDepartmentLead=true (CEO + 战略发展部负责人重合)。云端实际部门 3 个: 合作发展部 (乐乐) / 战略发展部 (顾源源) / 技术创新部 (林佳维)。林佳维在云端有员工档案 (emp_ebf2ea94ed) 但还没登录账号。

---

## 资讯情报站
**模块 id**: `module:intelligence_station`
**父模块**: `software:root`
**一句话定位**: 基于客户主线 + 个人能力 gap 的精准情报推荐
**entries 数**: 3

### 目的 / 北极星
- ◯ 基于客户主线 + 个人能力 gap 做精准情报推荐

### 边界 (做什么 / 不做什么)
- ◯ **不是通用 RSS / 不是给所有人推所有新闻**。每条资讯都跟某条主线或某个能力维度匹配，否则不推。

### 与其他模块的协同
- ◯ 数据中心 (客户主线匹配资讯类型) / 成长中心 (能力 gap → case study 推荐) / 客户工作台 (一键转入)

---

# L3 子功能级

## 周复盘/本周概览
**模块 id**: `submodule:weekly_overview`
**父模块**: `module:weekly_review`
**一句话定位**: 本周任务的 AI 聚合 + 主线卡片视图
**entries 数**: 2

### 目的 / 北极星
- ⭐ 本周的这个概览，它主要是关于任务的概览

### 边界 (做什么 / 不做什么)
- ◯ 只看 task (不看 documents / event_lines / evidence_cards / memory_facts)。数据流: tasks → 按本周 due_date / completed_at / deadline_at 筛 → AI 生成'重点主线卡片'

---

## 战略陪伴/客户主页
**模块 id**: `submodule:client_strategic_home`
**父模块**: `module:strategic_accompaniment`
**一句话定位**: 单客户的克制版主页 - 3 区块
**entries 数**: 2

### 目的 / 北极星
- ◯ 顾问开始陪伴这个客户时第一眼看到必要决策信息

### 边界 (做什么 / 不做什么)
- ◯ 前台只放 3 个区块: 本周新动态 / 你接下来要做 / 当前卡点。详细 DNA / 关系书 / 澄清面板放在底部入口

---

## 战略陪伴/澄清面板 (规划中)
**模块 id**: `submodule:strategic_clarification_panel`
**父模块**: `module:strategic_accompaniment`
**一句话定位**: AI 主动提针对性问题让用户检查 AI 理解对不对
**entries 数**: 3

### 目的 / 北极星
- ⭐ 需要让软件也具备这样澄清的能力，澄清的过程当中需要让软件去引用一些文件里的内容，甚至直接打开软件让客户确认是不是这个文件讲的东西

### 做出的设计决策
- ◯ Clarification Quality Score 评分: 针对性 30 (引用具体材料) + 矛盾揭示 25 (指出材料间矛盾) + 触发深度 20 (用户回答能引出新疑问) + 业务价值 15 (能影响决策) + 可执行性 10。目标: AI 平均分 ≥ 80 (对标 Claude 问日慈 10 问的水平)。

### 与其他模块的协同
- ◯ 跟客户字典融合; 跟事实澄清模块 (原'矛盾和待确认') 融合; 跟关系网的 L5 引擎层结合

---

## 数据中心/业务主线 (规划中)
**模块 id**: `submodule:business_thread`
**父模块**: `module:data_center`
**一句话定位**: 可追踪的'一件事' - 5 颗粒度 + 嵌套 + 衍生
**entries 数**: 4

### 目的 / 北极星
- ◯ **业务主线 (business thread)** = 把散落的事实串成可追踪的'一件事'。升级自现有 event_lines 表 (不新建), 加 9 个新字段。

### 边界 (做什么 / 不做什么)
- ◯ **5 种颗粒度** (顾源源确认 'thread_level' 字段): **project 项目级** (1-3 年, 例: '日慈战略陪伴' / '大山里的音乐课堂'); **phase 阶段级** (1 季度/半年, 例: '日慈使命愿景调整' / '黔行 6 月工作坊'); **commitment 承诺级** (几周-几个月, 例: '5/1 前发更新价值观给詹瑶'); **single_touch 一次约见级** (一次性, 例: '4/19 河南面谈詹瑶'); **mechanism 机制级** (长期持续, 例: '建立重点客户周跟进节奏表')。**判断规则**: 有交付物 + 截止日 = commitment / 跨多 commitment + 阶段目标 = phase / 跨多 phase + 战略方向 = project / 一次见面/电话 = single_touch / 无终点运营 = mechanism。
  - tags: spec

### 做出的设计决策
- ◯ **每条主线带的字段** (v0.3 升级清单): thread_level (5 选 1) + parent_thread_id (嵌套) + derivation_from_id ('衍生自') + committed_at (承诺日 业务时间锚) + expected_completion_at (预期完成日) + deliverable_spec_json (交付物 + 验收标准) + clarification_status_json (每个维度 ✓/⚠️/❌) + is_test_data (测试数据标记) + name_history_json (命名变更如 教师赋能→心松松)。**长程不预设寿命**: 承诺级可以是 2 周也可以是 3 年, 按真实业务跨度走。

### 真实案例
- ◯ **日慈基金会 5 条 event_lines 真实颗粒度** (混乱样本, 待规整): (1) 日慈战略陪伴 - 项目级; (2) 跟笑雨老师核对教师项目进度 - 承诺级; (3) 日慈基金会使命愿景价值观确认 - 阶段级; (4) 建立重点客户周跟进节奏表 - 机制级; (5) 约见日慈张真看益语系统 - 一次约见级。5 条全用 kind='project_line' 标记, 颗粒度没区分 - **这是 v0.3 升级要解决的核心问题**。

---

## 数据中心/关系网 5 层架构
**模块 id**: `submodule:relationship_graph_layers`
**父模块**: `module:data_center`
**一句话定位**: 关系网完整 5 层 - 花名册 + 事实卡片 + 项目台账 + 关系书 + 引擎层
**entries 数**: 2

### 做出的设计决策
- ◯ **Phase 1 硬交付的能力清单** (8 项, 基于 ≥12 分高价值场景反推): (1) 花名册 (人物 + 别名 + 部门挂载 + 客户挂载 + 状态); (2) 主线颗粒度 + 部门挂载 + 起止 + 责任人; (3) 主线推进状态量化 (顺利/卡住/逾期); (4) 事件流 (主线状态变化序列); (5) 事实卡片 4 标签 (业务语义/影响/时间锚/置信度); (6) 多维投影引擎 (部门/人物/任务/时间 4 种切面); (7) 提醒/触发引擎 (承诺到期/客户冷却 2 类); (8) 测试数据/AI 模拟标记。

### 架构详述
- ◯ **5 层叠加结构**: **第 1 层 花名册 (external_persons)** - 人物 + 别名归一 + 关系图 (家庭/同事/上下级) + 健康/在岗状态 + 工作风格 + 部门挂载 + AI 模拟标记; **第 2 层 事实卡片 (event_line_activities 升级)** - 业务语义 + 时间锚 + 影响 + 置信度; **第 3 层 项目台账 (event_lines 升级)** - 5 颗粒度 + 嵌套 + 生命周期 + 部门挂载; **第 4 层 关系书** - 8 段自动生成 + 段落级钻取; **第 5 层 引擎层** - 5 个引擎让关系网'主动'驱动业务判断。

---

## 数据中心/数据卫生 (清理 + 治理)
**模块 id**: `submodule:data_hygiene`
**父模块**: `module:data_center`
**一句话定位**: 测试数据 / AI 模拟数据 / 误归类的识别 + 标记 + 一键剔除
**entries 数**: 3

### 目的 / 北极星
- ◯ 解决数据中心当前的几类脏数据问题, 不让 AI 把测试/模拟数据当真。

### 做出的设计决策
- ◯ **清理机制 (v0.3 规划)**: (a) 所有承担生产业务的表加 is_test_data + is_simulated 字段; (b) UI 默认过滤 is_test_data=1 和 is_simulated=1 记录; (c) 任务模板生成的测试样本**默认 is_test_data=1**; (d) documents 加 misattribution_status 字段 ('' / 'disputed' / 'removed'); (e) 澄清面板内置'这份文档真的属于这个客户吗?' 操作。**不立刻批量删除**, 只标记 + UI 过滤 (Phase 2 才考虑批量清), 避免误删用户测试期真实数据。

### 真实案例
- ◯ **当前已识别的脏数据**: (1) 庆华 = AI 模拟操作员 (operators.id='op_qh' role_tier='ceo' is_current=1), 顾源源已明确要删; (2) 黔行 task '开展实地走访' 重复 3 次 + '签约改造方案' 重复 2 次 + '完成立项评审' 1 次, 全是测试模板; (3) event_line eline_1ff90fba91 name='eline_1ff90fba91' (id 当 name 用, 早期脚本批量创建脏数据); (4) 90% event_line_activities 是测试附件 (smoke_att.txt / final_test.txt / no_client_test / progress_test / offline_upload.txt 等); (5) 浙江敦和慈善基金会的研究报告误归类到黔行库 (应为研究素材, 非合作方); (6) operators 表 vs local_identities 表完全不重叠 (operators: 庆华/一朔/嘉宁; local_identities: 乐乐) - 两套人物体系未关联。

---

## 系统设置/软件 DNA 长期记忆
**模块 id**: `submodule:phase_1_5_module_dna`
**父模块**: `module:settings`
**一句话定位**: 跨 session 跨线程的产品认知长期记忆
**entries 数**: 4

### 目的 / 北极星
- ◯ 解决每个新 AI 线程都要花 20-40 分钟跟顾源源澄清同一些产品定位的痛点。建立软件级 + 模块级 + 子功能级三层长期记忆, 多 AI 线程联合写作, 未来 AI 启动新任务时**先读再做**, 减少重复澄清。

### 工作流 / 用户判断方式
- ◯ **两种沉淀触发** (指南 §6 关键): (a) **首次启动** - 新线程调 GET 一遍, 回顾历史对话, 批量 POST 历史澄清内容; (b) **持续沉淀** (每轮工作结束前必做) - 4 个自问: 1) 有没有澄清新定位? 2) 有没有撤回决定? 3) AI 发现了什么用户没明说的哲学? 4) 还有什么不清楚? → 全部 POST。**指南文档**: docs/MODULE-DNA-SEEDING-GUIDE.md + Word 版在 ~/Downloads/。

### 做出的设计决策
- ◯ **当前存储**: 本机 SQLite (跟其他 settings 同库)。**未来升级**: Phase 2/3 升级为云端 SoT, 跨设备 + 跨同事同步。**UI 入口规划**: 系统设置加一个 'software_dna' Tab, 卡片列表 + 编辑表单。API 完整可用, UI 待 Phase 1 后续做 (用户建议先看效果再决定)。

### 架构详述
- ◯ **数据结构** (2 张表): module_definitions (id, level, parent_id, display_name, summary, created_at, updated_at) + module_definition_entries (id, module_id, category, content, is_user_quote, source_thread, source_session, confidence, tags_json, superseded_by, created_at)。**核心设计**: 多 entries 共存不互覆盖, 每条带 source_thread 知道来源。API: GET/POST/PUT /api/v1/settings/module-dna + POST /{id}/entries (append) + DELETE /entries/{entry_id}。

---

## 跨模块协议 (三段流水线交接)
**模块 id**: `submodule:cross_module_protocol`
**父模块**: `software:root`
**一句话定位**: 工作台 → 数据中心 → 业务判断模块 的接口约定
**entries 数**: 2

### 做出的设计决策
- ◯ **关键约定** (3 条): (1) 工作台**先于**数据中心一个 Phase 跑 - 食材准备好, 数据中心才能编织; (2) 数据中心**不重复做工作台的事** - 不从原始文档抽字段, 只从工作台抽好的字段里挑、归一、串接; (3) 下游模块**不重复做数据中心的事** - 不自己推理客户当前状态, 直接读关系网。

### 架构详述
- ◯ **三段流水线交接合同** (顾源源原话定位'数据中心是所有判断的背景'): **上游 工作台线程** (文档分解) → 给数据中心: 16 字段浅解构 + 精解构 (合同 9 字段 / 会议纪要字段 / 项目方案字段) + FTS 召回结果 + 5 项新协同 (部门/主线/状态变更/时间承诺/实体提及); **中游 数据中心** (关系网编织) → 给下游: 客户关系书 + 主线全景 + 澄清面板 + 部门切面 + 个人能力快照; **下游 业务判断模块** (战略陪伴 / 成长中心 / 任务日程 / 客户工作台 / 周复盘) → **只读不写** - 直接消费数据中心的关系网作为业务判断背景, 不重复推理。

---

# L4 设计原则级

## 原则/优化公式 (用户决定做不做的标尺)
**模块 id**: `principle:formula_filter`
**父模块**: `software:root`
**一句话定位**: 频次 × 价值感知 = 是否值得做的硬约束
**entries 数**: 2

### 设计原则
- ⭐ 顾源源原话: '考虑的场景都应该是 功能价值 × 替客户解决的问题 × 这个问题出现的频次 × 这个问题给客户造成的困扰程度。这是判断一个功能值不值得做的准绳。'

### 做出的设计决策
- ◯ **实施化的评分表**: 频次档: 每天=5 / 每周 1-2 次=4 / 每月 1-2 次=3 / 季度=2 / 偶尔=1; 价值感知档: 强(无可替代)=5 / 中('有用比之前好')=3 / 弱('看起来还行')=1; 总分 1-25。**硬约束**: 总分 ≥ 12 的场景才进 Phase 1-3 硬交付范围; <12 不是说不做, 是'等高分场景做完有余力再说', 避免造 3 个轮子跑的车。

---

## 原则/功能反推方法论
**模块 id**: `principle:reverse_design_method`
**父模块**: `software:root`
**一句话定位**: 从用户在功能里要什么倒推数据结构, 而不是从架构推功能
**entries 数**: 2

### 设计原则
- ⭐ **功能反推方法论** (顾源源原话方向纠偏): '结构对不对, 不能靠想象数据中心怎么设计, 必须从用户在功能里要什么反推。你应该想象人类用户在任务与计划当中需要用到什么资料, 比如说在本周概览当中, 一个部门本周到底发生了什么事情, 比如说在部门信号当中这个部门有哪些关键的问题是需要留意的。你要通过这个软件的功能价值, 就是呈现给用户可感知的功能价值, 才能实现这些功能, 再倒推需要什么样的结构, 才能支撑这些资料稳定的被记录下来和被捕捉到。'

### 工作流 / 用户判断方式
- ◯ **4 步反推流程** (Phase 0 第二轮验证): (1) 列出软件里所有'会读关系网做判断'的功能场景 (~30 个); (2) 每个场景反推: 用户要看什么 → 关系网必须提供什么能力 → v0.2 有没有 → 缺什么; (3) 按用户公式打分: 频次 × 价值感知 (硬约束: ≥12 才进硬交付); (4) 把缺口归类到 4 层结构, 看是否要新加层 (反推暴露了需要第 5 层引擎层)。

---

## 原则/用户判断节奏
**模块 id**: `principle:user_judgment_pace`
**父模块**: `software:root`
**一句话定位**: 用户只能判断方向, 细节必须 UI 真实呈现才能判断
**entries 数**: 2

### 设计原则
- ⭐ **用户判断节奏铁律** (顾源源原话): '在你写的功能正在软件上通过判断呈现出文字给用户提供价值, 到这一步之前, 我都没有办法判断你的这个功能到底对不对, 我只能判断这个方向是对的。'

### 工作流 / 用户判断方式
- ◯ **应用规则**: (a) 方向文档审到 v0.3 就够, 不要继续 v0.4 v0.5; (b) 立刻做 UI demo (哪怕半 mock 数据); (c) 让用户在软件里点开看, 反馈具体痛点; (d) 基于真实呈现迭代, 不在纸上完善。**反例**: 我在 Phase 0 写了 v0.1/v0.2/v0.3 三轮文档共 1500+ 行, 用户看到后说'文档我审到这就到极限了', 应该早点出 UI。
  - tags: lesson

---
