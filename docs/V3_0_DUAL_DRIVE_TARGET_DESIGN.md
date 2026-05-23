# 11 · 益语智库 3.0 双驱动调度 + AI 客户工作闭环目标设计

> **生成日期**: 2026-05-23
> **来源**: 顾源源 2026-05-23 钦定 (基于 09 评估报告 + 10 接口化测试方案)
> **作用**: 把 V3.0 目标从"接口数量" 转向"用户可感知的客户工作闭环"
> **核心立场**: 益语智库 3.0 = 一个可被人类和 AI 共同调度的客户工作系统

---

## 一、本质: 不是"谁来回答", 而是"谁来调度"

```
现在: 用户问 AI → AI 回答
3.0:  用户交代目标 → 智能体制定计划 → 调用软件模块 → 调用内部模型
      → 写入数据中心 → 生成任务/澄清/风险/故事卡 → 人确认关键动作
```

AI 不只是"回答者", 而是"调度者". 益语智库 3.0 = **AI 操作系统接口**.

---

## 二、双驱动 (内置 + 外置), 共用同一套底座

```
Agent Gateway → Tool Registry → Domain Services → Data Center → Approval / Audit
       ↑                                                              ↑
       ├─ 内置驱动: 益语自配豆包/GPT/Qwen, 系统内部 AI agent
       └─ 外置驱动: Codex/Claude/Cursor 通过 API/CLI/MCP-like 工具
```

**关键**: 两种驱动**不能走两套逻辑**, 必须共用同一组领域接口.

### 内置驱动 vs 外置驱动对比

| 维度 | 内置模型驱动 | 外置 Agent 驱动 |
|---|---|---|
| 谁发起 | 益语系统内部 AI | Codex / Claude / 外部 agent |
| 谁负责调度 | 系统内置 planner | 外部 agent 像 CEO 一样调度 |
| 谁做专业分析 | 益语内部模型和数据中心 | 主要仍由益语内部模型完成 |
| 权限来源 | 用户在系统内授权 | 用户给外部 agent 授权 |
| 风险重点 | 内部自动化误判 | 外部 agent 越权/串客户/绕过确认 |
| 共同底座 | Agent Gateway / Tool Registry / Approval / Audit | 同左 |

---

## 三、CEO 模式: 外置 agent 不亲自分析, 而是指挥益语内部模型干活

外置 agent 像 CEO:
- 看目标 / 拆任务 / 决定调用哪些模块 / 检查执行结果 / 发现缺口后追问 / 推关键拍板给用户 / 监督闭环

专业工作由益语内部完成:
- 数据中心 → 事实/关系/承诺/风险/证据
- 工作台 → 客户上下文
- 战略陪伴 → 主动研判和澄清
- 任务模块 → 待办和承诺
- 智能文件导入 → 资料角色和文件关系
- 内部模型 → 抽取/总结/判断/生成

---

## 四、CEO 接口设计

未来不能只给外置 agent 暴露零散 API. 应该设计高层接口:

```
meeting.process
client.refresh_understanding
project.generate_story_card
file_batch.import_with_context
strategy.run_review
clarification.list_and_prepare
weekly_review.generate
task.create_drafts_from_commitments
intel.scan_and_summarize
growth.capture_method_card
```

调用的不是"按钮级接口", 而是"工作级接口".

---

## 五、三层工具体系

| 层 | 用途 | 例子 |
|---|---|---|
| **低层工具** | 系统内部调用, 不一定暴露给外置 | create_task / write_file / query_fact / update_risk |
| **业务工具** | 外置 agent 最适合调用 | meeting.process / file_batch.import_with_context / story_card.generate / weekly_review.generate |
| **CEO 工具** | 目标级指令 | "判断客户卡在哪" / "生成故事卡" / "找下周最值得推进的 5 件事" |

---

## 六、必须预留的 7 个东西

1. **Agent Gateway** — 所有 AI 操作入口统一经过, 判断 actor/permission/approval/audit
2. **Tool Registry** — 系统告诉 AI 有哪些能力可被调用 (tool 元信息 11 字段)
3. **Actor Type** — 区分 human / internal_ai_agent / external_ai_agent / system_daemon / integration_bot
4. **Agent Run Log** — 每次 agent 操作完整记录 (run_id / driver / model / context / 工具调用 / 写入 / 确认 / 失败 / 回滚)
5. **Approval Queue** — 危险动作进入确认队列
6. **Idempotency-Key** — 同 key 只能写一次, 防重试重复
7. **Model Router** — 外置 agent 只发指令, 模型选择和客户数据处理由益语内部控制

---

