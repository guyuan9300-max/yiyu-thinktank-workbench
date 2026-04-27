# 最小输入字段落点审计

本文档列出 6 项最小输入在当前代码中的真实落点。

---

## 1. 益语背景卡

| 项目 | 值 |
|------|---|
| 来源文件 | `backend/app/models.py:1218` |
| 类型 | `OrganizationDnaModuleRecord` |
| 关键字段 | `moduleKey`, `markdownContent`, `normalizedText`, `summary` |
| 前端类型 | `src/shared/types.ts` → `OrganizationDnaModule` (line 1902) |
| 可直接读取 | **YES** — 作为 `build_weekly_review_analysis()` 的直接参数传入 |
| moduleKey 值 | `organization_intro`, `business_intro`, `team_intro`, `market_intro` |

**读取链路：**
`review_analysis.py:2308` → `organization_dna_modules` 参数 → `_select_relevant_modules()` 选取 → 提取 `title` 和 `summary`

**无完整背景卡时的替代：** 无替代。如果没有录入组织 DNA 模块，分析引擎只能基于任务事实做判断。

---

## 2. 客户/项目背景卡

| 项目 | 值 |
|------|---|
| 来源文件 | `backend/app/models.py:894` |
| 类型 | `TaskProjectContextRecord` |
| 关键字段 | `clientId`, `clientName`, `backgroundSummary`, `goalSummary`, `riskSummary`, `infoCompleteness` |
| 前端类型 | `src/shared/types.ts:865` → `TaskProjectContext` |
| 可直接读取 | **YES** — 嵌在 `WeeklyReviewTaskSnapshotRecord.projectContext` 中 |

**读取链路：**
`WeeklyReviewTaskEntryRecord` → `.taskSnapshot.projectContext` → `review_analysis.py:469-470` `_project_context_summary()` 提取 goals/risks

**构建过程：**
`main.py:7635` `build_task_project_context()` 从以下来源合成：
- 客户 DNA 模块（`business_intro`, `organization_intro`）
- 目标记录（`goal_records`）
- 会议记录
- 文档摘要
- 任务描述中的关键词提取

**无完整背景卡时的替代：** `ClientSummary`（`models.py:481`）有 `name`, `domain`, `type`, `intro`, `stage`，但信息深度远不如完整的 `TaskProjectContext`。新增的 `ClientStrategicProfileRecord` 有 `industry`, `scale`, `influence`, `strategicValueToYiyu` 等更深层字段。

---

## 3. 组织或部门季度主线卡

| 项目 | 值 |
|------|---|
| 来源文件 | `backend/app/models.py:305` |
| 类型 | `OrgFocusItemRecord` |
| 关键字段 | `title`, `statement`, `status` |
| 部门计划 | `OrgDepartmentPlanItemRecord`（`models.py:317`）：`title`, `statement`, `status`, `priority` |
| 前端类型 | `src/shared/types.ts:246` → `OrgFocusItemSettings` |
| 可直接读取 | **PARTIAL** — 通过 `OrgModelProfileRecord` 间接传入 |

**读取链路：**
`build_weekly_review_analysis()` → `org_model_profile: OrgModelProfileRecord` 参数 → `_focus_item_reference_texts()` 提取 → `_department_plan_reference_texts()` 提取

**任务链接方式：**
任务通过 `TaskOrgContextRecord.focusItemId`（`models.py:886`）链接到机构重点，通过 `departmentPlanItemId` 链接到部门计划。

**无完整主线卡时的替代：** 组织 DNA 模块中的 `organization_intro` 可能包含季度目标文字（通过正则 `_extract_quarter_goal_lines()` 提取），但精度远低于正式录入的 `OrgFocusItemRecord`。

---

## 4. 任务标题

