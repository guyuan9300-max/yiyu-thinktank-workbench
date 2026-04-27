# 战略陪伴「学习清单」接通成长工作台（第一版）

## 1. 本次改了哪些内容

### 1.1 前端：战略陪伴学习清单从占位页改为真实页面
- 新增组件：`src/renderer/components/strategic_accompaniment/StrategicLearningListPanel.tsx`
- 替换占位渲染：`src/renderer/components/strategic_accompaniment/StrategicBrainView.tsx`
  - 原“我渴望学习更多 / 学习清单功能将上线”已被替换。
  - 现在会拉取成长工作台快照并展示 5 个板块：
    1) 当前最值得练
    2) 当前任务学习点
    3) 可复用方法卡
    4) 依据与缺口
    5) 完成后沉淀
- 页面动作打通：
  - 转为任务
  - 记录经验（跳转成长手册兜底）
  - 查看依据
  - 打开上下文

### 1.2 前端 API：扩展 getGrowthWorkbench 调用参数（保持兼容）
- 修改：`src/renderer/lib/api.ts`
- `getGrowthWorkbench()` 支持可选参数：
  - `weekLabel?: string`
  - `clientId?: string | null`
  - `mode?: 'global' | 'strategic'`
- 不传参数时，保持原行为（兼容成长手册原调用）。

### 1.3 前端类型：扩展快照作用域字段（不破坏旧枚举）
- 修改：`src/shared/types.ts`
- 为 `GrowthWorkbenchSnapshot` 增加 optional 字段：
  - `scopeMode?: 'global' | 'strategic'`
  - `scopeClientId?: string | null`
  - `scopeClientName?: string | null`
- `sourceMode` 枚举仍保持旧值，不引入破坏性变更。

### 1.4 App 透传动作回调
- 修改：`src/renderer/App.tsx`
- 为战略学习清单透传：
  - `flash`
  - `onTasksReload`
  - `onNavigate`
  - `onOpenContext`
  - `onCreateTaskFromLearning`

### 1.5 后端：/api/v1/growth/workbench 增加战略模式
- 修改：`backend/app/main.py`
- 扩展接口查询参数：
  - `weekLabel`
  - `clientId`
  - `mode`（`global` 默认，新增 `strategic`）
- 新增战略模式分支：
  - strategic 下按“真实任务优先 + 规则匹配”构建学习快照
  - 无任务时返回基础训练方法卡（不再空白）
  - `reasoningTrace` 固定 `rules_only`，并清空 `aiContribution`

### 1.6 后端模型：快照作用域字段
- 修改：`backend/app/models.py`
- 为 GrowthWorkbenchSnapshot 对应记录增加：
  - `scopeMode`
  - `scopeClientId`
  - `scopeClientName`

### 1.7 后端规则中心：预置方法卡体系（12 张）
- 新增：`backend/app/services/learning_presets.py`
- 包含：
  - `LearningPresetCard` 数据结构
  - `list_learning_presets`
  - `match_learning_presets`
  - `default_starter_learning_presets`
  - 预置卡与快照字段转换函数
- 第一版已落地 12 张核心卡：
  - 机构介绍三段式
  - 项目介绍五要素
  - 事实、判断、建议分离卡
  - 证据够不够检查卡
  - 会议纪要四分法
  - 下一步行动提取卡
  - 会前 3 个必须确认的问题
  - 候选判断转正式判断卡
  - 一页简介写作卡
  - 项目风险扫描卡
  - 方法卡写作卡
  - 缺失信息追问卡

### 1.8 测试
- 新增：`backend/tests/test_strategic_learning_workbench.py`
- 覆盖：
  - 默认 global 模式兼容
  - strategic 无任务不空白
  - 介绍基金会任务命中预置卡
  - 会议纪要任务命中预置卡
  - 正式判断任务命中预置卡
  - strategic 不调用 AI（rules_only）

## 2. 已执行检查（当时结果）
- 通过：
  - `cd backend && uv run pytest tests/test_strategic_learning_workbench.py`
  - `cd backend && uv run pytest tests/test_growth_workbench.py`
  - `npm run build:main`
  - `npm run build:renderer`
  - `npm run build:backend-check`
- 不存在脚本：
  - `npm run typecheck`
  - `npm run lint`
- `test_api_smoke.py` 存在若干历史失败项（与本次学习清单接通非同一问题域）。

## 3. 接下来的详细计划（第二阶段）

### 阶段 A：稳定性与一致性补强（优先）
1. 补充前端交互回归测试
- 验证 “全部客户 / 单客户”切换时请求参数正确。
- 验证 `selectedClientId` 变化后学习清单会重算，不残留旧数据。

2. 对齐 strategic/global 字段合同
- 全面检查 `scopeMode/scopeClientId/scopeClientName` 在前后端的空值语义。
- 补充 JSON 序列化快照样例到测试夹具。

3. 动作按钮失败兜底
- `转为任务` 失败时明确提示并保持页面状态。
- `记录经验` 若无法直写，统一跳转成长手册并给出可操作提示。

### 阶段 B：规则匹配效果优化
1. 调整预置卡打分权重
- 对“介绍/会议/判断/下一步”四类高频意图做更稳定排序。
- 控制方法卡展示数量（默认 4，最多 6）与去重策略。

2. 任务筛选精细化
- 补强 `task_client_matches` 对上下文字段的覆盖（以现有字段为准）。
- 对“会议行动项衍生任务”添加更明确识别标记。

3. 空态说明与引导文案
- 进一步简化空态文案，减少长段解释。
- 增加“如何从客户工作台快速生成学习任务”的快捷引导。

### 阶段 C：可观测与运维
1. 增加 strategic 命中日志（仅开发态）
- 记录匹配卡片 ID、命中关键词、任务来源类型。
- 不输出敏感文本正文。

2. 增加轻量诊断入口（可选）
- 允许在开发环境查看“为何推荐这张卡”。
- 与 `reasoningTrace` 保持一致，不新增外部 API。

### 阶段 D：第二版能力预留（不在本次强制）
1. 扩展预置卡库到 24/42 张
- 保持“规则可解释、可复用、可沉淀”标准。

2. 上下文联动增强
- 与事件线、项目认知、会议沉淀做更细粒度联动。
- 保持“不自由生成结论”的边界。

3. 评估 AI 情境化改写开关（默认关闭）
- 仅对既有预置卡做文案情境化，不允许替代规则判断。

## 4. 交付边界说明
- 第一版核心目标已实现：学习清单已从占位页切换为可用页，并接入真实数据与规则方法卡。
- 本文档记录的是“已完成改造 + 下一阶段可执行计划”，后续可按阶段逐步落地。
