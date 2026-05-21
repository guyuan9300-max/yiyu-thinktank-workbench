# Milestone Audit · F1.6 + F1.7 + 部分 N3 预留

> 时间: 2026-05-22
> 范围: F1.6a/b (ClientFactContext 全局接入) + F1.7 (multi-account stage audit) + 部分 N3 A1 (actor_type/actor_id 落地)
> 跑法: 对照 V2.2_NORTH_STAR.md 三北极星 + 整体规划位置, 不只看代码

---

## 1 · 这一组里程碑做了什么 (事实)

### F1.6a + F1.6b (commit 8ac7531)

| 产出 | 行数 | 服务北极星 |
|---|---|---|
| `src/renderer/contexts/ClientFactContext.tsx` (新) | 113 | N1 / N2 |
| `src/renderer/App.tsx` (5 行) | +5 | N1 / N2 |
| `docs/V2.2_PHASE1_SPEC_F16_REVISED.md` (新) | 119 | 文档契约 |

### F1.7 (即将 commit)

| 产出 | 行数 | 服务北极星 |
|---|---|---|
| `backend/app/db.py` schema (+25, +版本号) | +26 | N1 (修 v1.0 bug) + N3 (A1 预留) |
| `backend/app/modules/client/repository.py` (+ 5 方法) | +180 | N1 (修 v1.0 bug) + N3 (actor_type 支持) |
| `backend/app/tests/test_v22_f17_stage_audit.py` (新, 14 测试) | 240 | 校验门 A + C |
| `backend/app/main.py` (cloud sync 接入守门) | +20 | N1 (修 v1.0 bug 落到生产 path) |

### 文档契约校准 (commit 61712c6)

| 产出 | 行数 |
|---|---|
| `docs/V2.2_NORTH_STAR.md` 从 2 北极星扩为 3 北极星 + 4 主路径 + 5 维元数据 + 70% 自主边界 | +172 / -45 |
| `docs/V2.2_RFC.md` 加 F1.8/F1.9/F2.0/F2.8/F3.4b/F3.7 + 三校验门 | +49 / -12 |
| `docs/V2.2_INFORMATION_SOURCE_METADATA.md` (新, 5 维元数据规范) | 394 |

---

## 2 · 北极星对照 (不只看代码, 看它在总体里的位置)

### N1 · v2.2 做完后所有功能顺畅运行

**这一组里程碑给 N1 贡献的杠杆**:

| 维度 | 现状 | 这一组的进展 |
|---|---|---|
| 跨 view 数据一致性 | B 方案 #9 "多池并列", IntelligenceStation/EventLineReportPanel 各自 fetch 不同步 | ★ ClientFactProvider 全局接入, 后续 view 接入即同步 |
| v1.0 客户 bug #1 (frozen 被云端覆盖) | 已知存在, 多账号场景必复现 | ★ Repository 守门 + main.py cloud sync 接入 + 14 测试覆盖 = 实质修复 |
| 9 大模块功能完整 | 全在 | 未破坏 (后端全测试待跑) |

**N1 推进度**: 显著, 从 "Provider 不存在 + frozen bug 在生产" → "Provider 全局可用 + frozen 守门 + audit 可诊断"

### N2 · 手机 AI 4 主路径接通 + 软件灵魂

**这一组里程碑给 N2 贡献的杠杆**:

| 维度 | 现状 | 这一组的进展 |
|---|---|---|
| 4 路径统一通道 | Phase 2 才做 IngestPipeline, 这一组未碰 | ⚠️ 未直接推进 |
| 5 维元数据 schema | 文档化已完成, schema 落地待 F1.9 | ★ 文档契约就位, audit 表已用 actor_type/actor_id (是 5 维之一) |
| 机器人能力 | 没新 view 接入 useClientContext, B 门验收"日慈事件线"问答能力**这一组未推进** | ⚠️ B 门连续 1 个里程碑未推进 (上限 2) |

**N2 推进度**: 部分。基础设施 (Provider) 就位但实际 view 没接入, 朋友式聊天 + IngestPipeline 都在 Phase 2/3。**下个里程碑必须直接推进 B 门**, 否则触发 NORTH_STAR §8 "B 门连续不动" 警报。

### N3 · 为 3.0 埋好接入基础

**这一组里程碑给 N3 贡献的杠杆**:

| 维度 | 现状 | 这一组的进展 |
|---|---|---|
| A1 actor_type/actor_id 字段 | 全无 | ★ client_stage_audit 表已有 actor_type/actor_id, 是 N3 的首次实际落地 |
| A2 event_log 总线 | 无 | 未做 (留 F1.9) |
| A3-A6 + B | 无 | 未做 |
| AI Memory 5 表占位 | 无 | 未做 (留 F2.0) |

**N3 推进度**: A1 字段已开始落地 (audit 表) + 测试 `test_ai_agent_can_freeze_as_actor` 验证 ai_agent 可以作为 actor 改阶段。**这是 N3 的首次真实代码落地**, 之前只有文档计划。

