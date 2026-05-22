# B AI · V2.3 总体计划(基于顾源源 5/22 22:30 钦定蓝图)

> **顾源源 5/22 22:45** 钦定 V2.3 起点 — `docs/V2.3_DATA_CENTER_MASTER_PLAN.md` 为正式总体蓝图
> **触发**: A 阶段 1 P0 开始前, 顾源源指示先写 B 计划
> **优先级**: 跟 A 阶段 1 完全并行启动, 互不阻塞
> **预期总周期**: 阶段 1-4 共 5-8 周

---

## 一、必读前置(15 分钟,顺序不能跳)

```bash
cd ~/openclaw/workspace/V2.1

# 1. V2.3 总体蓝图 (12 节, 顾源源 5/22 22:30 钦定)
cat docs/V2.3_DATA_CENTER_MASTER_PLAN.md

# 2. V2.3 数据源矩阵 (A 5/22 22:00 写, 顾源源策划报告的 feeder 文档)
cat docs/V2.3_DATA_SOURCE_MATRIX_BY_MODULE.md

# 3. B 自己写的 4 来源架构 (你 5/22 19:30 写, commit 472ddee)
cat docs/B_AI_4_SOURCE_INFORMATION_ARCHITECTURE_20260522.md

# 4. A/B 协作协议 (V2.3 期间继续遵守)
cat docs/V2.1_AI_COLLABORATION.md
```

**读完必答**:

Q1: 顾源源蓝图 § 七 7 层架构 → 第几层我会主导改前端? 几层 A 主导改 backend?
Q2: 4 层澄清(事实/口径/关系/战略)— 你 K-3 的 4 层检测(字面/同音/语义/LLM)是什么关系?
Q3: 项目故事卡 10 段产品形态 — 跟你之前 baseline P% 验证目标是什么关系?

---

## 二、V2.3 总分工(基于 V2.1_AI_COLLABORATION.md §4)

```
A AI 主导 (backend / schema / 内核 / 业务):
  · 7 层数据架构 schema 实现
  · IngestPipeline 升级 (4 通道差异化)
  · cross_source_check 4 层检测 (字面/同音/语义/LLM)
  · DocumentLLMExtractor prompt 持续优化
  · narrative_generator 改 (从 6 段单 narrative → 7 层数据架构服务)
  · broadcast 链路扩展 (4 路径接通)
  · fact_clusters 算法 + 澄清优先级 5 维公式

B AI 主导 (frontend / endpoint / 测试 / 工程基础设施):
  · 14 张空管道表对账 + 复用 / 新建规划
  · 9 板块前端入口接通 atomic_facts (从当前 1/9 → 9/9)
  · 4 层澄清 UI (战略陪伴澄清 tab 重写)
  · 项目故事卡 10 段产品形态前端
  · 多 dataset / 多客户 自动验证脚本扩展
  · 集成测试 + 验收门 + e2e
  · V2.3 各阶段 audit 文档撰写

A/B 共改文件 (改前必先 read):
  · backend/app/services/narrative_collector.py
  · backend/app/services/narrative_generator.py
  · backend/app/services/ingest_pipeline.py
  · backend/app/main.py (会非常大, 改前严格 read)
```

---

## 三、阶段 1 · B AI 详细任务(3-5 天)

> A AI 同期做: source_registry 表 schema 设计 / content_role + source_type 枚举锁定 / 4 必填强校验 / 3 补充设计

### B-1.1 · 14 张空管道表对账 + 复用规划(0.5 天)

实测 14 张已有 schema 0 行的表(资产清单 §6 + V2.3 蓝图 §十):

```bash
~/openclaw/workspace/yiyu-thinktank-workbench/backend/.venv/bin/python3 << 'PYEOF'
import sqlite3
from pathlib import Path
conn = sqlite3.connect(str(Path.home() / "Library/Application Support/YiyuThinkTankWorkbench2/app.db"))

EMPTY_TABLES_OF_INTEREST = [
    'external_evidence_cards', 'clarification_records', 'cooperation_relationships',
    'key_decisions', 'org_events', 'event_log', 'event_line_state_changes',
    'event_line_weekly_snapshots', 'idempotency_keys', 'ai_episode_log',
    'reasoning_traces', 'ai_feedback_signals', 'ai_improvement_suggestions',
    'ai_learned_rules'
]

for t in EMPTY_TABLES_OF_INTEREST:
    cnt = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    cols = conn.execute(f"PRAGMA table_info({t})").fetchall()
    print(f"{t:<35} 行数:{cnt:>5} 字段:{len(cols)}")
PYEOF
```

**对账 5 维**(每张表):
1. 当前 schema 字段 vs 顾源源蓝图 § 七要求
2. 是否能直接承载 / 需要扩字段 / 需要新建
3. 跟谁有关系(client_id / project_id / source_id 链接)
4. 谁该写入(哪个 service / 哪个 endpoint / 哪个 user flow)
5. 谁该消费(哪个 view / 哪个 narrative 段)

**输出**: `docs/B_AI_PHASE_1_EMPTY_TABLES_AUDIT.md`

