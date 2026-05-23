# B AI 评估标准 v1 · 自动验收官冻结版

> **触发**: 顾源源 5/23 钦定 B 转角色为"自动验收官" — 建立可重复、可量化、可比较、以用户可感知为核心的评估系统.
> **冻结**: 2026-05-23 19:10
> **作用**: 三类评估统一标尺, R2 / R4-P0 / V3.0 共享.

---

## 一句话

> **不评估代码写了多少, 评估用户做真实动作后看到了什么.**

---

## 1 · 通用 3 层证据 (任何评估都要分清)

| 层 | 含义 | B 自动可测 | 是否 = 用户可感知 |
|---|---|---|---|
| **L1 API contract** | endpoint 返回什么字段 | ✅ (curl) | ❌ 不等于 |
| **L2 DB evidence** | V2.1 lab db 是否真写入 | ✅ (sqlite3) | ❌ 不等于 |
| **L3 UI / user-visible** | 用户在桌面 app 真看见 + 能处理 | ⚠️ 部分 (DOM probe) | ✅ 才算 |

**L3 不能由 L1 替代**. L3 必须标注:
- ✅ 已截图确认 (人工)
- ⚠️ 需人工确认
- ❌ 未可见

报告里 3 层证据分行列, 不混合.

---

## 2 · 三类评估统一评分

### 2.1 R2 评估 (会议纪要单链路, R2 完成)

```
脚本: scripts/run_v25_r2_meeting_minute.py
通过线: R2 真过 = 6/6 硬门槛全过 (顾源源 5/23 11:00 钦定)
评分: 100 分 7 维度 (D1-D7)
当前状态: 64/100 + 6/6 硬门槛 (V2.1 lab db 真过)
```

R2 不再追 ≥ 70 通过线 (顾源源 R4-P0 接受 6/6 硬门槛即可).

### 2.2 R4-P0 评估 (公司大脑用户可见化)

```
脚本: scripts/run_v30_ai_driven_software_eval.py (V3.0 吸收 R4-P0)
A 自评脚本: docs/A_R4_DB_FUNCTION_DEEP_LINK_RETEST_REPORT.md (A 自检 90/100)
通过线: ≥ 80 (顾源源不为过线改标准)
评分: 100 分 6 维度 (D1-D6)
B 独立 verify: 进展雷达 status="A 自评待 B 复验"
```

### 2.3 V3.0 AI 驱动软件做事评估

```
脚本: scripts/run_v30_ai_driven_software_eval.py
通过线: ≥ 80
评分: 100 分 7 维度 (D1-D7)
当前状态: baseline 56.5/100 (V2.1 lab db 真测)
分层: L1 单链路 / L2 多模块 / L3 主动缺口 / L4 Goal-Plan-Run
```

---

## 3 · L1-L4 能力分层定义 (V3.0 北极星)

| 层 | 能力 | 当前状态 | 缺什么 |
|---|---|---|---|
| **L1 单链路 AI 处理** | 一段输入 → 一个内置链路 (会议纪要 → facts/risks) | ✅ **真过** | - |
| **L2 多模块串联** | 一次输入触发 ≥ 4 模块 (会议纪要 → 合同 + 任务 + 品牌 + 理事会) | ❌ **几乎没** | contracts/draft, templates/generate, brand-proposition |
| **L3 主动缺口发现** | AI 看出"缺预算/缺历史", 自己生成澄清+调外部 | ❌ **完全没** | GET /data-gaps endpoint 404 |
| **L4 自主拆解目标** | 用户说"处理一下", AI 自己规划 N 步并执行 | ❌ **完全没** | /agent/plan + /agent/run 404 |

→ V3.0 ≥ 80 真过 = L1 ✅ + L2 ≥ 70% + L3 ≥ 50% + L4 ≥ 30%.

---

## 4 · 14 功能 A/B/C/D/E 评级 (A SELF_CHECK 沿用)

| 等级 | 定义 |
|---|---|
| **A** | 调 R3 新服务 + 真写 V2.1 lab db + 前端 evidence 可见 + 用户能处理 |
| **B** | 调 R3 新服务 + 真写 V2.1 lab db (前端不可见或不完整) |
| **C** | 调旧 service / 不调 R3 新服务 (有功能但缺新能力) |
| **D** | 部分调用, 但有断点 (写 1 表不写另 1 表 / 调用 1 模块不串别的) |
| **E** | 完全没做 / endpoint 404 |

R4-P0 通过线: 14 功能 A 级 ≥ 5 (顾源源 5/23 钦定).

---

## 5 · 硬门槛 (任意失败不算通过)

### 5.1 R2 6 硬门槛 (顾源源 5/23 11:00)

