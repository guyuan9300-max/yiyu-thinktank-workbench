# AI 协调协议 · 多 AI 协作 (A / B / C / D / E / ...)

**目的**: 多 AI 在同一个 V2.1 worktree (或相关仓库) 并行干活, 避免互相等 + 文件冲突 + 重复劳动.
**触发**: 顾源源 prompt 自带心跳, 不需要自主轮询.
**生效**: 2026-05-23 (顾源源拍板), 2026-05-25 扩为 N-AI 通用.

---

## 当前 AI 分工概览

| AI | 主战场 | 主仓库 |
|---|---|---|
| A | V2.1 lab 后端 (FastAPI :47831) + Electron 前端 (TS/React) | /Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench |
| B | V3 智能体能力 / MCP / AICommandModal AI 链路 | 同上 |
| C | 手机版 (Expo RN) + cloud_backend (FastAPI :47830, 火山云线上) | ~/openclaw/workspace/yiyu-thinktank-workbench/mobile/ + V2.1/cloud_backend/ |
| D | 官网 / 开源工作台介绍页 (web UI/质感) | ~/openclaw/workspace/yiyu-think-tank-website |
| E | (待顾源源指派) | /Users/guyuanyuan/openclaw/workspace/V2.1 |

新加 AI 时, 在这张表加一行. 不写"做什么具体任务" — 任务跟随顾源源 prompt 流动.

---

## 3 条规则

1. **每次 commit 完, 必须在相关方 inbox 写一行**(告知 done + 下一步预期)
2. **每次顾源源 prompt 我开工前, 必须先读 inbox-&lt;自己&gt;**(看有没有 sync / 阻塞)
3. **改 main.py / App.tsx 等巨型文件前, 先在 baton.md 写 `&lt;AI&gt;_HOLDING &lt;file&gt;`**(避免双 AI 同时改)

---

## 文件清单

| 文件 | 谁写 | 谁读 | 说明 |
|---|---|---|---|
| `inbox-A.md` | 任何 AI / 顾源源 | A | 写在头部, 最新在最上面 |
| `inbox-B.md` | 任何 AI / 顾源源 | B | 同上 |
| `inbox-C.md`* | 任何 AI / 顾源源 | C | 同上 (按需创建) |
| `inbox-D.md` | 任何 AI / 顾源源 | D | 同上 |
| `inbox-E.md` | 任何 AI / 顾源源 | E | 同上 |
| `baton.md` | 谁占用谁写, 占完删 | 所有人 | 大文件占位锁, 空 = 全 IDLE |
| `log.md` | 所有人追加 | 所有人 | commit / decision / sync 时间线, 只 append 不改历史 |

* C 目前一直把留言写在 inbox-A (历史原因), 真要 C 有自己 inbox 再单独建.

---

## 留言格式 (统一模板)

```markdown
## [&lt;我&gt;→&lt;对方&gt;] 2026-MM-DD HH:MM
**刚做完**: commit XXX + 一句话描述
**自验**: PASS/FAIL/部分 + 关键证据
**我接下来**: 下个动作 / 停下来等
**你可以做**: 对方下一步建议
**没动 / 安全区**: 文件/目录, 对方可放心改
**冲突避免**: 如果有正在动的大文件, 写这里
```

---

## baton.md 格式

单行, 占用前 append, 占完 (commit 后) 删除:

```
A_HOLDING backend/app/main.py  (since 14:30, 修 P0-A token hash)
B_OVERLAY src/renderer/components/ai_command/AICommandModal.tsx (bot_resolved stage only, 不碰别处)
C_HOLDING cloud_backend/app/main.py  (since 15:00)
```

OVERLAY = 同文件内某一区域独占, 跟另一 AI 区域不撞 (要在备注说明区域).

空文件 = 全 IDLE.

---

## 反模式 (不要这样)

```
不要在自己工作 commit 里夹杂 inbox 留言 (留言走专属文件)
不要写一千字 (留言 5-8 行内, 详情链报告)
不要带评分 / 自夸 / FINAL (留言只说"做完什么 / 接下来 / 给你"几点)
不要不读 inbox 直接干 (顾源源 prompt 前先读自己 inbox)
不要修对方留言 (只 append, 不改历史)
不要 emoji
不要假设别的 AI 在做什么 — 不确定就 inbox 问
```

---

## 新加入 AI 第一次开工 checklist

1. cat docs/AI_COORDINATION/README.md (本文件)
2. cat docs/AI_COORDINATION/inbox-&lt;自己&gt;.md (看顾源源 / 别人给自己的留言)
3. cat docs/AI_COORDINATION/baton.md (看别人正在占哪些大文件)
4. tail -50 docs/AI_COORDINATION/log.md (看最近 24-48h 时间线发生了什么)
5. git log --since="48 hours ago" --pretty=format:'%h %ar | %an | %s' (看代码侧最近 commit)
6. 在 README 上面那张"AI 分工概览" 加一行自己 (主战场 + 主仓库)
7. log.md append 一行 "[X] HH:MM 上线 + 任务领取"
8. 开工前 baton 占自己要改的大文件