| 项目 | 值 |
|------|---|
| 来源文件 | `backend/app/models.py:817` |
| 类型 | `TaskRecord` |
| 字段 | `title: str` (line 819) |
| 快照位置 | `WeeklyReviewTaskSnapshotRecord.title` (line 1531) |
| 前端类型 | `src/shared/types.ts:786` → `Task.title` |
| 可直接读取 | **YES** |

**读取链路：**
`WeeklyReviewTaskEntryRecord` → `.taskSnapshot.title` → `review_analysis.py:128` `_item_text()` → 用于事件线分组、假设生成、标签匹配

---

## 5. 任务说明

| 项目 | 值 |
|------|---|
| 来源文件 | `backend/app/models.py:817` |
| 类型 | `TaskRecord` |
| 字段 | `desc: str` (line 820) |
| 快照位置 | `WeeklyReviewTaskSnapshotRecord.desc`（如果存在于快照中） |
| 前端类型 | `src/shared/types.ts:786` → `Task.desc` |
| 可直接读取 | **PARTIAL** |

**关键说明：**
任务描述（`desc`）**不是直接传入** review analysis 的。它在 `build_task_project_context()`（`main.py:7635`）中被**消费并转化**为：
- `backgroundSummary` — 从描述中提取的背景信息
- `goalSummary` — 从描述中提取的目标线索
- `riskSummary` — 从描述中提取的风险线索

也就是说，原始 `desc` 经过加工后以 `TaskProjectContext` 的形式进入分析引擎。

**无加工时的替代：** 可以直接从 `taskSnapshot` 读取 `desc` 字段（如果快照中包含）。

---

## 6. 任务复盘资料

| 项目 | 值 |
|------|---|
| 来源文件 | `backend/app/models.py:1690` |
| 类型 | `WeeklyReviewTaskEntryRecord` |
| 关键字段 | `note: str`（自由叙述）, `structuredNote: WeeklyReviewTaskStructuredNoteRecord` |
| 前端类型 | `src/shared/types.ts` → `WeeklyReviewTaskEntry` |
| 可直接读取 | **YES** — 作为 `items` 参数直接传入分析引擎 |

**结构化笔记字段（`WeeklyReviewTaskStructuredNoteRecord`，`models.py:1661`）：**
| 字段 | 类型 | 说明 |
|------|------|------|
| `reflection` | `str` | 叙述性反思 |
| `lightweightTag` | `Literal["", "资料不足", "等待他人", ...]` | 轻量卡点标签 |
| `progress` | `str` | 进展描述 |
| `completionStatus` | `Literal["done_on_time", "done_late", "in_progress", "not_done"]` | 完成状态 |
| `successExperience` | `str` | 成功经验 |
| `blockerReason` | `str` | 阻碍原因 |
| `failureInsight` | `str` | 失败教训 |
| `supportNeeded` | `str` | 需要支持 |
| `nextAction` | `str` | 下一步 |

**读取链路：**
`review_analysis.py:2313` → `_reflection_text(item)` 提取 reflection → `_lightweight_tag(item)` 提取标签 → 用于证据权重计算、假设生成、完成率统计

---

## 总结

| # | 输入 | 类型 | 可直接读取 | 备注 |
|---|------|------|-----------|------|
| 1 | 益语背景卡 | `OrganizationDnaModuleRecord` | YES | 直接参数 |
| 2 | 客户/项目背景卡 | `TaskProjectContextRecord` | YES | 嵌在 task snapshot |
| 3 | 季度主线卡 | `OrgFocusItemRecord` | PARTIAL | 需要通过 org profile 间接读 |
| 4 | 任务标题 | `TaskRecord.title` | YES | 在 snapshot |
| 5 | 任务说明 | `TaskRecord.desc` | PARTIAL | 被消费为 project context |
| 6 | 任务复盘资料 | `WeeklyReviewTaskEntryRecord` | YES | 直接参数 |

**结论：** 6 项最小输入中，4 项可直接读取，2 项需要调整读取方式（季度主线卡需要补充直接传入路径，任务说明需要保留原始 desc 到分析链路中）。
