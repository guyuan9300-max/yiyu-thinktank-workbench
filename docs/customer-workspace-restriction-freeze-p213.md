# Customer Workspace Restriction Changes P2.13

目的：这份文件不再冻结旧限制，而是记录 **2026-04-22** 这一轮已主动拆除的客户工作台回答限制。

本轮结论已经通过真实运行态和日志确认：
- `介绍客户/机构` 类问题会被若干通用词误判成 `meeting_summary / evidence_question / task_next_action`
- 一旦进入这些 intent，后续就会连锁落入：
  - `work_status / short_synthesis`
  - `answerShape = meeting_summary / evidence_answer / task_next_action`
  - `generationProfile = short / standard`
  - `maxAnswerChars = 1200`
- 结果就是：明明在问组织画像，却稳定得到偏短、偏谨慎、偏任务/状态的回答

这轮的目标不是继续冻结，而是**拆掉这些限制**，让介绍类问题优先走组织画像链。

## 已移除的限制

### 1. workspace query 的 `work_status` 抢占
- 文件：
  - `/Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/backend/app/services/workspace_query_router.py`
- 变化：
  - 新增 `intro priority` 识别
  - 当 prompt 明确是介绍/组织画像问题时，即使里面出现 `风险 / 下一步 / 会议纪要` 等负面限制词，也优先走：
    - `workflow = synthesis`
    - `generationMode = long_synthesis`
    - `intent = intro_profile`

### 2. page intent 把“怎么做”误判成任务下一步
- 文件：
  - `/Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/backend/app/services/analysis_context.py`
- 变化：
  - `_TASK_NEXT_TOKENS` 移除了过宽的 `"怎么做"`
  - 增加 `intro priority` 识别
  - 对于“介绍客户/机构 + 方法/业务线/升级方向”的问题，优先返回：
    - `intent = intro_profile`

### 3. route decision 沿用上游误判
- 文件：
  - `/Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/backend/app/services/query_router.py`
- 变化：
  - 只要 prompt 命中介绍类路由，直接归一化成：
    - `intro_profile` 或 `project_intro`
  - 不再保留上游误判出来的 `task_next_action / meeting_summary / evidence_question`

### 4. question focus 被 advice/status/evidence 拉偏
- 文件：
  - `/Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/backend/app/services/question_focus.py`
- 变化：
  - 对 `intro_profile / project_intro` 增加 `intro priority`
  - 介绍类问题默认保持：
    - `goal = define`
    - `subjectFacet = identity`
  - 不再因为 prompt 里出现少量 `依据 / 风险 / 下一步` 词就改成 `evidence / advice / status`

### 5. intro answer 的长度和 section 过窄
- 文件：
  - `/Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/backend/app/services/answer_layer.py`
  - `/Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/backend/app/models.py`
- 变化：
  - `intro_profile.requiredSections` 增加：
    - `一句话优势总结`
  - `intro_profile.maxAnswerChars = 2600`
  - `business/strategy/project.maxAnswerChars = 2200`
  - schema 默认 `maxAnswerChars` 从 `1200` 提升到 `1800`

### 6. intro 的运行时 profile 太保守
- 文件：
  - `/Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/backend/app/main.py`
- 变化：
  - `focused_context` 的上下文预算从：
    - `7000 / 3200`
  - 放宽到：
    - `12000 / 5000`
  - `identity` 焦点指令的目标长度从：
    - `1100-1800`
  - 放宽到：
    - `1400-2600`

## 验证目标

以下 prompt 应稳定保留在组织画像链，而不是落成 `meeting_summary / evidence_question / next_actions`：

1. `介绍日慈基金会，它是怎么做这件事的？`
2. `介绍日慈基金会，但不要写成会议纪要或状态汇报。`
3. `介绍日慈基金会，不要展开风险和下一步建议。`
4. `介绍日慈基金会，请按顺序回答它是什么样的机构、它真正想解决的核心问题、它是怎么做这件事的、它有哪些主要业务线、它正在往什么方向升级、用一句话总结它最核心的优势。`

期望结果：
- `answerIntent = intro_profile`
- `routeIntent = intro_profile`
- `focusGoal = define`
- `focusFacet = identity`
- `answerShape = direct_profile`
- `generationProfile = focused_context` 或 `long`
- 回答不再稳定卡在 500-600 字的三段短答

## 注意

这份文件保留在原路径，是为了记录这轮拆除的是什么限制。  
它不再代表“冻结这些旧限制继续生效”。
