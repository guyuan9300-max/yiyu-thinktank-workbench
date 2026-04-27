# Reality Audit — Round 1

审计日期：2026-04-06

## 一句话现状

**记忆系统的写入管道已经建好并在运转，但理解层（understanding_builder）没有接入任何正式链路，记忆写了但几乎不被读回来用。**

---

## 已确认存在且运转的系统

| 系统 | 文件 | 状态 | 说明 |
|------|------|------|------|
| memory_foundation | backend/app/services/memory_foundation.py (1888行) | ✅ 运转中 | 写 memory_facts + org_notebook + event_line_memory，task/review/meeting 都触发写入 |
| understanding_builder | backend/app/services/understanding_builder.py | ⚠️ 存在但未接入 | 能生成 4 层理解（是什么/为什么重要/推进到哪/还缺什么），但只在测试文件中调用，**main.py 没有调用它** |
| review_analysis | backend/app/services/review_analysis.py (2724行) | ✅ 深度使用 | 每次周复盘都计算：事件线故事、趋势信号、指标卡、假说、下周重点 |
| review_rollup | backend/app/services/review_rollup.py (1461行) | ✅ 运转中 | 部门级汇总、员工维度聚合、跨团队协调检测 |
| review_narrative | backend/app/services/review_narrative.py (962行) | ✅ 运转中 | AI 叙事分析、周概述生成，已接入 local_memory |
| growth_engine | backend/app/services/growth_engine.py (2979行) | ✅ 深度使用 | 5 个 ingest 入口（task/meeting/review/strategic/handbook），写 signal + evidence + XP |
| local_memory | backend/app/services/local_memory.py | ✅ 运转中 | 文件系统记忆（project/event_line/weekly markdown），含 dream cycle 自动整理 |
| badge_engine | backend/app/services/badge_engine.py | ✅ 运转中 | 自动检测徽章解锁条件，写 signal + evidence + XP |

## 记忆写入链路（谁触发了什么写入）

| 用户动作 | 写入 memory_facts | 写入 notebook | 写入 event_line_memory | 写入 growth_signal | 写入 local_memory 文件 |
|---------|------------------|--------------|----------------------|-------------------|---------------------|
| 创建任务 | ❌ | ❌ | ❌ | ✅ | ❌ |
| 更新任务 | ❌ | ❌ | ❌ | ✅ | ❌ |
| 提交周复盘 | ✅ via writeback | ✅ refresh | ✅ refresh | ✅ per task entry | ✅ weekly + project + event_line |
| 发布会议 | ✅ via writeback | ✅ refresh | ✅ refresh | ✅ | ❌ |
| 创建手册条目 | ❌ | ❌ | ❌ | ✅ | ❌ |
| 确认战略研判 | ❌ | ❌ | ❌ | ✅ | ❌ |
| 手动 backfill | ✅ | ✅ | ✅ | ❌ | ❌ |

## 关键缺口

### 缺口 1：understanding_builder 完全未接入（最大问题）
- 这个模块已经能生成"这是什么/为什么重要/推进到哪/还缺什么"的 4 层理解
- 但 **main.py 没有一行代码调用它**
- 意味着��统写了大量记忆，但从不在任务详情、客户工作台、战略陪伴中展示"我理解了什么"
- 用户看不到系统的理解 → 无法校准 → 理解不会变好

### 缺口 2：任务创建/更新不触发 memory_facts 写入
- 创建和更新任务只触发 growth_signal（给成长系统用的）
- 不触发 memory_facts 和 notebook/event_line_memory 的刷新
- 意味着日常最高频的操作（每天改任务状态）不推动记忆积累
- 只有周复盘和会议发布才会真正刷新记忆

### 缺口 3：战略陪伴页使用 mock 数据
- StrategicBrainView 里的所有数据（脉搏、思考、客户认知）全是硬编码
- 后端有 build_strategic_cockpit_snapshot() 能生成真实数据
- 但前端没有调用任何 API

### 缺口 4：记忆被写入但几乎不被读回
- memory_facts 有 273 条
- organization_notebook 有 7 份
- event_line_memory 有 8 份
- 但只有 gather_project_context_for_ai() 在读（且只在周概述生成时）
- 任务详情页、客户工作台、战略页都不读记忆

### 缺口 5：没有自动定期记忆更新
- 所有记忆写入都是事件驱动（API 调用触发）
- 没有后台定时任务来定期刷新 notebook 或 event_line_memory
- 如果用户不做特定操作，记忆就不更新

### 缺口 6：local_memory 和 DB memory 是两套
- local_memory.py 写 markdown 文件到磁盘
- memory_foundation.py 写 memory_facts 到数据库
- 两者独立运行，没有交叉引用
- dream_cycle 只整理 markdown 文件，不触及 DB

## 前端模块现状

| 模块 | 数据来源 | 连接记忆系统？ |
|------|---------|-------------|
| 任务与日程 | ✅ 真实 API | ❌ 不展示理解，不展示记忆 |
| 客户工作台 | ✅ 真实 API | ⚠️ 有 notebook 数据但未展示为"理解" |
| 战略陪伴 | ❌ Mock 数据 | ❌ 完全断开 |
| 成长中心 | ✅ 真实 API | ✅ 展示 growth signals/XP |
| 选题雷达 | ✅ 真实 API | ❌ 不写入记忆 |
| 设置 | ✅ 真实 API | ✅ 日志系统已接入 |
