# B AI · K-3 sync 指令: Karpathy 7 维度独立 review

> **顾源源 5/22 22:30** 钦定 — 模式 C 互检(`docs/V2.2_KARPATHY_EVALUATION_20260522.md` §5)
> **触发**: A AI 写了 Karpathy 评估 (c427d18), 你需要独立 review,不 copy A 数字
> **优先级**: 跟 M-A broadcast 接通并行,我估 1-2 小时
> **产物**: `docs/B_AI_KARPATHY_REVIEW_20260522.md`

---

## 一、必读 (15 分钟)

按顺序读:

```bash
cd ~/openclaw/workspace/V2.1

# 1. Karpathy skill 本体 (B 自己整理的, 应该熟)
cat ~/.claude/skills/karpathy-software-3-0/skill.md

# 2. A AI 的 Karpathy 评估 (c427d18, 你要 review 这个)
cat docs/V2.2_KARPATHY_EVALUATION_20260522.md

# 3. 前置 4 维度数据 (A 跑过的 v2, 你独立 verify 一下数字)
cat docs/V2.2_ASSESSMENT_4D_20260522_v2.md
```

---

## 二、你的任务 — 用 Karpathy 7 维度跑独立评估

### 不准 copy A 数字 (模式 B "平行独立采样" 原则)

V2.1_AI_COLLABORATION.md §7.3 钦定:**A/B 各自跑 sqlite3 / git log / find 拿原始数据**,**不引用对方报告作"二手事实"**。

具体: A 报告里说 `atomic_facts 100% update_relation='none'`, **你必须自己跑 sqlite3 验证一遍**,不能直接引用。

```bash
~/openclaw/workspace/yiyu-thinktank-workbench/backend/.venv/bin/python3 -c "
import sqlite3
from pathlib import Path
conn = sqlite3.connect(str(Path.home() / 'Library/Application Support/YiyuThinkTankWorkbench2/app.db'))
print(conn.execute('SELECT COALESCE(update_relation,\"(null)\"), COUNT(*) FROM atomic_facts GROUP BY update_relation').fetchall())
"
```

### 7 维度逐项 review A 报告

对 A 报告里 7 维度的每个判断:

| Karpathy 维度 | A 判断 | 你的任务 |
|---|---|---|
| §1 三层架构 | ✅ 通过 | ★ 找反例 — V2.2 是否有 1.0/3.0 错层用? |
| §2 LLM as OS | 🟡 syslog 缺失 | ★ 独立 verify reasoning_traces / ai_episode_log 现在是不是真 0 行? |
| §3 Eval-Driven | 🟡 1 dataset + B baseline 错对象 | ★ 这是 B 你自己的教训, 用你视角再讲一遍, 看 A 总结是否准确 |
| §4 三角色 | 🟡 Evaluator 自动化缺 | ★ B 视角看 Evaluator 是不是真的弱? |
| §5 多 AI 协作 | ✅ A/B/C 都用 | ★ A 写"v2 计划缺 B review" — 你同意吗? |
| §6 拆轮子 | 🔴 3 个过度约束 | ★ A 提了 V2.1 双 app / 4 路径 / 文档过载 3 个候选, 你独立判断每个该不该拆 |
| §7 反检查 4 道 + 新 Q5 | ✅ 全过 + 新 Q5 eval 对象 | ★ 你能想到 Q6/Q7 吗? Karpathy skill §7 是否有未覆盖维度? |

### 输出对照表

```markdown
| 维度 | A 判断 | B 独立判断 | 印证 / 异议 |
|---|---|---|---|
| §1 三层架构 | ✅ | ? | ? |
| ... |
```

**双方都点 = 真信号**(顾源源决策依据)
**异点 = 视角差或盲点**(需要解释清楚)

---

## 三、K-3 的核心问题 (必答)

请按下列 4 个问题逐一回答(短回答, 每个 ≤ 100 字):

### Q1 · A AI 提的 K-1 (eval 对象重对齐) 对吗?

A 说: "B baseline 测 atomic_facts 单源 87% 跟 dogfood 1/7 严重背离, eval 对象错了, 应改成测 6 段叙事最终输出"

你的答案: ?(印证 / 反驳 / 修正)

### Q2 · A AI 提的 K-2 (Evaluator 自动化) 优先级该多高?

A 说: "V2.2 完成后做, 不阻塞主路径"

你的答案: ?(同意 V2.2 后 / 应该现在做 / 不重要)

### Q3 · A AI 提的 3 个过度约束哪个该拆?

A 提 3 个: V2.1 双 app 同跑 / 4 路径全接通 / 文档过载

你的答案: ?(具体哪个该拆 + 为什么 + Karpathy §6 视角)

### Q4 · 你的 Karpathy 视角有没有 A 漏掉的维度?

比如:
- §1 三层架构有没有错层错用?
- §2 OS 类比有没有遗漏 (eg. interrupt / scheduler 类比?)
- §4 Planner 是不是过强 / Generator 是不是过弱?

你的答案: ?

---

## 四、A/B 角色分工(本轮)

```
T+0     A: 改 V2.1 ingest_pipeline.py 加 broadcast (M-A, 已在做)
        B: 读 3 份文档 + 7 维度独立 review (K-3)

T+30min A: M-A 完成 commit (V2.1 lab + 主仓库 cherry-pick 路线待顾源源拍板)
        B: K-3 报告草稿写完

T+1h    A + B 双方报告齐 → 顾源源 review 双方一致点 + 异议点
        → 决定是否吸收 B 视角改 v2 计划
```

---

## 五、commit 规范

```
[B] docs(v2.2 ★ K-3): Karpathy 7 维度独立 review (A/B 互检 vs 单方)
```

文件: `docs/B_AI_KARPATHY_REVIEW_20260522.md`

---

## 六、不要做的事

| ❌ 不要 | ✅ 应该 |
|---|---|
| copy A 数字直接用 | 自己跑 sqlite3 / find / git log 验证一遍 |
| 全盘同意 A 判断 | 找异议点, 异议是 K-3 的价值 |
| 改 ingest_pipeline.py | A 在改, 你别同时动 |
| 加新 Karpathy 维度凭空想 | 引用 skill 内文 + V2.1_AI_COLLABORATION.md 实战 |

---

## 七、立刻开干

```bash
cd ~/openclaw/workspace/V2.1
cat ~/.claude/skills/karpathy-software-3-0/skill.md   # 复习方法论
cat docs/V2.2_KARPATHY_EVALUATION_20260522.md         # 读 A 评估
~/openclaw/workspace/yiyu-thinktank-workbench/backend/.venv/bin/python3 \
   -c "..."                                            # 自己跑数字验证

# 然后写 docs/B_AI_KARPATHY_REVIEW_20260522.md
# commit [B] docs(v2.2 ★ K-3): Karpathy 7 维度独立 review
```

---

**A AI · 5/22 22:30 · K-3 接力指令完毕**
**等 B AI 1-2 小时后产物**
