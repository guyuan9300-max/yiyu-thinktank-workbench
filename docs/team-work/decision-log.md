# Decision Log

## 2026-04-06 记忆系统优化（三步）

### 决策：先从文档知识入手，不从任务入手

**原因：** CEO 指出 363 份客户文档是最大的宝藏，但只有 11 条进入了 memory_facts。之前一直盯着任务和复盘那点薄数据是方向错误。

### 执行结果

| 步骤 | 改动 | 效果 |
|------|------|------|
| 第一步：文档知识回流 | `backfill_document_knowledge_to_memory()` 函数 | memory_facts 从 278 → 496 条（+214 条文档洞察） |
| 第二步：Dream cycle 升级 | `run_dream_cycle()` 增加 cross-pollinate + DB sync | 周记忆的"需要关注"、"卡点"自动进入 memory_facts |
| 第三步：导入自动触发 | 文档导入完成后自动调 backfill + refresh notebook | 新文档上传后记忆自动增长 |

### 关键教训

- 不要用 AI 凑内容——先让记忆变丰富，理解自然变深
- 文档是基础，任务和复盘是增量
- Dream cycle 不是裁剪文件，是整理认知
- 借鉴 Claude Code AutoDream：定向搜索信号，不重读全文
