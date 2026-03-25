# 项目上下文生成 Skill 规格（project-context-builder）

> 关联文档：
> - [docs/project-context-task-link-plan.md](/Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/docs/project-context-task-link-plan.md)
> - [docs/org-model-p0-spec.md](/Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/docs/org-model-p0-spec.md)
> - [docs/org-model-p1-p3-spec.md](/Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/docs/org-model-p1-p3-spec.md)

## 1. 目标

把客户资料、项目资料、会议、任务、复盘、分析结果等原始材料，稳定地转换成 AI 可消费的统一项目上下文。

这个 skill 不是“帮 AI 写一段漂亮介绍”，而是完成 4 件事：

1. 抽取机构/客户背景
2. 抽取项目背景
3. 绑定项目成长标尺
4. 生成面向 AI 和面向人类的结构化简介

输出结果要能同时服务：
- 客户工作台
- 任务与日历
- 战略陪伴
- 成长手册 / 成长引擎
- 资讯情报站
- 后续全局助理

## 2. 核心原则

- 先抽取字段，再生成介绍，不允许直接自由写摘要
- 没证据不补全，不确定就输出 `待确认`
- 所有关键字段尽量回溯证据来源
- 项目级判断优先于模块级局部判断
- 成长判断必须绑定项目上下文，不做脱离项目的泛化打分

## 3. 统一对象

### 3.1 organization_profile

用途：承载机构/客户母体背景。

必填字段：
- `organization_id`
- `name`
- `aliases`
- `organization_type`
- `mission`
- `core_positioning`
- `key_terms`
- `summary_for_ai`
- `source_refs`

推荐字段：
- `main_services`
- `target_groups`
- `stakeholders`
- `industry_context`
- `known_constraints`
- `communication_style`
- `risks_and_red_flags`

### 3.2 project_profile

用途：作为任务、情报、成长、战略陪伴共享的核心上下文对象。

必填字段：
- `project_id`
- `organization_id`
- `name`
- `aliases`
- `project_type`
- `project_intent`
- `current_stage`
- `stage_goal`
- `success_criteria`
- `project_keywords`
- `summary_for_ai`
- `source_refs`

推荐字段：
- `annual_goal`
- `deliverables`
- `key_actions`
- `key_milestones`
- `stakeholders`
- `dependencies`
- `constraints`
- `risks`
- `important_dates`

### 3.3 growth_rubric

用途：把“这个项目当前阶段最需要什么能力、如何判断”结构化。

必填字段：
- `rubric_id`
- `project_id`
- `project_stage`
- `priority_abilities`
- `expected_behaviors`
- `common_mistakes`
- `evidence_signals`
- `summary_for_ai`
- `source_refs`

推荐字段：
- `ability_definitions`
- `stage_specific_expectations`
- `recommended_learning_units`
- `scoring_notes`

### 3.4 evidence_map

用途：把字段和原始证据挂起来，防止生成层脱离事实源。

关键字段：
- `entity_type`
- `entity_id`
- `field_name`
- `source_type`
- `source_id`
- `source_excerpt`
- `confidence`
- `updated_at`

### 3.5 project_match

用途：在任务、会议、情报、成长信号进入系统时，判断它属于哪个项目。

关键字段：
- `matched_project_id`
- `matched_organization_id`
- `match_reason`
- `matched_terms`
- `confidence`
- `resolution`

规则：
- `confidence >= 0.85`：自动绑定
- `0.60 <= confidence < 0.85`：提示确认
- `< 0.60`：不自动绑定

## 4. Skill 能力拆分

### 4.1 extract_context

输入：机构资料、项目资料、会议纪要、任务、复盘、分析结果、历史上下文。

职责：
- 抽取 `organization_profile`
- 抽取 `project_profile`
- 生成 `evidence_map`
- 输出 `unresolved_questions`

输出要求：
- 结构化 JSON 优先
- 不允许只输出自然语言摘要

### 4.2 build_growth_rubric

输入：`project_profile` + 专业框架知识 + 历史沉淀。

职责：
- 识别项目阶段最关键的 3-5 项能力
- 定义做得好的行为表现
- 定义常见误区
- 定义可观察成长证据
- 形成 `growth_rubric`