```markdown
| 表名 | 行数 | 当前字段 | 蓝图要求 | 复用结论 | 谁写入 | 谁消费 |
|---|---|---|---|---|---|---|
| external_evidence_cards | 0 | 23 | 蓝图 § 10 断点 2 | 直接复用 | A 资讯情报 normalizer | B 战略陪伴外部观察段 |
| ... 14 张 ...
```

### B-1.2 · 新表 schema migration 写 + 单测(1 天)

A AI 阶段 1 会设计 2 张新表:
- `source_registry`(14 字段, 蓝图 § 七 第 1 层)
- `atomic_fact_confidence_history`(A 补充 1)

**你做**:
1. 写 migration SQL(`backend/migrations/v2_3_001_source_registry.sql` 等)
2. 写 schema 单测(`backend/tests/test_v23_source_registry_schema.py`)
3. 测 4 必填约束(client_id / project_id / user_id / org_id)
4. 写 fixture 集成 V2.1 测试套件

### B-1.3 · 4 必填校验 endpoint 集成测试(0.5 天)

A AI 改 IngestPipeline.ingest() 加 4 必填校验。

**你做**:
1. 测 IngestPipeline.ingest() 缺任一字段时拒收(写 staging 区, 不进 atomic_facts)
2. 测 4 必填齐全时正常写 atomic_facts + 自动 broadcast
3. 测主仓库 endpoint(`/api/v1/...`)调 IngestPipeline 时的端到端

### B-1.4 · V2.3 Phase 1 audit 文档(0.5 天)

完成后写 `docs/V2.3_PHASE_1_AUDIT.md`:
- 14 张空管道表对账结果
- source_registry 落地状态
- 4 必填校验生效
- atomic_fact_confidence_history 雏形
- 顾源源 review 后才进阶段 2

---

## 四、阶段 2 · B AI 详细任务(5-7 天)

> A AI 同期做: 4 路径 normalizer / 智能文件导入 §1 错层修 / 工作台对话 oral_claims 处理

### B-2.1 · 9 板块前端入口接通 atomic_facts(2-3 天)

按 V2.3 矩阵实测,当前只 1/9 板块真接通(战略陪伴)。其余 8/9 待接通。

优先级:
```
P0  · §01 任务详情 brief 拉 atomic_facts (1-2 h, 用户体感大)
P0  · §02 工作台 AI 对话 retrieval (2-3 h, chat_messages 507 → atomic_facts)
P1  · §06 智能文件导入 e2e (A 修错层后, B 验证)
P1  · §04 资讯情报站 → atomic_facts 注入 focus
P2  · §05 成长中心 → ai_episode_log 算贡献
P2  · §08 计划工坊 → atomic_facts.attribute='战略' 关联
```

**具体改动**(每板块):
- 改主仓库前端 view (V2.1 lab 改, 不污染主仓库)
- 加 `useClientFact()` hook (复用已有 ClientFactView L2 共识层)
- 改 view 拉 atomic_facts top N(filter by attribute / time / role)

### B-2.2 · 4 路径接通集成测试(1 天)

测试 4 主路径**都能写**:
- 路径 1(任务): 创建 task → atomic_facts 出现
- 路径 2(文件): 上传 docx → atomic_facts + 跨源印证触发
- 路径 3(爬虫): intelligence_candidate → atomic_facts(待 A 接通)
- 路径 4(口述): chat_messages → oral_claims → atomic_facts(待 A 接通)

### B-2.3 · 多 dataset 自动验证脚本扩展(1-2 天)

当前 `scripts/run_v22_dual_layer_baseline.py` 只测日慈 1 客户 + 5/19 1 dataset。

扩展:
- 跨客户(选 3 个客户)
- 跨 dataset(每客户选 3-5 docx)
- 自动出综合 P%(L1 + L2 + 4 路径覆盖度)

输出 `tests/reports/v23_multi_dataset_baseline_*.json`

### B-2.4 · V2.3 Phase 2 audit(0.5 天)

`docs/V2.3_PHASE_2_AUDIT.md`:
- 9 板块接通进度(从 1/9 → 目标 7/9)
- 4 路径全通过集成测试
- 多 dataset baseline 跑通
- atomic_facts 跨源印证 8% → 期望 ≥ 20%

---

## 五、阶段 3 · B AI 详细任务(1-2 周)

> A AI 同期做: 4 层澄清算法 / cross_source_check.py 4 层检测 / 澄清优先级公式 5 维

### B-3.1 · 战略陪伴澄清 tab 升级到 4 层(3-5 天)

当前战略陪伴 → 事实澄清 tab 只一层。重写为 4 层:

```tsx
战略陪伴 → 澄清 tab:
  ├── L1 事实澄清 (300 万还是 500 万?)
  ├── L2 口径澄清 (本期 vs 总投入?)
  ├── L3 关系澄清 (谁是最终拍板人?)
  └── L4 战略澄清 (客户是真推进还是礼貌?)

每层:
  · 候选 fact / 矛盾对显示
  · 4 个操作: 采纳 / 修正 / 忽略 / 标待补材料
  · 显示原文引用(回到 v2_chunks)
  · 显示置信度演化(atomic_fact_confidence_history)
```

