# 数据同步边界定义

## 原则

- 结构化数据同步到云端（任务、日程、复盘、组织配置、事件线）
- 本地文件不同步（导入的 Word/PDF 原始文件、问答向量）
- 原因不是保密，而是避免"污染"——每个人的文件库不同，同步会干扰

## 同步表（走云端）

| 表 | 说明 | 同步方向 |
|---|------|---------|
| operators | 员工账号 | 云→本地 |
| clients | 客户/项目基本信息 | 双向 |
| tasks | 任务 | 双向 |
| task_lists | 任务清单 | 双向 |
| task_tags | 标签 | 双向 |
| task_settings | 任务设置 | 双向 |
| event_lines | 事件线 | 双向 |
| event_line_activities | 事件线活动 | 双向 |
| event_line_memory_snapshots | 事件线记忆 | 双向 |
| event_line_weekly_snapshots | 事件线周历史 | 双向 |
| weekly_reviews | 周复盘 | 双向 |
| weekly_review_task_entries | 复盘条目 | 双向 |
| meetings | 会议 | 双向 |
| meeting_sources | 会议来源 | 双向 |
| agenda_items / decisions / action_items / risks / ambiguities | 会议结构结果 | 双向 |
| goal_records | 目标 | 双向 |
| organization_dna_documents | 组织 DNA | 双向 |
| client_dna_documents | 客户 DNA | 双向 |
| client_strategic_profiles | 客户战略画像 | 双向 |
| cooperation_relationships | 合作关系 | 双向 |
| project_modules | 项目模块 | 双向 |
| project_flows | 项目流程 | 双向 |
| strategic_cockpit_snapshots | 战略驾驶舱 | 双向 |
| growth_signal_events | 成长信号 | 云→本地 |
| growth_evidence_records | 成长证据 | 云→本地 |
| activity_logs | 活动日志 | 本地→云 |
| task_notes_cloud | 任务笔记（云版） | 双向 |
| task_attachments_cloud | 任务附件元数据（云版） | 双向 |

## 纯本地表（不同步）

| 表 | 说明 | 原因 |
|---|------|------|
| documents | 导入的原始文档 | 个人文件库，同步会污染 |
| knowledge_documents | 知识文档 | 同上 |
| knowledge_document_versions | 知识文档版本 | 同上 |
| document_cards | 文档卡 | 本地知识加工产物 |
| document_chunks | 文档分块 | 本地向量化产物 |
| v2_documents / v2_sections / v2_chunks | V2 知识体系 | 本地知识加工产物 |
| knowledge_surrogates | 知识代理 | 本地向量化产物 |
| knowledge_master_index | 知识主索引 | 本地检索产物 |
| knowledge_master_index_fts | 全文检索索引 | 本地 |
| chat_threads / chat_messages | 问答线程 | 个人问答历史 |
| imports | 导入记录 | 本地操作记录 |
| source_tree_snapshots | 源文件快照 | 本地 |
| client_folders | 客户文件夹 | 本地文件组织 |
| answer_runs / answer_citations | 问答运行 | 本地 |
| analysis_runs / analysis_templates | 分析运行 | 本地 |
| settings | 本地设置 | 本地偏好 |

## 层级可见性规则

| 角色 | 能看到的任务 | 能看到的总结 |
|------|------------|------------|
| 普通员工 | 只有自己的 | 只有自己的 |
| 部门负责人 | 本部门所有人的 | 本部门总结（看不到其他部门） |
| CEO | 每个部门负责人的（不看具体员工） | 所有部门总结 + 机构总结 |
