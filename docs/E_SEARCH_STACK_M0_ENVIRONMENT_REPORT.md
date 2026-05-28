# E · 检索底座测试 M0 环境冻结报告

- 日期: 2026-05-27 · 线程 E · 只读测试
- 主报告: `docs/E_SEARCH_STACK_QDRANT_FTS_SURROGATE_DEEP_TEST_REPORT.md`

| 项 | 值 |
|---|---|
| repo | `~/openclaw/workspace/yiyu-thinktank-workbench` |
| branch | main |
| commit | 34c6ccb |
| db_path | `~/Library/Application Support/YiyuThinkTankWorkbench2_V21Lab/app.db`（286M） |
| qdrant_store_path | `~/Library/Application Support/YiyuThinkTankWorkbench2_V21Lab/vector_store/_qdrant`（嵌入式 local，每 collection = 一个 storage.sqlite） |
| backend_process | dev app（47831/4174）已退出；老 factory backend 在 47830；Qdrant `.lock` 为 crash 残留、无进程占用 → 可只读直连 |
| settings.retrieval_models | 空 → 用默认；默认 resolver 实测产出签名 `local_fastembed:legacy_fastembed_256:BAAI/bge-small-zh-v1.5:256:projection`（后缀 3e09a527） |
| embedding_provider | local_fastembed / BAAI/bge-small-zh-v1.5 / dim 256 / projection |
| fastembed | 已安装可用 |
| qdrant_client | 已安装可用 |
| feature flag | STRATEGIC_NARRATIVE_SEMANTIC_RETRIEVAL_ENABLED（语义检索回滚开关，本轮按默认开启测） |
| 测试客户 | CFFC / 日慈 / 士平 / 益语智库 / 善加 / 为爱黔行 / 云南儿童（5 指定 + 2 随机） |

通过标准:db 路径、Qdrant store 路径、settings 状态、runtime resolver 输入 — 均已 100% 明确。