```
1 HTTP only (不直调 service)
2 V2.1 lab db 11 张表真存在
3 数据真有记录 (facts/event_line/risks/commits/clarif/run/approval)
4 不靠 dogfood_real snapshot
5 重复跑不重复写
6 跨客户隔离 0 leak
```

### 5.2 R4-P0 10 硬门槛 (顾源源 5/23 11:00 + 钦定 11)

```
H1-H5: R2 沿用 (endpoint / clarif / approval / run_log / idem_key)
H6 workspace/chat response 含 companyBrainSummary
H7 evidence_types ≥ 3 (10 真问题 ≥ 9/10)
H8 smart_import response 含 file_identity + contract_structure
H9 strategic narrative 引用 contract/historical/data_gap (≥ 2 类)
H10 single_file_only ≤ 10%
```

### 5.3 V3.0 10 硬门槛 (顾源源 5/23 18:20)

```
H1 不直接写 db
H2 对外材料不自动发送
H3 正式任务进 Approval Queue
H4 合同草稿标"待确认"
H5 缺预算/责任人不编造
H6 外部情报不覆盖内部权威
H7 必须有 Agent Run Log
H8 必须有用户可见成果包 (≥ 3 件)
H9 至少调用 4 个功能模块
H10 至少生成 3 类用户可处理结果
```

---

## 6 · "通过" vs "只算实验能力" 划线

| 状态 | 含义 |
|---|---|
| ✅ **通过** | L1/L2/L3 三层证据齐 + 硬门槛全过 + L3 用户可感知 |
| ⚠️ **只算实验能力** | L1/L2 过, L3 未截图或未挂前端 |
| ❌ **未通过** | L1 或硬门槛 fail |
| **A 自评待 B 复验** | A 自己跑分声称, B 还没用 Golden Test Pack 独立 verify |

→ A SELF_CHECK 41 / A R4 联动 63 / A R4 复测 90 全是 **A 自评待 B 复验** 状态.
→ B 真分 R2 64 / V3.0 56.5 是 **B 独立 verify 真分**.

---

## 7 · 必须判失败的情况

1. **跑 dogfood_real snapshot 自称通过** (A 5/23 上午吃过亏)
2. **A 自评 + 没 B 独立复验, 当作 V2.1 RC 真合格证明**
3. **API 字段返回 + 没真写 V2.1 lab db** → 只算 L1, 不能进 L2/L3
4. **L1+L2 过 + L3 没人工截图确认** → 只算"实验能力", 不能进"通过"
5. **改 prompt 让分数涨 + 没改底层能力** (顾源源原则五: 不为过线改标准)
6. **不带 commit id / 不带 db 路径 / 不带客户 client_id 的报告** (不可重复 = 不算)

---

## 8 · "可重复" 6 件必带

每份 B 评估报告必须列:

```
1 commit id (评估时主分支)
2 backend 端口 (默认 47831)
3 V2.1 lab db 路径 (默认 ~/Library/Application Support/YiyuThinkTankWorkbench2_V21Lab/app.db)
4 测试客户 client_id (日慈/CFFC/明远 fallback)
5 输入原文 (Golden Test Pack hash + 全文附录)
6 输出: API response 原文 + DB 前后增量 + 评分明细
```

缺一不算可重复.

---

## 9 · blocked_by_A / blocked_by_B 必标

每个不通过项必须标注:

```
blocked_by_A: endpoint XXX 未暴露 / service YYY 未实现 / 派生器 ZZZ 未接入
blocked_by_B: 评估脚本 XXX 未写 / Golden Test Pack 缺 YYY 类样本
blocked_by_user: 需顾源源人工截图 verify L3 / 拍板优先级
```

→ B 输出的每个问题都必须可执行, 不写"系统还不够智能".

---

## 10 · 不为过线改标准 (顾源源 5/23 原则五)

R4-P0 ≥ 80 不动.
V3.0 ≥ 80 不动.
R2 6/6 硬门槛全过不动.

低于线 = 继续修, 不降标.

如果 A 自评 R4 复测 90/100 后 B 独立 verify 只到 70/100, 不为过线改 verify 脚本, 而是:
- 找差异 (A 自评跟 B verify 差在哪里, 比如 A 用 dogfood 还是 V2.1 lab db?)
- 落档差异
- 让顾源源拍板 "认 A 自评 90 还是 B verify 70 当真分"

---

**Author**: AI B · 2026-05-23 19:10
**冻结**: V1 (后续修改要 commit 改名 V2, 不覆盖)
**关联**:
- 顾源源 5/23 19:00 B 下一阶段任务书
- A 5fefcf3 R4 联动 63/100 / 285e185 R4 复测 90/100 (A 自评)
- B 748c833 V3.0 56.5/100 (B 独立)
