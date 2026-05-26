# 52-E · 战略陪伴语义检索 P1 修复与合并准备报告

- 作者: E 线程 | 日期: 2026-05-26
- 分支: `feat/strategic-narrative-semantic-retrieval`
- 上轮: 51-E 强测试 84/100, 结论 B
- 本轮性质: **收口/合并准备**(不扩功能)

## 10/15. 合并结论: **B — P1 基本修复, 建议先合 integration 分支, live 验证后再 main**
回滚开关已实现并验证; 前端来源标记就绪; main.py 零冲突可合; 无 P0。但**真实 live 页面验证需合并+重启生产后端(动产线)**, 且**前端完整可见依赖云端 narrative schema 透传新字段(C 线程)**——这两项我不自主做, 备好交顾源源/协调 C。

## 1. 本轮目标
让已验证的语义取材层进入"可回滚/可解释/可合并"的上线准备态, 不再大改取材层。

## 2. 51-E 吸收
84/100, P0=0, CFFC 2→18-20 / business_intro 11/11, 日慈 reindex_required, live 仍旧代码。本轮只做 P1 收口。

## 3. M1 回滚开关 (完成 ✓)
- 新增开关 `STRATEGIC_NARRATIVE_SEMANTIC_RETRIEVAL_ENABLED`(`semantic_retrieval_enabled()` 读环境, 默认开)。
- `retrieve_dimension` 加 `semantic_enabled` 门控; 关闭 → 跳过 Qdrant/embedding, 仅 LIKE。
- 输出可观测: `retrieval_mode`(semantic / semantic+fallback / fallback_only / legacy_like_only) + `fallback_reason`。
- **实测**(CFFC essence):

| 开关 | retrieval_mode | chunks | 说明 |
|---|---|---|---|
| ON(默认) | semantic | 20 | 全语义 |
| OFF | legacy_like_only | 20 | 全 LIKE, 不崩, reason=semantic_disabled_by_flag |

通过: true 路径生效 ✓ / false 可回退 ✓ / Qdrant 不依赖(OFF 时) ✓ / 不崩 ✓ / 路径可观测 ✓。(Qdrant 不可用 ON 时仍 LIKE 兜底, 日慈语义空案例已验。)

## 4. M2 前端 retrieval_path 来源标注 (我方就绪, 全链路待跨线程)
- **后端**(narrative_generator, 完成): 每段 emit `retrievalMode / fallbackUsed / reindexRequired`(由该段 chunk 的 retrieval_path 统计)。
- **前端**(完成): `NarrativeDimensionRecord` 加可选字段; StrategicClarificationView 维度卡加轻量条件标签(语义检索/语义+兜底/关键词兜底/旧路径, 兜底态带 reindex 提示 title), 无数据时不渲染(forward-compatible, 不破坏现有 references 展示)。
- **关键阻塞(跨线程 P1)**: regenerate 返回的是**云端 ingest 响应**(main.py:29211), 我 emit 的字段进 ingest payload, 但**能否回传前端取决于云端 narrative schema 是否透传**(C 线程 cloud_backend)。仅"云端 ingest 失败 local-only fallback"路径(main.py:29228 `**dims[d]`)直接带回。
- 故 M2 现状: 后端 emit ✓ + 前端就绪 ✓, **完整可见待 (a) 云端 schema 透传(C) (b) live 合并(顾源源)**。
- 备注: 前端改动未在 worktree 跑 tsc(worktree 无 node_modules); 改动为可选字段 + 条件渲染, 风险低, 合并到有 node_modules 环境需补跑 tsc。

## 5. 全客户索引健康度与 re-index 方案 (M3)
| 客户 | 文档 | chunk | facts | surrogate | 分级 | reindex |
|---|---|---|---|---|---|---|
| CFFC | 185 | 3861 | 883 | 157 | semantic-rich | 否 |
| 日慈 | 234 | 2916 | 1014 | **0** | fallback-rich | **是** |
| 益语智库 | 135 | 666 | 97 | **0** | data-thin | 视情况(数据本就薄) |
- (49-E 全 12 客户量已扫; 本轮 surrogate 维度新增, 仅 CFFC>0。)
- **re-index 方案**:
  1. 优先级: 日慈(资料厚但 surrogate=0, 收益最大) > 其它 surrogate=0 且文档多的客户 > 数据本薄的(益语, 收益有限)。
  2. 机制: 重跑知识底座 ingest(`ingest_pipeline` / `knowledge_v2` 的 surrogate + master_index + Qdrant collection 构建), 为该客户 v2_documents 生成 surrogate markdown + 写 `knowledge_surrogates`/`knowledge_master_index` + 建 `vector_store/<client_id>` Qdrant collection。
  3. 影响: 只补建检索索引层, **不动原始 v2_documents/v2_chunks/atomic_facts**(原始事实源不变); 需为该客户重建 Qdrant collection + 重生成 surrogate。
  4. 复测: re-index 后重跑 `scripts/run_depth_stress_test.py`, 看该客户 retrieval_path 从 fallback_only 转为 semantic、surrogate>0。
