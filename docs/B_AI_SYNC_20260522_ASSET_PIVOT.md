# B AI · 5/22 资产盘点纠偏指令

> **来自顾源源 5/22 18:xx**(请 A AI 把这段贴给 B AI)
> **优先级**: 立刻停手,先读资产,再决定下一步

---

## 一、停手原因(顾源源原话)

> "我认为现在总是设计出现偏差的原因是,可能因为压缩上下文的关系,在走一段之后,你就会对全局的掌握会衰减。所以在这一轮实施新的计划之前,我还是希望你把整个仓库所有的表格全部梳理一下,看你有哪些资产去做这个新的目标。"

A AI 已经完整盘点 208 张表,**发现了重大设计偏差**:

1. **`memory_facts` 3038 行 vs `atomic_facts` 1998 行** — 两个 fact 表并存,重复造轮子
2. **`activity_logs` 26677 行** — 真正的主时间线,event_line_activities (104) 只是它的视图
3. **NarrativeKernel 8 段几乎都有现成表**(`open_questions` 23 / `risk_signals` 20 / `weekly_reviews` 9 / `client_dna_documents` 32 / `commitments` 66 / `meetings` 7 / `decisions` 3 / `tasks` 238 / `event_lines` 16 / 等等)
4. **NarrativeKernel 不应该 "从 atomic_facts 抽 8 段"**,而应该 "聚合 8 组现成表 + atomic_facts 作引用"

详情见: `docs/V2.2_DATA_ASSET_INVENTORY.md` (新文件, 36k 字)

---

## 二、你立刻要做的 3 件事

### 第 1 步(必做): 完整读 `docs/V2.2_DATA_ASSET_INVENTORY.md`

```bash
cd ~/openclaw/workspace/V2.1
cat docs/V2.2_DATA_ASSET_INVENTORY.md
```

**特别关注**:
- §1 总览统计(11 组业务模块)
- §3 重大发现 5 条
- §4 故事 8 段 → 现成表映射 ★ 重要
- §5 atomic_facts 应该 / 不应该做什么
- §6 重新校正的 5 条设计原则

### 第 2 步: 重读更新后的 `docs/V2.1_AI_COLLABORATION.md` §6.1 + §6.2

新增"强制重读资产清单"的触发场景 + 提案前 4 道自检题。

### 第 3 步: 自查你正在做的 iterate 1(前端 3/3 接入)

你之前接的 endpoint `/v22/narrative/full_narrative` 是基于"NarrativeKernel 从 atomic_facts 一张表分组成 8 段"的旧设计。

**自检 4 问**(不通过就停手):

```
Q1: 我的 endpoint 拉的数据源是只读 atomic_facts? 还是已经聚合 §4 映射的现成表?
    只读 atomic_facts → 偏差,需要补现成表

Q2: 前端 view (StrategicBrainView / TaskDetail / StrategicClarification) 渲染的 8 段,
    用户能看到哪些已有结构化记录的内容(open_questions 表 23 条 / risk_signals 表 20 条等)?
    看不到 → view 还是空的, 即使后端数据齐

Q3: timeline 段是否在拉 activity_logs (26677 行) ?
    没拉 → 主时间线骨架缺失, timeline 段空

Q4: 我做的事是不是跟"现成表 / 现成管道"重叠?
    重叠 → 砍掉, 不要重复造轮子
```

---

## 三、A AI 跟你的分工(纠偏后)

### A AI 接下来 (我):
- ✅ 完成资产盘点 (已写 `docs/V2.2_DATA_ASSET_INVENTORY.md`)
- ✅ 更新协作文档 (已加 Step 0 + 6.1 + 6.2)
- ⏭️ 等你完成第 1-3 步后,跟你 + 顾源源对齐:
  - NarrativeKernel 重设计方案 (8 段 ← 8 组现成表 聚合视图)
  - atomic_facts vs memory_facts 归并方案 (待顾源源决策)
  - IngestPipeline task_review 路径绑现有数据源 (event_line_activities + tasks + weekly_reviews)

### B AI 接下来 (你):
- 第 1 步: 读资产清单
- 第 2 步: 读协作文档更新
- 第 3 步: 自检 iterate 1
- 第 4 步: 把你的自检结果 commit 一个 `[B] resp: asset_pivot_self_audit` 文件(`docs/B_AI_ASSET_PIVOT_SELF_AUDIT.md`)
  - 列出你之前做错的部分 (哪几个 endpoint / view / 测试)
  - 列出基于资产清单重新设计后应该怎么做
  - 等 A AI + 顾源源 review 后再动手改

**不要先动手改代码,先做自检报告**。

---

## 四、新增强制流程(每次都要做)

下列任何一种发生 → 必须重读 `V2.2_DATA_ASSET_INVENTORY.md` 再回应:

- 用户说"重新评估"/"新计划"/"做错方向了"
- 用户问"你这件事跟现有 XX 表/功能的关系"
- 跨表设计 / 新表创建
- 收到上下文压缩通知
- session 超过 4 小时
- 评估"完成度 / 偏差度"

读完后过协作文档 §6.2 4 道自检题,再递提案。

---

## 五、commit 前缀依然 [B] 不变

```
git log --since="6 hours ago" --pretty=format:"%h | %ar | %s"
```

A AI 最近 commit (5/22): `[A] docs: V2.2 data asset inventory + collab protocol asset pivot`

---

## 六、如果你在跑 baseline / 测试任务

立刻停手,**先做自检**。

baseline P% 87% 这个数字基于"NarrativeKernel 从 atomic_facts 一张表"的旧设计,
新设计下 baseline 必须改成:
- 测 8 组现成表能直接答多少 / 7 道金标准
- 不是 测 atomic_facts 抽出来多少条 / 5/19 关键事实

---

## 七、收尾

你做完自检报告后,在仓库根目录 commit 它,A AI 会自动看到。

顾源源会收到 A AI 的纠偏报告 + 你的自检报告,然后决策下一步。

**优先级**: 这次纠偏比任何 baseline / endpoint / view 实现都重要。

---

**A AI · 2026-05-22**
