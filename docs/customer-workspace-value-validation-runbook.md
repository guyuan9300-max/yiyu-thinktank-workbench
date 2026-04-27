# Customer Workspace Value Validation Runbook

## Goal
- Validate that customer workspace answers are directly usable before expanding rollout.
- Use customer-visible value, not only backend safety metrics, as the release gate.

## Prerequisites
- `workspace_chat_data_center_primary = true`
- retrieval settings: `chatKernelPrimaryEnabled = true`
- allowlist contains the target client
- `eval_data_center_p23.py --strict` passes
- `eval_data_center_operational_p26.py --strict` is green or only blocked by non-code rollout artifacts

## Validation Flow
1. Select 1 real client.
2. Enable Kernel Primary for that client through the allowlist path only.
3. Start a `workspace-value-validation-session` from `WorkspaceAnswerValuePanel`.
4. Ask 10 real questions:
   - 这个客户是谁？
   - 核心业务是什么？
   - 最新战略是什么？
   - 当前合作推进到哪了？
   - 现在最大的风险是什么？
   - 下一步建议先做什么？
   - 系统内有哪些已批准正式判断？
   - 这个判断有什么证据？
   - 最近会议留下了哪些行动项？
   - 还有哪些资料缺口？
5. For each assistant answer, use the message footer actions to record:
   - usable / not usable
   - reviewer note
   - manual baseline minutes
   - data center review minutes
6. In `WorkspaceAnswerValuePanel`, use `用最近复核完成当前题` to progress the session.
7. Push at least 1 accepted answer into a proposal and continue it to an execution ticket.
8. Generate 1 evidence quality snapshot.
9. Review the failure pool and resolve any known false positives.
10. Run the customer workspace release report and runtime alignment check.
11. Decide keep / watch / rollback.

## Workspace Answer Experience
- Prefer `workspaceAnswerExperience` as the user-facing contract.
- `ready`: show answer card directly, no warning banner.
- `usable_with_boundary`: keep the answer card visible and show only a light boundary hint.
- `degraded`: keep answer visible, but treat it as a lead rather than a final answer.
- `needs_retry`: only this state should show the retry warning.

## Session 操作
1. Click `开始 10 问价值验证`.
2. Click `复制下一问题` and ask it in the client workspace.
3. For the returned answer, click:
   - `可用`
   - `不可用`
   - `记录耗时`
4. Back in the panel, click `用最近复核完成当前题`.
5. Repeat until 10/10.
6. Click `生成价值验证报告`.

## Answer To Action
- If the answer card contains action cards, prefer those buttons over manual ad-hoc actions:
  - `生成提案`
  - `创建任务`
  - `请求补证据`
- At least one answer in the session should be pushed through:
  - proposal draft
  - proposal approval
  - execution ticket

## Failure Pool
- Review `最近不可用回答` in `WorkspaceAnswerValuePanel`.
- Common failure types:
  - `retry_banner`
  - `too_template_like`
  - `no_evidence`
  - `no_direct_answer`
  - `boundary_violation`
  - `kernel_not_used`
  - `answer_too_short`
  - `user_marked_not_usable`
- Resolve only after the underlying issue is confirmed fixed or accepted as noise.

## Release Gates
- `retryBannerRate <= 0.10`
- `readyOrUsableRate >= 0.75`
- `needsRetryRate <= 0.10`
- `kernelPrimaryUsedRate >= 0.80`
- `businessStrategySlotHitRate >= 0.75`
- `officialBoundaryPass == true`
- `candidateBoundaryPass == true`
- `answerTooTemplateLikeRate <= 0.15`
- at least 10 human-reviewed answers

## Rollback Triggers
- `workspaceRetryBannerRate > 0.20`
- `workspaceReadyOrUsableRate < 0.75` and `workspaceNeedsRetryRate > 0.10`
- any official/candidate boundary violation
- `p95Latency > baseline * 1.5`

## Commands
```bash
cd backend
uv run python scripts/eval_customer_workspace_answer_value_p27.py --strict
uv run python scripts/check_customer_workspace_value_runtime_alignment_p29.py --strict
uv run python scripts/eval_data_center_p23.py --mode baseline --strict
uv run python scripts/eval_data_center_operational_p26.py --strict
uv run python scripts/generate_customer_workspace_release_report_p27.py
```
