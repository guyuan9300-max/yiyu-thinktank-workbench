# AI 协调协议 · A ↔ B

**目的**: A 和 B 在同一个 V2.1 worktree, 避免互相等 + 文件冲突.
**触发**: 顾源源 prompt 自带心跳, 不需要自主轮询.
**生效**: 2026-05-23, 顾源源拍板.

---

## 3 条规则

1. **每次 commit 完, 必须在对方 inbox 写一行**(告知 done + 下一步预期)
2. **每次顾源源 prompt 我开工前, 必须先读自己的 inbox**(看有没有 sync / 阻塞)
3. **改 main.py / App.tsx 等巨型文件前, 先在 baton.md 写 `<AI>_HOLDING <file>`**(避免双 AI 同时改)

---

## 4 个文件

| 文件 | 谁写 | 谁读 |
|---|---|---|
| `inbox-A.md` | B | A |
| `inbox-B.md` | A | B |
| `baton.md` | 谁占用谁写,占完删 | 双方 |
| `log.md` | 双方追加 (commit / decision / sync) | 双方 |

---

## 留言格式 (统一模板)

```markdown
## [<我>→<对方>] 2026-MM-DD HH:MM
**刚做完**: commit XXX + 一句话描述
**自验**: ✅/⚠️/❌ 关键证据
**我接下来**: <下个动作 / 停下来等>
**你可以做**: <对方下一步建议>
**没动 / 安全区**: <文件/目录, 对方可放心改>
**冲突避免**: <如果有正在动的大文件, 写这里>
```

---

## baton.md 格式

单行,占用前 append,占完(commit 后)删除:

```
A_HOLDING backend/app/main.py  (since 14:30)
B_HOLDING scripts/run_v25_r2_meeting_minute.py  (since 14:35)
```

空文件 = IDLE,双方都没占大文件。

---

## 反模式(不要这样)

```
❌ 在自己工作 commit 里夹杂 inbox 留言 (留言走专属文件)
❌ 留言写一千字 (留言 5-8 行内)
❌ 留言带评分/自夸 (留言只说"做完什么/接下来/给你"几点)
❌ 不读 inbox 直接干 (顾源源 prompt 前先读 inbox)
❌ 修对方留言 (只 append, 不改对方的)
```