- **诚实**: 日慈当前 fallback-rich 仅靠 LIKE 兜底, **不能说成"语义检索已充分生效"**; 已标 reindex_required。

## 6. main.py 合并风险检查 (M4)
```
main.py conflict status: 无冲突
E changed lines: 1 行 (main.py:28150, /next-steps: days=30,max_items=30 → days=3650,max_items=60)
B changed lines: main 分支自 fork(cc84975) 后未提交 main.py 改动 (cc84975..main 对 main.py 为空)
merge risk: 低 (单行, 在 list_next_steps 内, 与 B 的 BackgroundTasks 区不重叠; 且 main 当前无该文件新提交)
resolution: 直接合并即可; 若 B 之后提交 main.py, 因区域不同仍应自动 merge, 冲突概率低
```

## 7. live 页面真测 (M5) — 未做, 产线门, 待顾源源
- 需: 合并到 integration/main + **重启 live 生产后端**(47831 当前跑旧代码) + regenerate 会写 commitments 本地库/POST 云端(副作用)。
- 属动产线的不可逆/外向操作, **E 不自主执行**(符合本指令 §8 B 选项 + 产线安全)。
- 代码层已证(51-E M6): 前端 `regenerateClientNarrative` → `/narrative/regenerate`(29100) → `collect_client_fact_bundle`(29121) → 新 retriever。即合并+重启后 live 必走新检索。
- **建议步骤(交顾源源/集成)**: 合 integration 分支 → 起一个本分支后端(独立端口或替换) → 打开战略陪伴选 CFFC → regenerate → 验证 6 段更深 + retrieval_path 标签可见(需云端透传) + 无崩。

## 8. 合并后轻量强测 (M6) — 待合并后
- 回归脚本已就绪: `scripts/run_depth_stress_test.py`(M0-M9) + `scripts/run_m6_before_after.py`。
- 合并+重启后重跑, 确认 CFFC 仍 11/11、next_steps 无 30 天窗口、跨客户 0、性能 <30s、retrieval_path 可见。

## 9. P0 / P1 / P2
**P0**: 无。
**P1**:
1. (跨线程·C) 云端 narrative ingest schema 透传 retrievalMode/fallbackUsed → 前端才能完整显示来源。
2. (顾源源·产线) 合并 + 重启 live 后端做真机验证。
3. (数据工程) 日慈等 surrogate=0 客户 re-index, 兑现真语义。
4. 前端 worktree 未跑 tsc(无 node_modules), 合并环境需补跑。
5. collect_client_fact_bundle 默认 caps 放开会被其它调用方(工作台 chat 等)继承, 合并前需 A/B 评估 prompt 体积影响。
**P2**: business_intro 兜底关键词扩同义词; reindex 整页 banner; 维度 query 微调; 检索缓存; source 卡片样式。

## 11. 是否进入前端体验优化
是。后端已 emit + 前端已就绪, 待云端透传后即见效; 进一步做 reindex banner / source 卡片美化属 P2。

## 12. 原文证据
- 51-E 强测试: `docs/E_STRATEGIC_COMPANION_DEPTH_TEST_REPORT.{md,json}`
- 本轮代码: `strategic_narrative_semantic_retriever.py`(开关) / `narrative_generator.py`(emit) / `api.ts` + `StrategicClarificationView.tsx`(前端) / `main.py`(1行)
- 开关实测见 §3。

## 量化目标对照
| 指标 | 上轮 | 本轮 |
|---|---|---|
| 回滚开关 | 无 | **有, 已验证** |
| retrieval_path 前端 | 否 | **就绪(待云端透传)** |
| main.py 冲突 | 待查 | **零冲突** |
| live 页面新检索 | 未生效 | 待合并重启(产线门) |
| 强测复评分 | 84 | ≈86(回滚+前端就绪); 达 ≥90 需 live 验证通过 |
| P0 | 0 | 0 |
