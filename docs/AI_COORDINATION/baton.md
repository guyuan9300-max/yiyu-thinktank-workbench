# baton · 大文件占位

动 main.py / App.tsx / 等巨型 monolith 前, 在这里 append 一行。
commit 完删自己的占位行。

空文件 = 双方都 IDLE。

---

B_OVERLAY src/renderer/components/ai_command/AICommandModal.tsx (bot_resolved stage UI only) + src/renderer/lib/aiCommand.ts (since 2026-05-25 PM)
  · 顾源源真用反馈: "我理解的任务"卡片要可验证 — 庆华信息挤右上角,
    主区 step list 三段式 (做什么/基于什么/交付什么)
  · 只改 bot_resolved stage 行 588-641 区域, 不碰 A 的 mention picker (169-220)
  · 不改 createBotTaskPlan / submit 逻辑 (B 5/24 已修, A 已保留)
  · A merge 时除 bot_resolved 区, 其它区 A 优先

B_HOLDING backend/app/services/plan_executor.py (handler bodies) + backend/app/main.py (BackgroundTasks signature) (since 2026-05-25 PM late)
  · 顾源源拍板"不等 A, 全干, 从底层架构修, 不要硬编码模拟" → B 跨界接 P0-1 + P0-2
  · documents.generate handler: 真接 AIService._qwen_generate → 真写 markdown → 真 INSERT documents 表
  · tasks.create handler: title/owner/ddl/desc 用 subtask.payload + plan_text 时间解析, 不再用 plan_text 前 30 字
  · execute_plan(plan_id, db) signature 加 ai_service 参数 + main.py 2 处 BackgroundTasks.add_task 同步改
  · A merge 时: handler body 用 B 的; ExecutorRegistry/execute_plan 主流程 A 优先 (B 只改 signature 加参数)
