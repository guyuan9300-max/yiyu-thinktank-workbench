# 第一轮绝对安全删除审计

生成时间：2026-04-27

## 本轮结论

本轮只删除生成产物，不删除后端接口、数据库迁移、legacy/FREEZE 主链、Electron IPC、用户数据文件，也不删除当前已有未提交修改的源码文件。

已删除内容通过系统废纸篓处理，未使用不可恢复删除。

## 已删除：S0 可直接清理

| 路径 | 类型 | 删除证据 | 删除方式 |
| --- | --- | --- | --- |
| `backend/output/` | 后端评估、RC、审计报告生成产物 | `git status` 显示为未跟踪目录；内容为 `P2.x` 报告、baseline、eval 输出；不属于运行入口、数据库迁移、用户数据或源代码 | `trash backend/output` |
| `output/ui-consistency-audit/` | UI 静态审计输出产物 | `git status` 显示为未跟踪目录；内容为审计 CSV/JSON/Markdown；旧报告已明确 runtime 验证失败，不能作为继续保留的运行依赖 | `trash output/ui-consistency-audit` |

## 未删除：S1 前端叶子候选

这些文件在 `src` 产品代码中没有 import 或动态入口，但不满足“全仓引用为 0”或存在未提交修改，所以本轮只登记，不删除。

| 路径 | 当前证据 | 本轮处理 |
| --- | --- | --- |
| `src/renderer/components/handbook/GrowthHandbookView.tsx` | `src` 内只有自身定义；历史文档 `docs/thread-sync.md` 多处引用 | 暂不删除 |
| `src/renderer/components/settings/FeishuAccountBindingPanel.tsx` | `src` 内只有自身定义；历史文档仍引用 | 暂不删除 |
| `src/renderer/components/settings/FeishuBotSettingsPanel.tsx` | `src` 内只有自身定义；历史文档仍引用 | 暂不删除 |
| `src/renderer/components/settings/OrganizationTreeCanvas.tsx` | `src` 内只有自身定义；历史文档仍引用 | 暂不删除 |
| `src/renderer/components/settings/UpdateSettingsPanel.tsx` | `src` 内只有自身定义，但文件当前有未提交修改 | 暂不删除，避免误删现有改动 |

## 未删除：S2 高风险类别

- 后端 FastAPI endpoint：前端未绑定不代表无人调用，可能被脚本、云端、运维诊断、外部 webhook 或测试使用。
- 数据库 schema、migration、backfill：即使只运行一次，也可能保护老用户数据。
- `legacy` 兼容逻辑：多数用于旧数据、旧包、旧向量库、旧复盘字段兼容。
- `FREEZE` 标记代码：多数表示旧链路已冻结、暂不继续扩张，不等于可删。
- Electron `main/preload` 和 IPC：涉及启动门禁、安装包、桌面能力，本轮不碰。

## 未删除：S3 需要人工确认

| 路径 | 原因 |
| --- | --- |
| `app.db` | 根目录未跟踪数据库文件，当前大小为 0B；仍按潜在用户数据处理，不自动删除 |
| `output/main-chain/` | 包含 main-chain baseline/wave 输出，可能被 RC 脚本或人工对账使用；本轮不删除 |
| `src/renderer/lib/api.ts` 中的无调用 wrapper | 文件当前已有未提交修改，且 wrapper 删除会改变公共前端 API 面；本轮只登记，不在第一批删除 |

## 验证要求

本轮删除仅涉及未跟踪生成产物，已完成以下验证：

- `npm run build:renderer`：通过；仅保留 Vite chunk size 警告。
- `cd backend && uv run pytest tests/test_data_center_sync_outbox.py tests/test_data_center_ingest.py tests/test_weekly_review_material_pack.py tests/test_weekly_mainline_cards.py -q`：33 passed。
- `cd backend && uv run pytest tests/test_api_smoke.py -q -x`：失败在 `test_template_fill_start_reuses_existing_active_run_for_same_template`，表现为模板填充启动没有复用既有 running run，而是生成了新 `tmplfill_*`。该失败与本轮删除的生成产物无直接关联。

如后续要删除 S1 前端叶子组件，建议先单独开一批，并在删除前更新或确认历史文档引用不再作为保留条件。
