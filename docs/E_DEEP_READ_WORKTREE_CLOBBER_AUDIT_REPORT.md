# E · 深读管线工作树污染与恢复路径诊断报告(三态取证)

- 线程 E · 2026-05-27 · 只读取证(未改 main.py / 未 checkout / 未 reset / 未重建)
- 隔离环境:`git worktree add --detach /tmp/yiyu-clean-head HEAD` + 临时 DB 副本 `/tmp/yiyu-deepread-test/app.db`

## 1. 最终裁决:**A —— 工作树污染,建议外科式恢复**

已提交 HEAD 的深读管线**本来就是好的、且实测可用**;当前运行失败是因为**工作树 `backend/app/main.py` 被多 AI 跨 worktree 覆盖,丢掉了 E 已提交的 W2 deep-read worker 线程 + W4 /local-ai 端点**。**不需要重建 DocumentEnrichmentService(路线 B)。**

## 2. 三态对比(HEAD / 工作树 / runtime)

| 能力 | HEAD(已提交) | 当前工作树 | runtime(运行版) |
|---|---|---|---|
| `/local-ai/settings\|coverage\|backfill` 端点 | ✅ 有(4) | ❌ 无(0) | ❌ 404(历史日志实测) |
| W2 deep-read-worker 启动线程 | ✅ 有(12 处引用) | ❌ 无(被删) | ❌ worker 没起 → card-gen attempts=0 |
| card-gen `_qwen_generate` 修复 | ✅ 有(3) | ✅ 有(在 local_model_optimizer.py,未被污染) | ✅ |

→ 工作树 main.py `git diff HEAD` = **删 135 行(E 的 W2/W4 深读)+ 增 156 行(他人活)**,`M backend/app/main.py`。

## 3. M1 关键 commit 能力对账(全在 HEAD 祖先)