## 七、AI 客户工作闭环指数 (100 分制)

满分 100, 通过线 ≥ 80, 硬门槛必须全部通过.

### 7 个评分维度

| # | 维度 | 满分 | 关键指标 |
|---|---|---|---|
| 1 | AI 能否不通过界面完成工作调度 | 15 | UI 自动化 0%, API 调用 ≥ 90%, 操作计划 ≥ 6 动作, 调动 ≥ 4 模块, 上下文绑定 100% |
| 2 | AI 是否把资料变成客户理解 | 20 | 新增事实 ≥ 5 / 时间线 ≥ 1 / 风险 ≥ 1 / 承诺 ≥ 1 / 战略判断 ≥ 1, 来源 ≥ 90%, 不确定标记 100% |
| 3 | AI 是否生成"用户能处理"的澄清问题 | 15 | 每次 ≥ 1 / 客户 ≥ 3, 来源对比 100%, 影响说明 100%, 建议动作 100%, 用户能处理 100% |
| 4 | AI 是否把理解转成行动草稿 | 15 | 任务草稿 ≥ 1, 客户/项目绑定 100%, 来源 100%, 截止/负责人 ≥ 80%, 正式发布前确认 100% |
| 5 | 用户纠错后系统是否真记住 | 15 | 纠错入服务 100%, 旧事实标 superseded 100%, 新值权威候选 100%, 后续 5 问不再用旧口径 100%, 故事卡同步 100% |
| 6 | 内置模型和外置 Agent 结果一致 | 10 | 工具重合度 ≥ 70%, 事实重合度 ≥ 80%, 风险/承诺/澄清重合度 ≥ 70%, 同 Gateway 100%, 同 Run Log 100%, 不直写 DB 100% |
| 7 | 安全/审计/人工确认完整 | 15 | 直写 DB 0, 缺上下文写入 0, 危险动作 approval 100%, Agent Run Log 100%, Idempotency 100%, 重复运行 0 重复, 跨客户串数据 0 |

### 7 项硬门槛 (任一失败 = 目标不算完成)

```
1 AI 不操作界面
2 AI 不直接写数据库
3 所有写入绑定上下文 (org/user/client/project/source/actor/run)
4 不能只写 atomic_facts (必须派生 event_line_activities/risk_signals/commitments/clarification_records/strategic_thought_insights/task drafts)
5 危险动作必须进入人工确认
6 必须有 Agent Run Log
7 跨客户隔离必须为 0 错误
```

---

## 八、双驱动同题测试设计

### 测试题

同一段会议纪要:
> "今天和某客户开会, 客户提到下个月想先做教师端试点, 预算还没有最终确认. 项目负责人希望先压缩方案复杂度, 但秘书长担心学校配合度不够. 我们答应下周二前给一版更轻量的试点方案, 同时补充风险控制说明."

### A 组: 内置模型驱动
```
internal_agent → meeting.process → 生成事实/风险/承诺/任务草稿/澄清问题/战略刷新
```

### B 组: 外置 agent 驱动
```bash
yiyu agent run meeting.process --client-id xxx --project-id xxx --mode draft
```

### 对比指标

| 对比项 | 要求 |
|---|---|
| 调用工具 | 两组应基本一致 (重合度 ≥ 70%) |
| 数据写入 | 两组都不能直接写 DB |
| 上下文绑定 | 两组都必须有 org/user/client/project |
| 审计日志 | 两组都必须有 agent_run |
| 危险动作 | 两组都必须进入 approval |
| 数据结果 | 事实/风险/承诺/澄清/任务草稿应基本一致 |
| 用户感知 | 用户看到的结果不应因驱动者不同而割裂 |

通过 = 益语智库已具备双驱动底座.

---

## 九、CLI 设计

```bash
yiyu auth login
yiyu agent tools                                                       # 列工具
yiyu agent plan --goal "处理今天和日慈的会议纪要" --client "日慈基金会"   # 出操作计划
yiyu agent run --plan-id xxx --mode dry-run                            # 模拟
yiyu agent run --plan-id xxx --mode draft                              # 真跑草稿
yiyu agent status --run-id xxx                                         # 查状态
yiyu approvals list                                                    # 列待确认
yiyu approvals approve --id xxx                                        # 批准
yiyu storycard refresh --client "日慈基金会"
yiyu datacenter diff --run-id xxx                                      # 前后对比
```

外置 agent (Codex/Claude/Cursor) 调用这些命令 → Agent Gateway → 权限/Tool Registry/Domain Service/Audit.

---

## 十、外置 agent 的边界 (不是无限权力 CEO)

