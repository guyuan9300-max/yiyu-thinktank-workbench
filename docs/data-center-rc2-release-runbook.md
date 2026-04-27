# 数据中心 RC2 发布 Runbook（P2.6）

## 1. 发布前检查
- 修复并验证 Kernel Primary gate：空 allowlist 必须拒绝放行。
- 运行 `uv run python scripts/run_data_center_full_regression_p25.py` 并确认 `backend/output/P2.5-full-regression-report.json` verdict 为 `pass`。
- 运行 strict eval：
  - `uv run python scripts/eval_data_center_realistic_p22.py --mode baseline --strict`
  - `uv run python scripts/eval_data_center_p23.py --mode baseline --strict`
- 运行前端构建：
  - `npm run build:main`
  - `npm run build:renderer`
  - `npm run build:backend-check`
- 生成运营产物：
  - `uv run python scripts/generate_kernel_primary_rollout_report_p26.py`
  - `uv run python scripts/generate_evidence_quality_snapshot_report_p26.py`
  - `uv run python scripts/generate_data_center_rc2_release_report.py`

## 2. 灰度阶段
- Stage 1：`stage_1_client`，1 个客户，观察 24h。
- Stage 2：`stage_3_clients`，3 个客户，观察 24h。
- Stage 3：`stage_10_clients`，10 个客户，观察 24h。
- 每次进入阶段前使用：
  - `POST /api/v1/data-center/kernel-primary-rollout/start`
  - 阶段结束后使用：`POST /api/v1/data-center/kernel-primary-rollout/{run_id}/complete`

## 3. 监控指标
- Kernel Primary：
  - `kernelPrimaryFallbackRate`
  - `answerQualityFailRate`
  - `officialBoundaryViolation`
  - `candidateBoundaryViolation`
  - `p95LatencyMs`（相对 baseline）
- Execution Retry：
  - failed tickets
  - retry exhausted
  - retry success rate
  - avg retry count
  - oldest failed ticket age(h)
  - failure reason TopN
  - failed stage TopN
- Evidence Feedback：
  - useful/noise/needs_review 分布
  - 快照推荐规则是否稳定
- Customer Workspace Value：
  - `readyOrUsableRate`
  - `usableAnswerRate`
  - `retryBannerRate`
  - `needsRetryRate`
  - `answerTooTemplateLikeRate`
  - `humanReviewCount`
  - `estimatedTimeSavedRate`
  - `proposalCreatedFromAnswerCount`
  - `executionTicketCreatedFromAnswerCount`

## 4. 回滚条件
- 任一出现即建议回滚：
  - `officialBoundaryViolation > 0`
  - `candidateBoundaryViolation > 0`
  - `kernelPrimaryFallbackRate > 0.2`
  - `answerQualityFailRate > 0.1`
  - `p95LatencyMs > baseline * 1.5`

## 5. 回滚步骤
1. 执行 dry-run：
   - `POST /api/v1/data-center/rollback-drill` with `{"dryRun": true}`
2. 人工确认后执行：
   - `POST /api/v1/data-center/rollback-drill` with `{"dryRun": false}`
3. 对指定 rollout run 记录回滚：
   - `POST /api/v1/data-center/kernel-primary-rollout/{run_id}/rollback`

## 6. 验收标准
- `kernelPrimaryGateEmptyAllowlistPass=true`
- `fullRegressionVerdict=pass`
- `p22StrictPass=true`
- `p23StrictPass=true`
- `rollbackDrillPass=true`
- `executionRetryMetricsAvailable=true`
- `evidenceQualitySnapshotPass=true`
- `opsPanelP25ContractPass=true`
- `rolloutRuns>0`
- `releaseReportVerdict=pass`
- `officialBoundaryPass=true`
- `candidateBoundaryPass=true`
- `noAutoExecutionViolation=true`
- `runtimeValueAlignmentPass=true`
- `humanReviewCount>=10`
- `proposalCreatedFromAnswerCount>=1`
- `executionTicketCreatedFromAnswerCount>=1`

## 7. 客户工作台价值验证
1. 在 `WorkspaceAnswerValuePanel` 启动 `10 问价值验证` session。
2. 使用真实客户连续问完 10 个标准问题。
3. 对每条回答执行：
   - `可用` 或 `不可用`
   - `记录耗时`
4. 至少把 1 条高质量回答推进为 proposal，并继续到 execution ticket。
5. 运行：
   - `uv run python scripts/check_customer_workspace_value_runtime_alignment_p29.py --strict`
   - `uv run python scripts/generate_customer_workspace_release_report_p27.py`
6. 若 `humanReviewCount < 10`，或 `retryBannerRate`、`readyOrUsableRate` 不达标，发布结论保持 `hold`。
## 8. 已知风险
- 灰度期间可能出现 client 级别冷启动波动，需要结合 fallback rate 与 p95 同步判定。
- execution retry 指标依赖日志完整性，若历史票据未写全日志会导致 TopN 失真。
- evidence quality 快照当前只做建议沉淀，不自动改权重，仍需人工决策后再调参。
