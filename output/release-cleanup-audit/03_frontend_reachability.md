# 03 Frontend Reachability

Generated: 2026-05-06T12:09:27.425Z

## Summary
- Frontend files scanned: 74
- Deleted frontend paths already present in working tree: 5
- Candidate rows below are approximate static reachability signals, not deletion approval.

## Deleted Frontend Paths Currently in Working Tree
- src/renderer/components/settings/ReviewGovernanceSettingsPanel.tsx
- src/renderer/components/strategic_accompaniment/StrategicLearningListPanel.tsx
- src/renderer/components/tasks/HierarchyReportCard.tsx
- src/renderer/components/tasks/WeeklyReviewSimulationPanel.tsx
- src/renderer/components/tasks/WeeklyReviewSummaryPanel.tsx

## Candidate Components / Modules
| Path | Ref Count | Sample Referrers | Recommendation | Evidence |
| --- | ---: | --- | --- | --- |
| src/renderer/components/handbook/GrowthHandbookView.tsx | 0 |  | delete_candidate | no direct basename references in renderer/shared scan |
| src/renderer/components/settings/DataCenterProposalInboxPanel.tsx | 0 |  | delete_candidate | no direct basename references in renderer/shared scan |
| src/renderer/components/settings/FeishuAccountBindingPanel.tsx | 0 |  | delete_candidate | no direct basename references in renderer/shared scan |
| src/renderer/components/settings/FeishuBotSettingsPanel.tsx | 0 |  | delete_candidate | no direct basename references in renderer/shared scan |
| src/renderer/components/settings/OrganizationTreeCanvas.tsx | 0 |  | delete_candidate | no direct basename references in renderer/shared scan |
| src/renderer/components/settings/UpdateSettingsPanel.tsx | 0 |  | delete_candidate | no direct basename references in renderer/shared scan |
| src/renderer/components/tasks/AgentExecutionPanel.tsx | 0 |  | delete_candidate | no direct basename references in renderer/shared scan |
| src/renderer/components/tasks/AgentSimulationCalendarView.tsx | 6 | src/renderer/App.tsx; src/renderer/App.tsx | needs_product_review | deprecated/simulation/legacy naming |
| src/renderer/components/tasks/AgentWeeklyDigestPanel.tsx | 0 |  | delete_candidate | no direct basename references in renderer/shared scan |
| src/renderer/components/tasks/AgentWeeklyPlanPanel.tsx | 0 |  | delete_candidate | no direct basename references in renderer/shared scan |
| src/renderer/components/tasks/ReviewHistoryPicker.tsx | 0 |  | delete_candidate | no direct basename references in renderer/shared scan |
| src/renderer/components/tasks/ReviewMetricGrid.tsx | 0 |  | delete_candidate | no direct basename references in renderer/shared scan |

## Interpretation Rules
- delete_candidate means only “candidate for a later confirmed cleanup batch.”
- needs_product_review means the code may still be reachable but the product concept looks deprecated or debug-only.
- Files already deleted in the working tree should be reviewed as one separate deletion batch, not mixed with new deletions.