输出要求：
- 标尺必须跟项目阶段绑定
- 标尺必须可观察，不接受纯抽象评价词

### 4.3 generate_structured_briefs

输入：已抽取的 `organization_profile`、`project_profile`、`growth_rubric`。

职责：
- 生成“客户介绍”
- 生成“项目介绍”
- 生成“当前阶段说明”
- 生成“成长重点说明”

输出要求：
- 只能由结构化字段整理，不允许新增事实
- 对外文案和对 AI 的摘要要区分

## 5. 输入输出契约

### 5.1 输入契约

```json
{
  "organization_documents": [],
  "project_documents": [],
  "meetings": [],
  "tasks": [],
  "reviews": [],
  "analysis_outputs": [],
  "existing_profiles": null,
  "operator_notes": null
}
```

### 5.2 输出契约

```json
{
  "organization_profile": {},
  "project_profiles": [],
  "growth_rubrics": [],
  "evidence_map": [],
  "project_matches": [],
  "unresolved_questions": []
}
```

### 5.3 unresolved_questions 约定

用于承载必须人工确认的信息，避免模型瞎补。

示例：
- “当前资料里出现两个可能的年度目标版本，待确认哪一个生效”
- “项目简称命中了两个历史项目，待人工选择”
- “阶段看起来已进入实施期，但缺少明确阶段定义文本”

## 6. 客户介绍 / 项目介绍固定模板

### 6.1 客户介绍

固定结构：
- 这是谁
- 它为什么存在
- 它主要做什么
- 它当前合作相关的重点背景是什么
- 它有哪些边界、风险或表达禁忌

### 6.2 项目介绍

固定结构：
- 项目名称与归属机构
- 这个项目想解决什么问题
- 当前处于什么阶段
- 这个阶段的目标是什么
- 做成的标准是什么
- 当前最关键的风险和阻力是什么

### 6.3 成长重点说明

固定结构：
- 这个项目当前最看重哪些能力
- 这些能力在本项目里的具体表现是什么
- 常见错误是什么
- 近期最适合补哪条学习或练习

## 7. 和各模块的接入关系

- 客户工作台：提供母体资料、项目背景、长期语境
- 任务与日历：通过 `project_match` 自动识别任务所属项目，读取项目背景做判断
- 战略陪伴：把阶段、目标、风险、关键动作作为推进骨架
- 成长模块：把成长信号绑定到 `growth_rubric`，不再用脱离项目的泛化打分
- 资讯情报站：把候选情报挂到相关项目，判断是否值得转任务或沉淀
- 全局助理：后续根据项目上下文给出“漏步骤”与“最佳路径”提醒

## 8. Skill 执行顺序

统一顺序：

1. 识别组织/项目实体
2. 抽取结构化字段
3. 生成证据映射
4. 构建成长标尺
5. 生成固定格式简介
6. 输出待确认项

不允许倒序。

## 9. 质量闸门

每次运行 skill 后，至少做 5 个检查：

1. `project_profile` 是否有明确 `project_intent`
2. `current_stage` 和 `stage_goal` 是否同时存在
3. `success_criteria` 是否是可观察结果，而不是空话
4. `growth_rubric.priority_abilities` 是否控制在 3-5 项
5. 输出里是否存在“看起来很像常识脑补但没有 source_refs 的字段”

任一失败，都应进入 `unresolved_questions`。

## 10. 第一版落地范围

第一版只要求跑通最小闭环：

- 1 个 `organization_profile`
- 1 个主 `project_profile`
- 1 个 `growth_rubric`
- 任务标题/说明到项目的自动识别
- 基于项目背景的成长判断

先不做：
- 多项目复杂关系图
- 过度自动化的复杂评分系统
- 脱离证据的“高级人格化总结”

## 11. 后续实现建议

为了避免把 skill 做成一次性 prompt，后续实现时建议拆成：

- `context_schema`：字段层
- `context_extractor`：抽取层
- `rubric_builder`：标尺层
- `brief_generator`：生成层
- `project_matcher`：匹配层

这样才能同时服务多个模块，而不是只给某一页写一段介绍。