---

## 3 · 自主决策记录 (顾源源后续可审)

| 决策 | 把握 | 理由 |
|---|---|---|
| F1.6 spec 修订 (跳过 5 view 重写, 改为 Provider + 2 view 局部) | 80% | 实地探查 ClientFactBundle 只能替代基础信息, view 专项 fetch 不可替代 |
| F1.6c/d 跳过, 直接进 F1.7 | 75% | 局部接入价值低, view 改造留 v2.3 各自做更高效 |
| F1.7 合并 A1 actor_type 字段一起做 | 90% | audit 表本来就需要 changed_by 字段, 顺手对齐 N3 命名 |
| `apply_cloud_stage_change` 设计为 (applied, message) tuple | 85% | 让 main.py 调用方能区分守门拒绝 vs 写入成功, 不藏错误 |

---

## 4 · 校验门状态

### 门 A (N1 功能不掉链)
- ✅ TS 编译 0 错误
- ⏳ 后端全测试运行中 (启动)
- ✅ F1.7 单测 14/14 PASS
- ⏳ 9 大模块手工跑 (留下个 session 做)

### 门 B (N2 数据中心入口统一 + 机器人能力)
- ✅ ClientFactProvider 已包在 App 顶层, 子组件可调
- ⏳ 实际 view 接入 0 个 (推 v2.3)
- ⏳ "日慈事件线" 机器人测试这一里程碑未做

**预警**: B 门连续 1 个里程碑未推进。下个里程碑必须直接验机器人答题能力, 否则 NORTH_STAR §8 触发"重新评估方向"。

### 门 C (N3 3.0 接入预留)
- ✅ A1 actor_type/actor_id 字段在 audit 表落地
- ✅ ai_agent 作为 actor 的测试通过
- ⏳ A2 event_log / A4 verification_status 留 F1.9
- ⏳ A3/A5/A6/B 留 Phase 2

---

## 5 · 这一组里程碑的真实价值评估

### 客户能感知的变化 (诚实评估)

| 变化 | 客户能感知? |
|---|---|
| ClientFactProvider 接入 | ❌ 没 view 实际用, 客户感知 0 |
| frozen 被云端覆盖 bug 修复 | ✅ 客户用 2 个账号时, 本地冻结不会丢 (v1.0 真实 bug) |
| 5 维元数据 schema 计划 | ❌ 文档级, 客户不感知 |
| AI agent 可以作为 actor 预留 | ❌ 3.0 才能用 |

**客户价值评估**: **1 件真实可感知的修复 (frozen 守门)** + **1 套基础设施 (Provider)** + **1 套规范 (元数据)**。前者直接修客户 bug, 中后者为后续铺路。

### 跟整体规划 (v2.2 10-12 周) 的位置

- Phase 1 进度: 6/9 features (F1.1-F1.5 + F1.6a/b 完成, F1.7 即将完成) = **67%**
- Phase 1 剩余: F1.6c/d (跳过) + F1.7 收尾 + F1.8 + F1.9
- 估剩余时间: 2-3 天到 Phase 1 完整收尾

### 失败模式自检 (NORTH_STAR §8)

- ❌ 代码漂亮陷阱: 没出现, 这一组实际修了真实 bug
- ❌ 完美主义陷阱: 没出现, F1.6 spec 修订就是承认做不完
- ❌ 业务并行污染: 没出现, App.tsx 用 backup/restore 干净 commit
- ⚠️ AI session 漂移: 本 session 中段有过 (误读 DATA-CENTER 文档当 v2.2 真目标), 已校准
- ⚠️ B 门连续不动: 第 1 个里程碑未推进, 下个里程碑必须推

---

## 6 · 下一步具体动作

按优先级:

1. **F1.8 + F1.9 同步做**: 把 5 维元数据 schema 字段加到 atomic_facts / event_lines / tasks / commitments / risk_signals 5 张表, 包括:
   - actor_type / actor_id (N3 A1)
   - verification_status / confidence_source / confidence_score (N3 A4 + N2 5 维)
   - source_type / content_role / speaker_person_id / time_anchor (N2 5 维)
   - validity_status / superseded_by_id (N2 5 维)
   - event_log 表 (N3 A2)
2. **直接推进 B 门**: 在某个 view (推荐 StrategicClarificationView 客户档案 tab) 用 useClientContext 显示真实数据, 提供"客户事件线/任务"答题能力的前端基础, 也算实质 view 接入
3. **写 Phase 1 整体收尾文档**: F1.6/F1.7/F1.8/F1.9 全完成后, 跑 Phase 1 三校验门 (A+B+C), 出 V2.2_PHASE1_FINAL_EVAL.md

---

**这份 audit 不是给 Evaluator 的代码评估, 是给后续任何 session 接手时校准方向用的。如果数字过期请重新跑。**
