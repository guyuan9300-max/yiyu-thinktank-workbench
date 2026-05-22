# B AI · M-G sync 指令: Evaluator 自动化 + 双层 baseline runner

> **顾源源 5/22 22:50** 批准计划 v3 (吸收你 K-3 全部 5 处异议)
> **触发**: 你 K-3 异议 2 (Evaluator 立刻做, 不是 V2.2 后) + 异议 4 (双层 L1+L2 eval) 已被采纳
> **优先级**: 立刻开干, 跟 A 的 M-B (路径 2 接入) 并行, 互不阻塞
> **预期时长**: 0.5 天 (你给的工作量评估, 顾源源采信)
> **产物**: 新 baseline runner + JSON 报告格式 + auto-trigger 机制

---

## 一、必读 (10 分钟)

```bash
cd ~/openclaw/workspace/V2.1

# 1. v3 计划增量 (A AI 在跟顾源源沟通时给的, 还没 commit, 复述如下)
#    M-B 路径 2 接入 (A 在做) + M-C collector 补表 + M-G Evaluator 自动化 (你做) +
#    M-D smart_file_import 切迁 + M-E N3 流量 + 协作机制升级

# 2. A AI 当前 dogfood 脚本 (你要改它)
cat scripts/run_v22_dogfood_6dim_baseline.py | head -50

# 3. 你 K-3 报告里"双层 L1+L2"原话 (验证自己想法)
grep -A 10 "异议 3.*L1\|双层" docs/B_AI_KARPATHY_REVIEW_20260522.md | head -20
```

---

## 二、M-G 核心任务: 双层 baseline runner

### 2.1 你的核心洞察(你 K-3 自己写的)

```
L1 = atomic_facts 抽取层 eval (LLM extractor 抽的 fact 对不对)
L2 = 6 段叙事拼合层 eval (collector + generator 拼的对不对)

只测 L2 会掩盖 L1:
  · collector 漏拉 → L2 命中低
  · LLM 抽漏 → L2 也命中低
  · 单 L2 看不出哪种 bug
```

### 2.2 L1 eval 具体设计

输入: prod db (或 V2.1 lab db) + client_id + 5/19 金标准 7 关键词

```python
# L1 命中算法 (atomic_facts 层)
L1_KEYWORDS = ["法人", "理事长", "强哥", "秘书长", "兴盛", "心理魔法学院", "安心妈妈"]

l1_hits = 0
for kw in L1_KEYWORDS:
    rows = db.fetchall("""
        SELECT id, subject_text, attribute, value_text
        FROM atomic_facts
        WHERE client_id = ?
          AND (subject_text LIKE ? OR attribute LIKE ? OR value_text LIKE ?)
    """, (client_id, f"%{kw}%", f"%{kw}%", f"%{kw}%"))
    if rows:
        l1_hits += 1

l1_pct = l1_hits / 7 * 100  # 0~100%
```

**L1 P% 含义**: atomic_facts 表层有没有这 7 条事实 — 测 LLM extractor 工作

### 2.3 L2 eval 具体设计

输入: 同 client + 7 关键词 + 跑 narrative_generator 拿 6 段

```python
# L2 命中算法 (6 段叙事输出层)
from app.services.narrative_collector import collect_client_fact_bundle
from app.services.narrative_generator import generate_narrative_dimensions

bundle = collect_client_fact_bundle(db, client_id)
dims, overall, model = generate_narrative_dimensions(ai, bundle, db=db,
                                                    enable_clarification_pre_search=False)

all_narrative_text = "\n".join(
    str(d.get("narrative", "") if isinstance(d, dict) else "")
    for d in dims.values()
)

l2_hits = sum(1 for kw in L1_KEYWORDS if kw in all_narrative_text)
l2_pct = l2_hits / 7 * 100
```

**L2 P% 含义**: 用户在战略陪伴看到的 6 段叙事里有这 7 条事实没 — 测用户感

### 2.4 综合判决逻辑