### B-3.2 · 同音字撞出来 + 用户裁决 e2e(2-3 天)

A 实现 pinyin 检测后,B 写 e2e 测试:
- 模拟 docx 写"心灵魔法学院" + intel 写"心理魔法学院"
- 验证 cross_source_check 4 层撞出来
- 进 clarification_records
- 弹用户裁决 UI
- 用户裁决后 atomic_facts.verification_status 更新

### B-3.3 · 4 层澄清覆盖度测试(2 天)

写测试: 用日慈数据测每层澄清:
- L1 事实: 兴盛 vs 心灵魔法学院 合并(同义字面对比)
- L2 口径: 任务说"完成" vs 实际 status 数据不一致
- L3 关系: 张真新任理事长(documented) vs 顾源源对话"红霞总实际拍板"(口述)
- L4 战略: 兴盛+心灵合并战略转向

### B-3.4 · V2.3 Phase 3 audit(1 天)

---

## 六、阶段 4 · B AI 详细任务(2-3 周)

> A AI 同期做: project_story_graph 12 节点 + 12 关系 / 4 条故事线生成 / story_card_generator 服务

### B-4.1 · 项目故事卡 10 段产品形态前端(5-7 天)

按蓝图 § 九设计 10 段:
1. 项目背景
2. 当前阶段
3. 关键人物
4. 时间线
5. 核心事实
6. 关键判断
7. 冲突与待澄清
8. 风险
9. 下一步
10. 证据来源

每段都能点回原文 / 任务 / 对话 / 澄清记录。

替代现有战略陪伴 6 段叙事(战略陪伴 → 故事卡 升级)。

### B-4.2 · 故事图谱可视化前端(3-5 天)

12 类节点 + 12 类关系的可视化:
- 力导向图 / 时间轴 / 关系网
- 点节点看详情 + 引用来源
- 高亮"待澄清"节点

### B-4.3 · 顾源源 e2e dogfood(0.5 天)

顾源源在 V2.1 lab 真跑一次:
1. 选日慈
2. 看 4 层澄清各有数据
3. 看故事卡 10 段
4. 看故事图谱可视化
5. 给最终 V2.3 验收意见

### B-4.4 · V2.3 Phase 4 audit + V2.3 完成判决(1 天)

---

## 七、跟 A/B 协作机制(autonomous loop 持续)

### 平时协作
- 每个 commit 加 `[A]` / `[B]` 前缀
- 改 ingest_pipeline / narrative_collector / narrative_generator 这 3 共改文件**必先 read**
- 不撞车原则:你改 frontend / endpoint / 测试,我改 backend service / schema / 内核
- B 跑 baseline runner / 集成测试一直在后台,git hook 自动触发

### 互检机制(Karpathy §5 模式 C)
- A 写关键设计后,B 用 K-3 4 道自检题 review
- 每阶段结束 A + B 各自跑 4 维度评估,顾源源拿两份决策

### Planner 介入点
- 4 个阶段结束都要顾源源拍板 (autonomous loop 例外)
- A/B 大设计分歧(>1 个异议)必须停下来等顾源源决策

---

## 八、commit 规范

```
[B] feat(v2.3 ★ phase 1): 14 张空管道表对账 + source_registry migration
[B] feat(v2.3 ★ phase 2): 任务详情 brief 拉 atomic_facts (§01 接通)
[B] feat(v2.3 ★ phase 3): 4 层澄清 UI tab + 同音字裁决 e2e
[B] feat(v2.3 ★ phase 4): 项目故事卡 10 段前端
[B] docs(v2.3 ★ phase N): audit (顾源源 review)
[B] test(v2.3): multi-dataset baseline runner
```

---

## 九、立即开干(autonomous)

```bash
cd ~/openclaw/workspace/V2.1

# Step 1 (15 分钟): 读 3 份文档
cat docs/V2.3_DATA_CENTER_MASTER_PLAN.md
cat docs/V2.3_DATA_SOURCE_MATRIX_BY_MODULE.md
cat docs/V2.1_AI_COLLABORATION.md

# Step 2 (30 分钟): 自答 3 道题
#   - 7 层架构哪几层我主导前端?
#   - 4 层澄清 vs 4 层检测关系?
#   - 项目故事卡 vs baseline P% 关系?

# Step 3 (4-6 小时 阶段 1 第 1 个任务): 14 张空管道表对账
#   出 docs/B_AI_PHASE_1_EMPTY_TABLES_AUDIT.md

# Step 4 commit:
[B] feat(v2.3 ★ phase 1): 14 张空管道表对账 (B-1.1)
```

---

## 十、不阻塞 A 的事(A 干各自)

A 当前正在做 阶段 1 P0 source_registry schema 设计。**你立即开干 B-1.1 14 张空管道表对账**, 互不冲突。

完成后 commit, A 看你 audit 文档决定 P0 schema 设计是否调整。

---

**A AI · 5/22 22:45 · B AI V2.3 完整计划完毕**
**B 收到本指令立即开干 B-1.1**