### 可以做
- 生成操作计划 / 执行只读分析 / 创建候选事实 / 创建任务草稿 / 创建风险候选 / 创建澄清问题 / 刷新故事卡 / 发起审批请求 / 汇报执行结果

### 不能做
- 直接写数据库 / 直接覆盖权威事实 / 直接发材料给客户 / 直接推送飞书群 / 跨客户读取 / 直接删资料 / 把用户口述判断变客户事实 / 修改权限

---

## 十一、内部模型 = 员工 / 外部 agent = CEO / 用户 = 董事长

```
员工 (内部模型, 系统配置):
  AI 撰稿员 / AI 数据员 / AI 风险员 / AI 客户关系员 / AI 情报员 / AI 成长教练

CEO (外部 agent, 通过 CLI/API 调度):
  "让数据员整理这批事实"
  "让风险员检查有没有风险"
  "把结果汇总给我"
  "哪些地方需要人类确认?"

董事长 (用户, 最终责任人):
  是否采纳判断 / 是否确认事实 / 是否对外发送 / 是否正式创建任务 / 是否授权外置 agent 继续推进
```

---

## 十二、3.0 产品表达

**不是**: "我们有很多 AI agent."

**是**: 益语智库 3.0 是一个可被人类和 AI 共同调度的客户工作系统. 人通过界面操作, 内置模型通过系统内部工具工作, 外置 agent 通过授权接口像 CEO 一样调度整个软件.

核心:
- 可授权 / 可调度 / 可审计 / 可确认 / 可回滚 / 可持续理解客户

---

## 十三、R2/R3/R4 三阶段目标

### R2 · 最小通过目标 (下一轮工程验收)

| 指标 | 目标 |
|---|---|
| AI 客户工作闭环指数 | ≥ 70 |
| 硬门槛 | 7 中 ≥ 6 通过 |
| 调用模块 | ≥ 4 |
| 任务草稿 | ≥ 1 条 |
| 澄清问题 | ≥ 1 条 |
| 风险信号 | ≥ 1 条 |
| Agent Run Log | 100% |
| 跨客户串线 | 0 |

### R3 · 产品可用目标 (真实 dogfood 前)

| 指标 | 目标 |
|---|---|
| AI 客户工作闭环指数 | ≥ 80 |
| 硬门槛 | 7/7 通过 |
| 内置/外置一致性 | ≥ 80% |
| 用户纠错保持率 | 100% |
| 故事卡关键段完整率 | ≥ 90% |
| 自然语言回答证据覆盖率 | ≥ 90% |
| 重复运行产生重复数据 | 0 |

### R4 · 真实使用目标 (用户开始依赖)

| 指标 | 目标 |
|---|---|
| 三类客户 dogfood 平均分 | ≥ 80 |
| 用户 10 分钟内能看懂客户状态 | ≥ 80% |
| 每客户有效澄清问题 | ≥ 3 |
| 每客户可执行下一步 | ≥ 3 |
| 使用前后故事卡提升 | ≥ 20% |
| 用户主观"系统更懂客户"评分 | ≥ 4/5 |

---

## 十四、下一轮目标 (一句话)

> 用户交给系统一段真实会议纪要后, 无论由内置大模型驱动, 还是由外置 Agent 通过 API/CLI 驱动, 系统都能不操作界面、不直接写数据库, 安全地生成一份"客户理解与行动包": 包括新增事实/时间线/风险/承诺/澄清问题/任务草稿/故事卡更新和可审计日志.

---

## 十五、6 件用户最终使用对应的事

1. **想快速看懂客户** → 故事卡完整度/时间线/关键人物/风险/下一步/证据来源
2. **想开完会后自动形成行动** → 任务草稿/承诺/截止/负责人/客户+项目绑定
3. **想知道哪里不确定** → 澄清问题数量+质量/来源对比/影响说明
4. **想教会系统** → 纠错回写/旧事实降权/后续回答改变/故事卡刷新
5. **想放心让 AI 操作软件** → 审计日志/人工确认/幂等/上下文绑定/跨客户隔离/不直写 DB
6. **希望外置 Agent 像 CEO 调度系统** → 外置调同一套工具/双驱动结果一致/外置只调度不越权写

---

**钦定**: 顾源源 2026-05-23
**承前**: 09 客观评估报告 (V2.3 38/100) + 10 接口化可行性测试方案
**B 落档**: 2026-05-23
**A AI 状态**: V2.5 P0-1+P0-2 IngestPipeline 实时 trigger 已接通 (clarification_records 真破零)
**下一步**: A 继续 V2.5 P0-3 工作台对话反向入库 + Approval Queue, B 准备 R2 测试
