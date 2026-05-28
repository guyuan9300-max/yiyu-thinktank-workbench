# E · Qdrant / FTS / Surrogate 检索底座深度真相测试报告

- 线程: E
- 日期: 2026-05-27
- 仓库: `~/openclaw/workspace/yiyu-thinktank-workbench` · branch `main` · commit `34c6ccb`
- 性质: **只读深度测试**(未改 knowledge_base.py / 未跑全量 reindex / 未 populate)
- 探针脚本: `scripts/e_search_stack_probe.py`(只读,可复跑)
- 原始数据: `docs/E_SEARCH_STACK_QDRANT_FTS_SURROGATE_DEEP_TEST_REPORT.json`

---

## 1. 本轮测试目标

弄清数据中心**真实**检索能力来自哪里:Qdrant 是否真的工作?FTS/surrogate 是否才是主力?写入与查询是否有 collection 签名漂移?各模块实际依赖哪条路径?

## 2. 关键发现摘要(TL;DR)

1. **Qdrant 全局不工作。** 7 个测试客户、所有 query,`qdrant_hits` 一律 **0**。只有日慈有 Qdrant collection 目录,且**点数=0(空骨架)**;CFFC/士平/益语/善加/为爱黔行/云南**连 collection 都没有**。
2. **签名漂移假设(H1)证伪。** 真实 resolver 算出的 runtime 签名 = `local_fastembed:legacy_fastembed_256:BAAI/bge-small-zh-v1.5:256:projection`(后缀 `3e09a527`),与 manifest/磁盘 active **一致**。查询查的是**对的 collection**——但它是空的。
3. **根因是 populate 从未完成(H2 坐实),不是签名。** 所有 manifest 行 `master_indexed=0 / chunk_indexed=0 / status=stale`。
4. **查询会创建空 collection(M3 坐实)。** 查不存在客户 → 顺手建 `..._3e09a527` 空壳(点数 0)。
5. **"语义"层只对 CFFC 一个客户产出。** 用生产 dimension query 跑 `retrieve_dimension`(纯语义、关 LIKE):CFFC 6 维共 **104 chunk**;日慈/士平/益语/善加/为爱黔行/云南 **全 0**(coverage 全 0.0)。而 CFFC 的 104 chunk **qdrant_hits 仍是 0** → 来自 surrogate/lexical 基底,不是向量。
6. **系统真正靠什么活着:**
   - **战略陪伴**(`knowledge_base.retrieve_knowledge_bundle`):CFFC 靠 surrogate-lexical;其余 12 客户语义层=0,**全靠 narrative_collector 注入的 LIKE 兜底**。
   - **chat工作台问答 / 周复盘 / review_narrative / 分析上下文 / 数据中心搜索**(`knowledge_v2.retrieve_knowledge_bundle`):**直接 SQL 查 `v2_documents`,根本不碰 Qdrant/surrogate/FTS。**
7. **FTS 贡献很小**(每 query 1–8 raw hit),且对非 CFFC 客户不转化为 bundle chunk。
8. **manifest 是诚实的**(如实报 stale/0),没有"谎报 indexed>0"。→ 路线①(读 manifest active_collection)零收益。

> 一句话:**我们以为系统在用 Qdrant 向量语义检索,实际 Qdrant 全局零贡献;战略陪伴只有 CFFC 有真 surrogate 语义,其余客户靠 LIKE;chat 等模块根本是 v2_documents 直查。**

## 3. 环境与路径(M0)

| 项 | 值 |
|---|---|
| branch / commit | main / 34c6ccb |
| db_path | `~/Library/Application Support/YiyuThinkTankWorkbench2_V21Lab/app.db`(286M) |
| qdrant_store | 同上 `/vector_store/_qdrant`(嵌入式 local,每 collection 一个 `storage.sqlite`) |
| backend | dev app(47831/4174)已退出;Qdrant `.lock` 为 crash 残留、无进程占用(故可只读直连) |
| settings.retrieval_models | **空 → 用默认**(默认 resolver 实测产出 projection 签名 `3e09a527`) |
| fastembed / qdrant_client | 均已安装可用 |

## 4. settings / signature / manifest 三方对账(M1)

