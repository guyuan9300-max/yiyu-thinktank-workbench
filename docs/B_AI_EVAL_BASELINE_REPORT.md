# B AI 评估基线报告 · 自动验收官

> 生成: 2026-05-23T11:08:57.908567+00:00
> commit: `efd6870cf5` · backend: http://localhost:47831
> db: `/Users/guyuanyuan/Library/Application Support/YiyuThinkTankWorkbench2_V21Lab/app.db`
> client: 日慈基金会 (client_284afd836e)
> mode: capability-probe

**北极星**: 每次软件能力变化, 自动评估 "用户看到了什么 / AI 是否真调度软件做事".
**不替 A 写复杂业务. 不为过线改标准.**

## L1 · capability-probe (19 个关键 endpoint)

通 2 / 部分 12 / 缺 0 / 共 14

| Method | Path | 名称 | 状态 |
|---|---|---|---|
| POST | `/api/v1/meeting-minutes/process` | R2 会议纪要 | ✅ 通 |
| GET | `/api/v1/approvals` | R2 待审批 list | ✅ 通 |
| POST | `/api/v1/clients/client_284afd836e/workspace/chat` | 工作台问答 | ⚠️ timeout (LLM 慢非 404) |
| GET | `/api/v1/clients` | 客户列表 | ⚠️ timeout (LLM 慢非 404) |
| POST | `/api/v1/contracts/draft` | V3.0 合同草稿 | ⚠️ timeout (LLM 慢非 404) |
| POST | `/api/v1/templates/generate` | V3.0 模板生成 (理事会说明等) | ⚠️ timeout (LLM 慢非 404) |
| POST | `/api/v1/clients/client_284afd836e/brand-proposition` | V3.0 品牌建议 | ⚠️ timeout (LLM 慢非 404) |
| GET | `/api/v1/clients/client_284afd836e/data-gaps` | V3.0 P0a Data Gap API | ⚠️ timeout (LLM 慢非 404) |
| POST | `/api/v1/agent/plan` | V3.0 P1 Goal-Plan | ⚠️ timeout (LLM 慢非 404) |
| POST | `/api/v1/agent/run` | V3.0 P1 Goal-Run | ⚠️ timeout (LLM 慢非 404) |
| GET | `/api/v1/agent-run-logs` | Agent Run Log list | ⚠️ timeout (LLM 慢非 404) |
| POST | `/api/v1/intelligence/brand-mirror/analyze` | 品牌分析 | ⚠️ timeout (LLM 慢非 404) |
| POST | `/api/v1/clients/client_284afd836e/strategic-cockpit/meeting-pack` | 会谈提纲 | ⚠️ timeout (LLM 慢非 404) |
| POST | `/api/v1/clients/client_284afd836e/workspace/smart-import` | 智能文件导入 | ⚠️ timeout (LLM 慢非 404) |

---

**关联**:
- 评估标准: `docs/B_AI_EVAL_STANDARD_V1.md`
- Golden Test Pack: `docs/B_AI_GOLDEN_TEST_PACK.md`
- V3.0 报告: `docs/V3_0_AI_DRIVEN_SOFTWARE_EVAL_REPORT_<timestamp>.md`
- 进展雷达: `docs/B_AI_PROGRESS_RADAR.md`