```python
if l1_pct < 70:
    diagnosis = "L1 低 → LLM extractor 或 atomic_facts 入库有问题, 查 ingest_pipeline + document_llm_extractor"
elif l1_pct >= 70 and l2_pct < 50:
    diagnosis = "L1 高 L2 低 → collector 漏拉或 generator prompt 没用上, 查 narrative_collector + narrative_generator"
elif l1_pct >= 70 and l2_pct >= 70:
    diagnosis = "PASS — atomic_facts 有, 6 段也讲到"
else:
    diagnosis = "L1+L2 都低 → 系统性问题, 排查全链路"
```

---

## 三、M-G 任务清单 (按顺序)

### Task 1 (60 min) · 写双层 baseline runner

**文件**: `scripts/run_v22_dual_layer_baseline.py` (新建)

参考 `scripts/run_v22_dogfood_6dim_baseline.py` 现有模板, 改为:
- 加 L1 命中查询 (上面 2.2 SQL)
- 保留 L2 命中查询 (现有 6 段叙事关键词匹配)
- 加 diagnosis 综合判断 (2.4)
- JSON 输出格式 (见下方 2.5)
- markdown 输出格式 (人读)

**JSON 报告 schema** (`tests/reports/dual_layer_baseline_<timestamp>.json`):

```json
{
  "generated_at": "2026-05-22T...",
  "client_id": "client_284afd836e",
  "client_name": "日慈基金会",
  "dataset_version": "5/19 张真会议 7 关键词",
  "L1": {
    "pct": 14.3,
    "hits": 1,
    "total": 7,
    "by_keyword": {"法人": 0, "理事长": 2, ...},
    "level": "atomic_facts"
  },
  "L2": {
    "pct": 14.3,
    "hits": 1,
    "total": 7,
    "by_keyword": {...},
    "level": "narrative_6_dim_output",
    "model_used": "openclaw",
    "overall_confidence": 0.84
  },
  "diagnosis": "L1+L2 都低 → 系统性问题, 排查全链路",
  "duration_seconds": 162.0
}
```

### Task 2 (30 min) · auto-trigger 机制

选 1 种实现 (我推荐 a):

**a) git post-commit hook** (推荐, 简单可控)
```bash
# .git/hooks/post-commit (V2.1 仓库 + 主仓库 都装)
#!/bin/bash
# 如果 commit 改了 narrative_collector / narrative_generator / ingest_pipeline / document_llm_extractor
# 自动跑双层 baseline + 出报告
CHANGED=$(git diff HEAD~1 HEAD --name-only)
TRIGGER_FILES="narrative_collector|narrative_generator|ingest_pipeline|document_llm_extractor"
if echo "$CHANGED" | grep -qE "$TRIGGER_FILES"; then
    echo "[auto-eval] 检测到关键文件改动, 跑双层 baseline..."
    nohup ~/openclaw/workspace/yiyu-thinktank-workbench/backend/.venv/bin/python3 \
        ~/openclaw/workspace/V2.1/scripts/run_v22_dual_layer_baseline.py \
        日慈基金会 > /tmp/auto_eval.log 2>&1 &
    echo "[auto-eval] 后台跑 (日志 /tmp/auto_eval.log), 完成后看 docs/AUTO_EVAL_LATEST.md"
fi
```

**b) Python watchdog file watcher** (复杂, 跑常驻进程)
**c) npm script trigger** (用户手动 npm run eval, 不算 auto)

我推荐 a — git post-commit 是 Karpathy §3 "数字推进 = 真改进" 的自动化抓手, 每个 collector/generator 改动后立刻有数字.

### Task 3 (30 min) · markdown 报告升级

**文件**: `docs/AUTO_EVAL_LATEST.md` (每次 auto-trigger 后覆盖, 顾源源能直接看)

```markdown
# 自动 eval · {timestamp}

## L1 vs L2 命中对比

| 维度 | 命中 | P% | 含义 |
|---|---|---|---|
| L1 atomic_facts | 1/7 | 14.3% | LLM extractor 抽到的 |
| L2 6 段叙事 | 1/7 | 14.3% | 用户在战略陪伴看到的 |

## 诊断

L1+L2 都低 → 系统性问题, 排查全链路

## 7 关键词逐项

| 关键词 | L1 (atomic_facts) | L2 (6 段叙事) |
|---|---|---|
| 法人 | 0 | 0 |
| 理事长 | 2 | 2 |
| ...

## 历史对比 (last 5 runs)

| 时间 | L1 P% | L2 P% | 主要改动 |
|---|---|---|---|
| 2026-05-22 22:50 | 14.3% | 14.3% | M-A broadcast 接通 |
| 2026-05-22 22:00 | 14.3% | 14.3% | (基线, M-A 前) |
| ...
```

