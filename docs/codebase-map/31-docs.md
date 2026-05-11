# docs/ 文档主题索引

## 文档清单

### calendar-week-context-retrieval-and-prompt-spec.md（316 行）

标题：日历周判断：取数与指令规格

首段：
```
## 1. 目标

这份规格只解决一个问题：

`怎样让 AI 生成的周判断更像真实管理判断，而不是通用空话。`
```

### calendar-week-intelligence-implementation-plan.md（326 行）

标题：日历模块周判断系统实施计划

首段：
```
## 1. 实施目标

把当前 `周复盘` 从“任务复盘填写页”升级成：

`低人工输入 + 高背景注入 + 高洞察输出` 的周判断系统
```

### calendar-week-intelligence-spec.md（393 行）

标题：日历模块周判断系统设计规格

首段：
```
> 对齐说明（2026-03-21）：
> 本文档继续作为 `P2` 的核心规格，但其上位原则已明确为：
> 总结与周判断优先利用背景母盘、计划层和执行痕迹，不应额外增加员工填报负担。
> 后续实现以 [AI 背景优先总规划](./ai-context-first-rollout-plan.md) 和
> [全局模块改造清单与阶段路线图](./global-module-refactor-roadmap.md) 为主。
```

### developer-id-signing-notarization.md（139 行）

标题：Mac Developer ID 签名与公证准备清单

首段：
```
## 目标

本阶段只做官网分发，不上架 Mac App Store。

目标效果：
```

### event-line-implementation-plan.md（306 行）

标题：事件线系统实施计划

首段：
```
## 1. 实施目标

把“事件线”从概念落到可运行系统，使其成为：

- 任务与日历里的工作主线对象
```

### event-line-spec.md（350 行）

标题：事件线系统设计规格

首段：
```
## 1. 定位

事件线不是标签，也不是另一种任务列表。

它是：
```

### event-line-week-summary-spec.md（400 行）

标题：事件线式周判断规格

首段：
```
## 1. 目标

这份规格只解决一个问题：

`如何把周总结从任务流水账，升级成面向管理者可读、面向 AI 可推理的事件线式周判断。`
```

### feishu-single-bot-phase1-plan.md（250 行）

标题：Feishu Single-Bot Phase 1 Plan

首段：
```
## Goal

在不改客户工作台核心架构的前提下，为益语智库增加一个飞书单机器人入口。

Phase 1 只解决两件事：
```

### handoff-followup-2026-05-11.md（229 行）

标题：益语智库项目接手评估报告（2026-05-11）

首段：
```
本报告是基于 `docs/project-handoff-2026-05-11.md` 完成的接手评估。仓库已在
`/Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench`，工作区 dirty，
未做任何写入或 reset 动作；本次只读评估 + 决策清单。

## 0. 一句话结论
```

### mac-release-update-plan.md（126 行）

标题：官网分发与应用内更新总计划

首段：
```
## 目标

- 首发模式：官网分发版，不走 Mac App Store。
- 安装体验：用户第一次从官网下载安装包，双击后可以安装并正常运行。
- 更新体验：用户安装后，软件内可以提示新版本、下载新版，或在必要时引导安装。
```

### org-model-foundation-plan.md（551 行）

标题：组织模型层落地计划（任务与周总结系统）

首段：
```
## 1. 目标定义

本期不是做一个好看的组织架构页，而是补一层可被系统和 AI 共同读取的“组织语义底座”，让以下能力从模拟走向真实：

- 部门总结
```

### org-model-p0-spec.md（537 行）

标题：组织模型层 P0 规格（数据库 + 接口 + 页面字段）

首段：
```
> P1-P3 的延续规格见：[docs/org-model-p1-p3-spec.md](/Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/docs/org-model-p1-p3-spec.md)

## 1. P0 范围

P0 只做组织语义底座，不做复杂流程引擎，不做 HR 档案库，不做绩效系统。
```

### org-model-p1-p3-spec.md（619 行）

标题：组织模型层 P1-P3 规格（计划、流程、趋势与业务对象）

首段：
```
## 1. 文档目标

本文件承接：
- [docs/org-model-foundation-plan.md](/Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/docs/org-model-foundation-plan.md)
- [docs/org-model-p0-spec.md](/Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/docs/org-model-p0-spec.md)
```

### org-permission-redesign-shell.md（369 行）

标题：组织与权限 — 新壳设计文档

首段：
```
> 给 Jeana 的完整壳搭建说明。搭完壳后我们再接通后端数据。

---

## 一、背景
```

### organization-strategy-plan-tree.md（429 行）

标题：组织战略树 / 部门计划树 / 月度执行树设计稿

首段：
```
> 对齐说明（2026-03-21）：
> 本文档描述的是组织计划分解的结构层，但后续执行顺序已调整：
> `年度战略 -> 季度承接` 归入 `P1` 的 AI 背景母盘，
> `部门月度计划 -> 任务 / 日历 / 会议` 归入 `P2` 的执行浅入口。
> 统一以 [AI 背景优先总规划](./ai-context-first-rollout-plan.md) 和
```

### project-context-builder-skill-spec.md（314 行）

标题：项目上下文生成 Skill 规格（project-context-builder）

首段：
```
> 关联文档：
> - [docs/project-context-task-link-plan.md](/Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/docs/project-context-task-link-plan.md)
> - [docs/org-model-p0-spec.md](/Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/docs/org-model-p0-spec.md)
> - [docs/org-model-p1-p3-spec.md](/Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench/docs/org-model-p1-p3-spec.md)

```

### project-context-task-link-plan.md（264 行）

标题：项目背景源接入任务系统实施方案

首段：
```
> 对齐说明（2026-03-21）：
> 本文档继续作为“项目上下文链”的专项设计使用，但现在应放在
> [全局模块改造清单与阶段路线图](./global-module-refactor-roadmap.md) 的框架下理解。
> 它的核心职责已收口为：
> `项目上下文 -> 任务识别 -> 周判断 -> 成长解释`。
```

### project-handoff-2026-05-11.md（245 行）

标题：益语智库项目交接资料（2026-05-11）

首段：
```
## 0. 当前交接结论

当前最重要目标不是做正式发布，而是先产出一个“本机安装、打开、基础功能通过”的内部测试 DMG，再发给同事安装测试。

交接时必须先守住四件事：
```

### release-process.md（156 行）

标题：官网版 Mac 发版流程

首段：
```
## 目标

- 首次安装通过官网下载安装包完成。
- 后续版本通过软件内更新提示完成下载与安装。
- 发版动作由受控构建机或 CI 完成，不在普通用户机器上执行。
```

### release-rollback.md（127 行）

标题：官网版发版回滚方案

首段：
```
## 目标

- 当新版本安装、启动、更新或核心流程出现严重问题时，可以快速切回上一版本。
- 回滚优先保证：
  - 用户仍可安装
```

### sync-boundary.md（69 行）

标题：数据同步边界定义

首段：
```
## 原则

- 结构化数据同步到云端（任务、日程、复盘、组织配置、事件线）
- 本地文件不同步（导入的 Word/PDF 原始文件、问答向量）
- 原因不是保密，而是避免"污染"——每个人的文件库不同，同步会干扰
```

### thread-sync.md（7093 行）

标题：Thread Sync

首段：
```
## 2026-04-03 客户工作台回答产物按钮收口
- 线程目标：收口客户工作台中“建立向量 / 导出文件”两个按钮偶发看起来没反应的问题，并确认导出 Word 的真实归档行为。
- 已读文件：
  - `src/renderer/App.tsx`
  - `src/renderer/lib/api.ts`
```

