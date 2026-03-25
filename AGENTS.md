# AGENTS.md - yiyu-thinktank-workbench

## Project Identity

当前项目是**桌面优先的内部工作系统**，不是单一任务软件，也不是单一知识库。

当前主结构分为两条线：
- 本地知识与判断线：客户工作台、资料导入、知识底座、AI 问答、事件线记忆、战略判断
- 共享业务与协作线：账号、审批、任务协作、周复盘、管理视角、组织搭建

## Critical Files

当前关键底座在：
- `backend/app/models.py`
- `cloud_backend/app/models.py`
- `backend/app/main.py`
- `backend/app/services/*`
- `src/shared/types.ts`
- `src/renderer/components/tasks/*`

如果要改“日历与任务判断系统”，先读这些文件，再看其他页面。

## Non-Negotiables

不允许：
- 先做新抽象，再回头找落点
- 继续形成双真源
- 证据不足时强写业务判断
- 把结构问题伪装成业务风险
- 前后端维持两套判断系统

默认约束：
- 优先复用现有对象与接口
- 优先收口已有 heuristics，而不是新增第三套逻辑
- 所有 judgment output 都必须能追溯到 evidence / facts / snapshot
- 所有 UI 改动都必须指出对应后端链路和共享类型
- 所有非平凡设计都必须先做外部模式扫描，优先参考官方文档、成熟产品和稳定开源项目，不允许只靠主观想象拍板

## Existing Reality

当前仓库已经存在的关键判断对象包括：
- `OrganizationNotebookSnapshot`
- `EventLineMemorySnapshot`
- `MemoryFact`
- `ClarificationRecord`
- `MemoryStatus`
- `BackgroundReadiness`
- `EventLineContextBundleRecord`
- `EventLineJudgmentRecord`
- `TaskContextPreviewRecord`
- `EventLineSummaryCardRecord`
- `ManagementSignalCardRecord`
- `StrategicCockpitSnapshotRecord`

不要假装这些对象不存在。当前任务不是从零设计判断系统，而是把已有底座收敛成更可信的一条链。

## Required Workflow

任何阶段：
1. 先写 docs
2. 再做实现
3. 再做挑战
4. 再更新 release gate

没有审计，不许设计。  
没有外部模式扫描，不许做非平凡路线裁决。  
没有收敛，不许实现。  
没有挑战，不许宣称完成。  
没有 release gate，不许进入下一主题。

当前项目级工作流文档位于：
- `docs/virtual-team/charter.md`
- `docs/virtual-team/reality-audit.md`
- `docs/virtual-team/external-pattern-scans.md`
- `docs/virtual-team/strategy-debates.md`
- `docs/virtual-team/active-plan.md`
- `docs/virtual-team/release-gates.md`

## Virtual Team Roles

当前虚拟项目组使用真实软件岗位，而不是抽象方法论角色：
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

原则：
- 先让真实岗位各自给出判断，再由主编排者裁决
- 不是简单分工，而是先讨论最佳路径，再实施最小改动
- 必须保留一个专门负责“去外部找成熟模式”的岗位，避免团队闭门造车

## Current P0 Scope

一期只围绕“日历与任务判断系统”推进：
1. 真源收口
2. 统一判断对象
3. 低完整度降级输出
4. 附件/会议最小摘要预处理
5. 任务详情 AI 面板与周判断统一后端链
6. 判断页面首屏骨架重构
7. 动作卡可闭环