### Task 4 (30 min) · 跟 A 工作流集成

A 在做 M-B 路径 2 接入. M-B 完成 commit 后, post-commit hook **自动触发**双层 baseline, **5 分钟内出 L1+L2 P%**.

A 看 P% 判断:
- L1 飙升 + L2 还低 → A 继续做 M-C collector 补表
- L1+L2 都飙升 → M-B 完美打到 N2 北极星, 进 M-D
- L1 不动 → M-B 没真接通, 排查

**M-G 是 M-B/M-C/M-D 的 Evaluator 工具**, 不是终点.

---

## 四、跟 A 并行点

```
T+0       A: M-B 路径 2 接入 (改 backend/app/modules/task/* commitment/* + 加 event_line_activities adapter)
          B: M-G Task 1 (双层 baseline runner)

T+1 h     A: M-B 部分接通, atomic_facts 出现新数据 + 触发 broadcast 链路
          B: M-G Task 1 完成, 跑一次双层 baseline 出 baseline 数字

T+1.5 h   A: M-B 完成, commit (post-commit hook 自动触发双层 baseline)
          B: M-G Task 2-3 (auto-trigger + markdown 报告)

T+2 h     A + B 看 docs/AUTO_EVAL_LATEST.md
          ★ 顾源源决策点 1: M-B 是否真打到 5/19 ≥ 5/7
```

---

## 五、不要做的事

| ❌ 不要 | ✅ 应该 |
|---|---|
| 直接砍 A 现有 dogfood 脚本 | 复用模板, 新建 dual_layer_baseline.py |
| 改 ingest_pipeline.py 或 narrative_collector.py | A 在做, 你别同时动 |
| 设计单层只测 L2 | 双层 L1 + L2 (你自己 K-3 异议 4 的核心) |
| auto-trigger 用复杂 watcher | git post-commit 简单可控 |
| eval 同时测多 dataset | V2.2 阶段只测 5/19, 多 dataset 留 V2.3 |

---

## 六、commit 规范

```
[B] feat(v2.2 ★ M-G): 双层 L1+L2 baseline runner + git post-commit auto-trigger
```

文件清单:
- `scripts/run_v22_dual_layer_baseline.py` (新)
- `.git/hooks/post-commit` (新, 但 git 不 track hooks, 写一个 scripts/install-eval-hook.sh 让 A/B 装)
- `docs/AUTO_EVAL_LATEST.md` (初始版, auto-trigger 后覆盖)

---

## 七、立刻开干

```bash
cd ~/openclaw/workspace/V2.1

# Step 1 (60 min)
cp scripts/run_v22_dogfood_6dim_baseline.py scripts/run_v22_dual_layer_baseline.py
# 编辑加 L1 命中 + diagnosis + JSON schema

# Step 2 (30 min)
# 写 .git/hooks/post-commit + scripts/install-eval-hook.sh

# Step 3 (30 min)
# 跑一次 baseline 验证 L1+L2 都出数字, 写 docs/AUTO_EVAL_LATEST.md 模板

# Step 4 (30 min)
# 跟 A AI M-B commit 后联调 (A 推 commit → hook 自动跑 → 你看报告)

commit [B] feat(v2.2 ★ M-G): ...
```

---

## 八、验收门

- 跑 `python3 scripts/run_v22_dual_layer_baseline.py 日慈基金会` 出 2 个数字 (L1 + L2)
- JSON 报告写到 `tests/reports/dual_layer_baseline_*.json`
- markdown 报告写到 `docs/AUTO_EVAL_LATEST.md` (含诊断 + 历史对比)
- A 跑 git commit (改 ingest/collector/generator 时) → 后台自动触发 baseline → 5 分钟内出报告

---

**A AI · 5/22 22:50 · M-G sync 指令完毕**
**B 立即开干, 0.5 天完成, 跟 A 的 M-B 并行**
