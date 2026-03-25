# External Pattern Scans v1

## Purpose

这个文档专门承接：
- 外部成熟产品模式
- 真实软件团队分工
- 已成型的产品/工程经验
- 哪些适合当前仓库，哪些不适合

规则：
- 优先官方文档、成熟产品说明、稳定开源项目
- 不收集营销软文
- 每条参考必须回答：
  - 学到什么
  - 为什么适合或不适合当前仓库
  - 应该影响哪一个 loop / 哪一个 plan

## Scan 1: Virtual Team Role Design

### 1. Agency-Agents
- Source: [Agency-Agents](https://github.com/msitarzewski/agency-agents)
- 关键信号：
  - 用岗位说明书而不是模糊人格来定义 agent
  - 每个岗位强调职责、流程、交付物
  - 适合“多角色协作软件团队”的组织方式
- 对当前仓库的影响：
  - 保留“多角色、强边界、可交接”的方法
  - 不照搬其全部角色数量
  - 改成适合当前仓库的真实软件岗位

### 2. Product Manager
- Source: [Atlassian Product Manager Guide](https://www.atlassian.com/agile/product-management/product-manager)
- 关键信号：
  - 产品经理负责战略、路线图、功能定义和业务/技术/用户之间的平衡
- 对当前仓库的影响：
  - 需要一个岗位专门判断“这功能到底给谁用、为什么值得做、边界在哪”
  - 不能把这个职责混给工程或 UI 角色

### 3. Product Operations
- Source: [Atlassian Product Operations Guide](https://www.atlassian.com/software/jira/product-discovery/resources/product-operations-guide)
- 关键信号：
  - Product Ops 的职责是优化流程、工具、协作与文档，让产品团队稳定运作
- 对当前仓库的影响：
  - 需要一个岗位专门维护 docs/virtual-team、依赖、节奏和 release gate
  - 不能让主编排者既裁决又亲自维护所有流程细节

### 4. UX Research
- Source: [Interaction Design Foundation - UX Research](https://www.interaction-design.org/literature/topics/ux-research)
- 关键信号：
  - 先理解用户的真实行为和需求，再判断设计是否成立
- 对当前仓库的影响：
  - 必须有人专门盯 CEO / 部门负责人 / 员工的实际工作流
  - 不能只从页面逻辑反推用户行为

### 5. Interaction Design
- Source: [Interaction Design Foundation - Interaction Design](https://www.interaction-design.org/literature/topics/interaction-design)
- 关键信号：
  - 交互设计关注“使用那一刻”的反馈、状态、可操作性
- 对当前仓库的影响：
  - 任务卡展开、周复盘保存、状态切换、日历交互必须有专岗盯

### 6. Information Architecture
- Source: [Interaction Design Foundation - Information Architecture](https://www.interaction-design.org/literature/topics/information-architecture)
- 关键信号：
  - IA 负责组织、标签、导航与可理解性
- 对当前仓库的影响：
  - 背景 / 证据 / 记忆 / 判断 / 动作 的边界必须由专岗维护

### 7. Data Engineer
- Source: [IBM - Data Engineer vs Data Scientist vs Analytics Engineer](https://www.ibm.com/think/topics/data-engineer-data-vs-data-scientist-vs-analytics-engineer)
- 关键信号：
  - Data Engineer 负责设计和维护数据架构、管道与可靠性
- 对当前仓库的影响：
  - 本地与云端边界、写回、backfill、schema 演进要有专岗，不应混在一般后端讨论里

### 8. Analytics Engineer
- Source: [IBM - Data Engineer vs Data Scientist vs Analytics Engineer](https://www.ibm.com/think/topics/data-engineer-data-vs-data-scientist-vs-analytics-engineer)
- 关键信号：
  - Analytics Engineer 把原始数据转成可计算、可解释、可消费的分析模型
- 对当前仓库的影响：
  - `coverage / confidence / safeOutputMode / ranking` 这些 judgment 合同应由专岗维护

### 9. Relevance Engineer
- Source: [OpenSource Connections - What is a Relevance Engineer?](https://opensourceconnections.com/blog/2020/07/16/what-is-a-relevance-engineer/)
- 关键信号：
  - 相关性工程处理检索、推荐、准确率与性能之间的平衡
- 对当前仓库的影响：
  - 证据引擎、chunk、召回、citation 解释不能只靠通用后端思维处理

### 10. Platform Engineer
- Source: [IBM - Platform Engineering](https://www.ibm.com/think/topics/platform-engineering)
- 关键信号：
  - Platform Engineering 关注为开发与交付提供稳定、可复用的平台能力
- 对当前仓库的影响：
  - Electron 启动、安装、数据目录、更新链、封装稳定性需要专岗常驻

### 11. QA Engineer
- Source: [BrowserStack - What is Quality Assurance?](https://www.browserstack.com/guide/define-quality-assurance)
- 关键信号：
  - QA 是贯穿开发周期的质量过程，不只是上线前找 bug
- 对当前仓库的影响：
  - 必须保留一个专岗做真实点击回归、关键路径验证和 release gate 放行

## Initial Conclusion

对当前仓库，最合适的不是继续维持抽象方法论角色，而是：
- `program_director`
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

其中 `competitive_intelligence_analyst` 是必须新增的角色，用来保证虚拟项目组不是闭门造车。
