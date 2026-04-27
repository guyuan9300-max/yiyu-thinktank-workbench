# Customer Workspace Answer Freeze P2.12

目的：当前客户工作台回答链已经开始产出可用结果，但仍处于“先稳定成功，再整体拆旧链”的阶段。

本文件不是设计稿，而是**冻结清单**。下面这些硬编码当前直接影响：
- `介绍客户/机构` 的回答结构
- 证据优先级和机构画像资料命中
- 模型超时后的 fallback 内容
- 前端回答卡与工作轨迹的用户感知

在明确进入“整体拆旧链”之前，这些位置**不要随手改**。任何改动都必须同步更新：
- 本文件
- `backend/tests/test_customer_workspace_answer_freeze_p212.py`

## 冻结范围

### 1. 回答结构冻结
- `/Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/backend/app/services/answer_layer.py`
  - `required_sections_map`
  - `build_grounded_answer_context()` 中的 `【回答结构】`、`【写作要求】`、`【禁止事项】`

### 2. 组织画像上下文冻结
- `/Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/backend/app/services/workspace_data_center_adapter.py`
  - `【组织画像目标】`
  - `【组织画像参考草稿】`
  - `【原始证据摘录】`

### 3. 机构画像 fallback 冻结
- `/Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/backend/app/main.py`
  - `_build_intro_problem_points`
  - `_build_intro_method_points`
  - `_build_intro_business_lines`
  - `_build_intro_upgrade_paragraph`
  - `_build_intro_advantage_summary`
  - `build_intro_profile_answer_from_evidence`
  - identity 场景的 `focus_instruction`

### 4. 证据提权和语义标记冻结
- `/Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/backend/app/services/source_semantics.py`
  - `institution_identity / program_overview / method_or_model / strategy_direction` 的规则词
- `/Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/backend/app/services/evidence_selector.py`
  - `_profile_anchor_bonus()` 的提权锚点

### 5. 回答区 UI 冻结
- `/Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/src/renderer/App.tsx`
  - 成功回答默认只保留正文，不再渲染 `Context Quality / 本轮来源 / 诊断 / 本轮路由 / 证据下钻` 这些下层壳
  - 失败态、文件检索态、工作状态态仍可保留结构化面板
  - `工作轨迹` 标题与 `原始证据 / 背景线索 / 联网补充` 统计口径只保留给运行中轨迹，不再进入成功回答正文区
- `/Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/backend/app/services/workspace_answer_experience.py`
  - `headline_map / user_message_map / trustSignals`
- `/Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/src/shared/mainChainPresentation.ts`
  - 路由标签、意图标签与解释文案
- `/Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/src/shared/types.ts`
  - `WorkspaceAnswerPresentationSection.title`

## 当前明确冻结的关键文案/结构

### `intro_profile` 的结构
1. `它是谁`
2. `它在解决什么问题`
3. `它的核心方法是什么`
4. `主要业务板块`
5. `它正在往哪升级`

### 运行态 identity focus 的固定顺序
1. 一句组织定义
2. `1）它主要在解决什么问题`
3. `2）核心方法（教育现场 + 数据与路径 + 生态协作）`
4. `3）主要项目与业务板块`
5. `4）当前组织升级方向`
6. `5）一句话优势总结`

### 当前刻意压制的扩展项
- 近期动态
- 风险
- 待确认事项
- 下一步建议
- proposal / execution 动作

## 为什么现在先冻结
- 当前最大价值不是“让代码更干净”，而是**让客户工作台先稳定成功**。
- 这些硬编码目前就是把运行态结果压到正确位置的关键支架。
- 如果现在边成功边继续漂移，很容易把已经跑通的链重新打散。
- 当前新的前端原则是：**成功回答先看正文，诊断壳不再抢主视觉。**

## 未来拆除条件
只有当下面两件事都成立时，才进入整体拆除：
- `介绍客户/机构` 类问题在真实运行态中稳定成功
- 新的通用回答配置层或 schema 层已经接住这些结构与词汇，不再靠散落在代码里的硬编码支撑