| commit | card-gen fix | W2 worker | W4 端点 | 结论 |
|---|---|---|---|---|
| d6111f4 | ✅ 引入 _qwen_generate | — | — | 在 HEAD 祖先 |
| d9f529c | — | ✅ | ✅ 引入 /local-ai/* | 在 HEAD 祖先 |
| fdb8efd | — | ✅ | ✅ | 在 HEAD 祖先 |
| 7979817(merge origin/main) | — | — | — | merge 改了 main.py 120 行 |
| **HEAD(e938f66)** | ✅ | ✅(12) | ✅(4) | **已提交代码完整** |

## 4. M2 工作树 main.py diff 三分类

| 代码块 | 类型 | 来源 | 保留? | 恢复策略 |
|---|---|---|---|---|
| W2 deep-read-worker startup/shutdown 线程 | A·丢失 | E(HEAD) | 恢复 | 从 HEAD 取回 |
| `/local-ai/settings` GET+PUT | A·丢失 | E(HEAD) | 恢复 | 从 HEAD 取回 |
| `/local-ai/coverage` | A·丢失 | E(HEAD) | 恢复 | 从 HEAD 取回 |
| `/local-ai/backfill` | A·丢失 | E(HEAD) | 恢复 | 从 HEAD 取回 |
| `import local_model_optimizer_worker_loop` | A·丢失 | E(HEAD) | 恢复 | 从 HEAD 取回 |
| `_persist/_restore_maintenance_state` + 维护持久化 | B·新增 | 维护修复(本会话) | **保留** | 不动 |
| `get_team_sync_stats`/`enqueue-all`/`run-once` 端点 | B·新增 | B 的 V2.3 | **保留** | 不动 |
| `predict_plan_link_from_text` + 端点 | B·新增 | 他人 | **保留** | 不动 |
| AppState 字段区(deep_read_thread/stop vs 新增) | C·冲突 | E + 他人 | 都要 | 人工合并 |

## 5. M3 runtime 路由验证
历史日志实测:`PUT/GET /api/v1/local-ai/settings` → **404**(运行版缺该路由)。情况 = **"HEAD 有、工作树无、runtime 404"→ 工作树污染导致 runtime 缺失**(非路由注册 bug、非 commit 不完整)。(注:本会话为做干净 benchmark 已退出该 app,故未再 curl;以日志 + 代码三态为据。)

## 6. M4 worker 任务链路验证
card-gen `attempts=0` 直接原因 = **B(worker 未启动)**:工作树 main.py 删了 W2 `deep-read-worker` 启动线程 → 没有常驻 worker → 队列任务无人 claim → attempts 永远 0。**不是 profile 跳过、不是 worker 代码缺失**(代码在 HEAD + local_model_optimizer.py 都在)。

## 7. M5 干净 HEAD 隔离验证(决定性)
环境:`/tmp/yiyu-clean-head`(HEAD e938f66 干净检出)+ 临时 DB 副本 + 豆包,**未碰真库/真工作树**。

| 项 | 结果 |
|---|---|
| 测试文档 | 汇丰超级平台建设计划书.pdf(正文 19178 字) |
| `_process_document_card_task`(HEAD 代码,豆包) | **40.0s 成功** |
| 汇丰 document_cards | **0 → 1** ✅ |
| 生成卡质量 | 真实摘要(173 字 summary + 关键词 汇丰/超级平台/RC积分/权益资产),**非乱码** |

→ **已提交 HEAD 的深读管线可用(card-gen 产出真实卡片)。** 之前"全坏"是工作树污染的假象。

## 8. M6 外科式恢复 patch plan(本轮不执行,仅出方案)

目标:`工作树 main.py = HEAD 的 E 深读代码(W2+W4) + 保留 maintenance + team-sync + predict`。

步骤(建 integration 分支做,**禁止** `git checkout HEAD -- main.py` / `reset --hard`):
1. 从 HEAD 提取 4 个 A 类区块(W2 worker startup/shutdown + import + W4 三端点)的精确文本(`git show HEAD:backend/app/main.py`)。
2. 在当前工作树 main.py 对应位置**插回**这些区块(它们与 maintenance/team-sync/predict 区域不重叠,见 §4)。
3. 处理 C 类冲突:AppState 字段区把 `deep_read_thread/deep_read_stop` 与新增字段并存;startup 区把 deep-read-worker 线程与新增逻辑并存。
4. `npx tsc --noEmit`(前端不受影响)+ `py_compile main.py`。
5. baton 标 `E_HOLDING backend/app/main.py` + inbox-B 知会(team-sync 同文件)。

## 9. M7 恢复后验证方案
1. `GET/PUT /local-ai/settings` → 200;`/coverage` 200;`/backfill` dry-run 可。
2. 启动日志出现 `deep-read-worker` 线程。
3. 入队汇丰 1 篇 + 士平 1 篇 → `attempts` 0→>0、`document_cards` 增加。
4. 不影响 team-sync / maintenance / predict_plan_link(三者端点仍 200)。
5. 通过后再考虑小批量(汇丰 6 / 士平 14)+ hydrate→surrogate→coverage 复测。

## 10. 结论口径
- **A. 是工作树污染** ✅(三态对比 + M5 实证)。
- **B. HEAD 深读代码可用** ✅(40s 产出真实卡)。
- **C. runtime 404/attempts=0** = 工作树删了 W2 worker + W4 端点。
- **D. 建议走恢复路线 A**(外科式,保留 maintenance/team-sync/predict)。
- **E. 不需要 DocumentEnrichmentService 路线 B**——已提交管线本就能用,重建是浪费。

## 11. P0/P1/P2
- **P0**:工作树 main.py 污染使已验证深读能力在运行版消失;多 AI 共改 main.py 无 baton 导致互相覆盖(本会话亲历:E 深读 / B team-sync / 维护修复 三方缠在一个未提交文件)。
- **P1**:恢复需人工合并 C 类冲突;恢复后 worker 性能(40s/篇 doubao,841 篇=数十小时)+ 失败率仍需在批量前压;真库当前 document_cards 仍多客户=0(需恢复后重跑 worker 补)。
- **P2**:给 main.py 这类巨型 monolith 建更强的并行编辑保护(baton 强约束 / 拆分)。

## 12. 原文证据
- 隔离脚本:`/tmp/yiyu-clean-head/scripts/e_m5_cleanhead_1doc.py`;结果 `/tmp/e_m5_result.json`。
- 三态:`git diff --stat HEAD -- backend/app/main.py`(156+/135-);HEAD main.py local-ai 端点=4、worker=12;工作树=0/0。
- 上游:`docs/E_DOC_ENRICHMENT_M0_OLD_PIPELINE_DIAGNOSIS.md`、`docs/E_SEARCH_STACK_*`(61-E)。