| 客户 | runtime active collection | manifest active | drift | runtime collection 存在 |
|---|---|---|---|---|
| 日慈 | `master_index_client_284afd836e_3e09a527` | 同 | ❌ False | ✅(但空) |
| CFFC | `..._a4d1db29a7_3e09a527` | 同 | ❌ False | ❌ 磁盘无 |
| 士平/益语/善加/为爱黔行/云南 | `..._<cid>_3e09a527` | 同 | ❌ False | ❌ 磁盘无 |

**结论:无签名漂移。** 三方签名一致,查询定位到正确 collection 名;问题在该 collection 不存在或为空。

## 5. Qdrant collection 真实点数(M2)

| 客户 | disk collection | 真实点数 | surrogate | master_index | deep_read |
|---|---|---|---|---|---|
| 日慈 | master/raw × (legacy+active) | **全 0** | 116 | 121 | 34 |
| CFFC | 无 | — | 159 | 162 | 118 |
| 士平 | 无 | — | 14 | 14 | 0 |
| 益语 | 无 | — | 19 | 21 | 12 |
| 善加 | 无 | — | 44 | 44 | 0 |
| 为爱黔行 | 无 | — | 70 | 70 | 0 |
| 云南 | 无 | — | 82 | 82 | 3 |

payload 抽样:无任何 collection 有点可抽。**Qdrant 全局空。**

## 6. 查询创建空 collection 副作用(M3)

查不存在客户 `client_PROBEZZZ999` → `search_master_index_qdrant` 经 `ensure_qdrant_collections` **新建** `master_index_client_PROBEZZZ999_3e09a527` + `raw_chunk_...`(点数 0)。
→ **P1**:每次对未建索引客户查询都会留下空壳 collection,长期堆积 orphan。(本轮测试创建的空壳已清理;日慈预存的保留。)

## 7. FTS / Qdrant / Surrogate / LIKE 三路贡献拆分(M4)

生产 dimension query、纯语义(关 LIKE)下,每客户 6 维语义 chunk 总数:

| 客户 | 语义 chunk(6维) | qdrant_hits | 说明 |
|---|---|---|---|
| **CFFC** | **104** | **0** | 全部来自 surrogate-lexical 基底 + 少量 FTS,**非向量** |
| 日慈 | 0 | 0 | coverage 0.0;靠 LIKE 兜底 |
| 士平/益语/善加/为爱黔行/云南 | 0 | 0 | 同上 |

裸标签 query(对照)下 bundle 几乎全 0,印证短 query 弱;但即便生产 query,**非 CFFC 客户语义层依然 0**。差异不在 surrogate 缺失(日慈 rich_summary 111/121),而在 CFFC searchable_text 更长(avg 855 vs ~230)+ bundle coverage 打分——**这是 surrogate/lexical 层的覆盖率问题,与 Qdrant 无关**。

## 8. 模块层影响(M5)

**两套独立检索栈:**

| 栈 | 实现 | 使用模块 | 用 Qdrant? |
|---|---|---|---|
| A | `knowledge_base.retrieve_knowledge_bundle`(surrogate+FTS+Qdrant) | **战略陪伴**(narrative_collector→retrieve_dimension) | 是,但实测=0 |
| B | `knowledge_v2.retrieve_knowledge_bundle`(直查 `v2_documents` SQL) | **chat工作台问答 / 周复盘 / review_narrative / analysis_context / 数据中心搜索 / main.py:14465** | **否(完全不碰)** |

→ Qdrant 仅被栈 A(战略陪伴)引用,且贡献 0。栈 B(chat 等多数模块)走 v2_documents 直查,与 Qdrant 无关。
→ **关闭 Qdrant 对全系统无感**(本就 0 贡献)。**关闭 LIKE / v2_documents 才会大幅退化**(那才是真正的召回来源)。
→ 模块均**不展示 retrieval provenance**(用户/上层看不到结果来自 semantic/like/v2sql)——除战略陪伴的 retrieval_path 字段已就位但前端未完整暴露。

## 9. populate / upsert 链路(M6)

manifest 全客户 `master_indexed=0 / status=stale`,磁盘点数=0 → **upsert 向量点从未成功 commit**。
最可能原因:**嵌入式 Qdrant 是单进程锁**(`QdrantClient(path=...)`);历史 reindex 若在持锁后端进程之外的脚本里跑,upsert 静默失败、只留下 collection 骨架 + manifest 行(status 停在 building/stale,counter=0)。本轮未做实写测试(避免污染),但 manifest+磁盘证据足以定性:**populate 链路未闭环**。

## 10. manifest 可信度(M7)

