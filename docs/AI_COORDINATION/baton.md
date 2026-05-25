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
