# 益语智库平台 — 决策日志

## 2026-04-05 — 建立自定义技能库

**Context**: 项目涉及多个技术栈，每次新会话都需重新建立上下文，反复遇到相同类别问题。
**Decision**: 创建 5 个自定义技能 + 安装 engineering 插件。
**Alternatives considered**: 使用 Everything Claude Code（ECC）全家桶 — 太重、不稳定。
**Consequences**: 每次会话自动加载相关知识，Cowork 和终端版共享同一套技能。
**Reversibility**: Easy

## 2026-04-05 — Cowork 与终端版 Claude Code 并行使用

**Context**: Cowork 桌面版体验好（图片、文档、架构图），但需挂载文件夹才能写代码；终端版能直接改代码但不能看图片。
**Decision**: 两边并行使用，各取所长。代码密集工作用终端版，UI 分析/文档/架构图用 Cowork。技能和项目记忆两边共享。
**Consequences**: 需要在项目目录下维护 project-memory/ 文件夹，两边都能读写。
**Reversibility**: Easy

## 2026-04-05 — 事件线活动分类（is_key 字段）

**Context**: 事件线里系统痕迹（状态变更、字段更新）太多，淹没了真正重要的活动。
**Decision**: event_line_activities 表新增 is_key 字段，区分关键事件和系统痕迹，默认只展示关键事件。
**Consequences**: 事件线更清晰，但需要确保所有新增活动类型正确设置 is_key。
**Reversibility**: Easy

## 2026-04-05 — 本地附件缓存策略

**Context**: 附件从云端拉取很慢，影响事件线浏览体验。
**Decision**: 首次从云端拉取后缓存到 ~/Library/Application Support/YiyuThinkTankWorkbench/Cache/event-line-attachments/，后续秒加载。
**Consequences**: 需要管理缓存大小和过期策略（暂未实现）。
**Reversibility**: Easy

## 2026-04-04 — 数据架构按三层主权模型重构

**Context**: 原来的数据架构图没有清晰区分本地/云端/LAN 三层数据归属。
**Decision**: 将数据架构图按三大模块展开，每个对象明确标注数据主权归属。
**Consequences**: 所有新增对象必须先确定数据主权层，再设计存储方案。
**Reversibility**: Medium

## 2026-04-03 — 任务系统前台保持"滴答清单级轻量"

**Context**: 2026 战略明确提出"不要陷入工具战争"，客户抗拒学习成本高的系统。
**Decision**: V1 冻结范围：单任务、单负责人、接收/退回、周计划/周总结、部门汇总、基础预警。
**Consequences**: 所有新增功能必须先问"是否直接服务 OS V1、标准件或标杆客户"。
**Reversibility**: Easy