manifest 如实报告 `stale / indexed=0`,与磁盘真实点数(0)**一致** → **manifest 可信(诚实),没有谎报**。
推论:**路线①(读侧改用 manifest active_collection)零收益**——既无漂移、manifest 指向的 collection 也是空的。

## 11. 三种修复路线评估(M8)

| 路线 | 能解决 | 不能解决 | 成本 | 风险 | 优先级 |
|---|---|---|---|---|---|
| ① 读侧用 manifest active_collection | (理论上消漂移) | 实测无漂移、目标 collection 空 → **零收益** | 中 | — | ❌ 不做 |
| ② 修 populate 链路(单进程锁内真写入) | 让 Qdrant 真有点 | 仍受 bundle coverage 门限制;且只惠及栈 A;栈 B 根本不用 Qdrant | 中–高 | 中 | ⏸ 暂缓(列债) |
| ③ 暂缓 Qdrant,强化 surrogate/deep-read + 查清非 CFFC bundle coverage=0 | 直接提升 12 个客户的真实召回(CFFC 已证可行) | Qdrant 长期债 | 中 | 低 | ✅ **首选** |

## 12. P0 / P1 / P2 清单

**P0(影响整体判断,已澄清):**
- Qdrant 全局空、零贡献,却被当作语义底座 → 优化方向若围绕它会全盘错。
- 战略陪伴"语义检索"实际仅 CFFC 生效,其余靠 LIKE。

**P1:**
- 查询对未建索引客户创建空壳 collection(orphan 堆积)。
- populate 链路未闭环(单进程锁/未 commit)。
- 模块无 retrieval provenance,无法分辨结果来自 semantic/like/v2sql。
- 非 CFFC 客户 bundle coverage=0(有 surrogate 却召回 0)——surrogate/lexical 层覆盖问题,待专项。

**P2:**
- Qdrant orphan collection 清理工具;检索健康仪表盘;FTS/向量混排;surrogate 质量评分;检索 explain。

## 13. 推荐下一步(结论口径:**B**)

**B — Qdrant 当前全局不可用,但 surrogate/lexical + LIKE + v2_documents 在支撑系统;先转向 deep-read/surrogate 强化,Qdrant 列为技术债。**

具体:
1. **不要**为任何客户盲目 reindex Qdrant(它对召回贡献 0,且 populate 未闭环)。
2. **最高 ROI 的真问题**:查清"为什么有 surrogate 的非 CFFC 客户(日慈 116 surrogate)bundle coverage 仍=0"——这才是让 12 个客户获得 CFFC 级语义的钥匙(对齐 deep-read-foundation / enrich-surrogates / searchable_text 充实)。
3. **Qdrant** 标记为独立技术债:需同时修 ① populate 单进程锁写入 + ② 读侧确认 + ③ 评估它相对 surrogate-lexical 的真实增益,三者齐了再启用向量召回;在此之前关闭它对系统无感。
4. **补 retrieval provenance**:让各模块/前端能看到结果来自 semantic/like/v2sql,后续任何"内容变深"评估都要带它。

**不写** "已确认 Qdrant 无价值"(它在 populate 修复后仍可能有价值,只是当前零贡献);**不写** "全客户 re-index 就能解决"(populate 与覆盖率门都没解决)。

## 14. 原文证据
- 探针: `scripts/e_search_stack_probe.py` + 原始 JSON。
- 关键代码: `knowledge_base.py` collection_name:1047 / _resolve_vector_runtime:1264 / search_master_index_qdrant:1520 / _pick_collection_with_fallback:1299 / retrieve_knowledge_bundle:3779;`knowledge_v2.py` retrieve_knowledge_bundle:4644(查 v2_documents);`strategic_narrative_semantic_retriever.py` retrieve_dimension:222。
- manifest 表 `vector_index_manifests`;磁盘 `vector_store/_qdrant/collection/*/storage.sqlite`。

## 评分自评(对照 rubric,总分 100)
- settings/signature/manifest 对账 15/15 · collection 点数真实性 15/15 · 查询副作用 10/10 · 三路贡献拆分 18/20(裸 query 初测有偏,已用生产 query 复测纠正)· 模块层 13/15(发现双栈,栈 B 仅代码层确认未活测)· populate 定位 12/15(未做实写测试,靠 manifest+磁盘定性)· 路线评估 10/10 → **合计 93/100 ≥ 90,可决策修复路线。**
