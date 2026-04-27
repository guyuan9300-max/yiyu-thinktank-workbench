# Dirty Paths Ledger

Recorded at: 2026-04-27 18:06:37 CST

## Main repository dirty paths

| Repo | Path | State | Classification | Rationale | Recommended action |
| --- | --- | --- | --- | --- | --- |
| main | .gitignore | modified | product_code | 防漂移规则补齐，防止未来生成物再次进入协作提交。 | 本轮小批提交。 |
| main | .yiyu-sync/settings.system_admin.json | untracked | shared_config | 仅含系统权限开关与品牌 Logo data URL，未命中 secret 关键词。 | 作为共享设置单独提交；若团队不希望共享 Logo，再转 local/private。 |
| main | output/worktree-cleanup/ | untracked | audit_output | 本轮计划指定的审计底稿目录。 | 随本轮审计提交。 |
| main | output/worktree-cleanup/v2-merge-migration/20260427-161554/calendar-empty-root-cause-fix.json | untracked | audit_output | V1 到 V2 数据迁移证据，保留用于解释当前 V2 数据来源。 | 归档在本轮审计产物下，不作为运行依赖。 |
| main | output/worktree-cleanup/v2-merge-migration/20260427-161554/db-merge-report.json | untracked | audit_output | V1 到 V2 数据迁移证据，保留用于解释当前 V2 数据来源。 | 归档在本轮审计产物下，不作为运行依赖。 |
| main | output/worktree-cleanup/v2-merge-migration/20260427-161554/file-copy-and-final-check.json | untracked | audit_output | V1 到 V2 数据迁移证据，保留用于解释当前 V2 数据来源。 | 归档在本轮审计产物下，不作为运行依赖。 |
| main | output/worktree-cleanup/v2-merge-migration/20260427-161554/growth-signal-fk-repair.json | untracked | audit_output | V1 到 V2 数据迁移证据，保留用于解释当前 V2 数据来源。 | 归档在本轮审计产物下，不作为运行依赖。 |
| main | output/worktree-cleanup/v2-merge-migration/20260427-161554/orphan-parent-repair.json | untracked | audit_output | V1 到 V2 数据迁移证据，保留用于解释当前 V2 数据来源。 | 归档在本轮审计产物下，不作为运行依赖。 |
| main | mobile/ | nested dirty | migration_active | 独立移动端仓库有迁移态修改，根仓只显示子仓 dirty。 | 在 mobile 仓内单独建账和提交，不从根仓混提交。 |

## Historical tracked generated debt

| Repo | Path pattern | State | Classification | Rationale | Recommended action |
| --- | --- | --- | --- | --- | --- |
| main | .playwright-cli/*.yml | tracked in HEAD (45 files) | delete_candidate | 浏览器/Playwright 录制产物，不应长期作为产品源代码。 | P1：专门提交删除，删除前确认没有脚本依赖。 |
| main | *.db / cloud_backend/*.db | tracked in HEAD (4 files) | delete_candidate | 本地/云端数据库快照，不应长期进入源码仓库。 | P1：专门提交删除或迁移到 fixture，删除前确认测试不依赖真实 DB。 |

## Mobile dirty paths

| Repo | Path | State | Classification | Rationale | Recommended action |
| --- | --- | --- | --- | --- | --- |
| mobile | .gitignore | modified | migration_active | 移动端迁移配套配置，需跟随移动端验证后单独提交。 | 保留在 mobile 迁移账，按主题小批提交。 |
| mobile | android/app/src/main/AndroidManifest.xml | modified | migration_active | 移动端 local-first / route-store 迁移态已修改文件，当前不直接判为废代码。 | 保留在 mobile 迁移账，按主题小批提交。 |
| mobile | app/(tabs)/calendar.tsx | modified | migration_active | Expo Router 真实入口或布局文件，route_bound，不能按孤儿代码删除。 | 保留在 mobile 迁移账，按主题小批提交。 |
| mobile | app/(tabs)/consult.tsx | modified | migration_active | Expo Router 真实入口或布局文件，route_bound，不能按孤儿代码删除。 | 保留在 mobile 迁移账，按主题小批提交。 |
| mobile | app/(tabs)/profile.tsx | modified | migration_active | Expo Router 真实入口或布局文件，route_bound，不能按孤儿代码删除。 | 保留在 mobile 迁移账，按主题小批提交。 |
| mobile | app/(tabs)/tasks.tsx | modified | migration_active | Expo Router 真实入口或布局文件，route_bound，不能按孤儿代码删除。 | 保留在 mobile 迁移账，按主题小批提交。 |
| mobile | app/_layout.tsx | modified | migration_active | Expo Router 真实入口或布局文件，route_bound，不能按孤儿代码删除。 | 保留在 mobile 迁移账，按主题小批提交。 |
| mobile | app/login.tsx | modified | migration_active | Expo Router 真实入口或布局文件，route_bound，不能按孤儿代码删除。 | 保留在 mobile 迁移账，按主题小批提交。 |
| mobile | components/CreateTask.tsx | modified | migration_active | 移动端 UI 组件迁移态，需由 route/component importer 证明后再收口。 | 保留在 mobile 迁移账，按主题小批提交。 |
| mobile | components/DateTimePicker.tsx | deleted | migration_active | 移动端 UI 组件迁移态，需由 route/component importer 证明后再收口。 | 保留在 mobile 迁移账，按主题小批提交。 |
| mobile | components/DateTimePickerSheet.tsx | modified | migration_active | 移动端 UI 组件迁移态，需由 route/component importer 证明后再收口。 | 保留在 mobile 迁移账，按主题小批提交。 |
| mobile | components/RecordNote.tsx | modified | migration_active | 移动端 UI 组件迁移态，需由 route/component importer 证明后再收口。 | 保留在 mobile 迁移账，按主题小批提交。 |
| mobile | components/SettingsAccount.tsx | modified | migration_active | 移动端 UI 组件迁移态，需由 route/component importer 证明后再收口。 | 保留在 mobile 迁移账，按主题小批提交。 |
| mobile | components/SmartInputSheet.tsx | modified | migration_active | 移动端 UI 组件迁移态，需由 route/component importer 证明后再收口。 | 保留在 mobile 迁移账，按主题小批提交。 |
| mobile | components/TaskDetail.tsx | modified | migration_active | 移动端 UI 组件迁移态，需由 route/component importer 证明后再收口。 | 保留在 mobile 迁移账，按主题小批提交。 |
| mobile | components/TaskReviewComposer.tsx | modified | migration_active | 移动端 UI 组件迁移态，需由 route/component importer 证明后再收口。 | 保留在 mobile 迁移账，按主题小批提交。 |
| mobile | lib/api.ts | modified | migration_active | 移动端 service/store/repository 迁移态，含 local-first 和 sync 边界代码。 | 保留在 mobile 迁移账，按主题小批提交。 |
| mobile | lib/auth-context.tsx | modified | migration_active | 移动端 service/store/repository 迁移态，含 local-first 和 sync 边界代码。 | 保留在 mobile 迁移账，按主题小批提交。 |
| mobile | lib/cache.ts | modified | migration_active | 移动端 service/store/repository 迁移态，含 local-first 和 sync 边界代码。 | 保留在 mobile 迁移账，按主题小批提交。 |
| mobile | lib/smart-input-queue.ts | modified | migration_active | 移动端 service/store/repository 迁移态，含 local-first 和 sync 边界代码。 | 保留在 mobile 迁移账，按主题小批提交。 |
| mobile | lib/types.ts | modified | migration_active | 移动端 service/store/repository 迁移态，含 local-first 和 sync 边界代码。 | 保留在 mobile 迁移账，按主题小批提交。 |
| mobile | package-lock.json | modified | migration_active | 移动端迁移配套配置，需跟随移动端验证后单独提交。 | 保留在 mobile 迁移账，按主题小批提交。 |
| mobile | package.json | modified | migration_active | 移动端迁移配套配置，需跟随移动端验证后单独提交。 | 保留在 mobile 迁移账，按主题小批提交。 |
| mobile | components/EventLineDrawer.tsx | untracked | migration_active | 新增移动端 UI 组件，需从 route/component importer 证明。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | components/FocusBar.tsx | untracked | migration_active | 新增移动端 UI 组件，需从 route/component importer 证明。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | components/TaskSyncBadge.tsx | untracked | migration_active | 新增移动端 UI 组件，需从 route/component importer 证明。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | components/UnderstandingCard.tsx | untracked | migration_active | 新增移动端 UI 组件，需从 route/component importer 证明。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | components/WeekSignalCard.tsx | untracked | migration_active | 新增移动端 UI 组件，需从 route/component importer 证明。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | components/WorkspaceLiteSheet.tsx | untracked | migration_active | 新增移动端 UI 组件，需从 route/component importer 证明。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | components/calendar-screen/CalendarDragLayer.tsx | untracked | migration_active | 新增 screen 分层组件，疑似替代旧大组件结构。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | components/calendar-screen/CalendarHeader.tsx | untracked | migration_active | 新增 screen 分层组件，疑似替代旧大组件结构。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | components/calendar-screen/CalendarModalCoordinator.tsx | untracked | migration_active | 新增 screen 分层组件，疑似替代旧大组件结构。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | components/calendar-screen/DayView.tsx | untracked | migration_active | 新增 screen 分层组件，疑似替代旧大组件结构。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | components/calendar-screen/MonthView.tsx | untracked | migration_active | 新增 screen 分层组件，疑似替代旧大组件结构。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | components/calendar-screen/WeekView.tsx | untracked | migration_active | 新增 screen 分层组件，疑似替代旧大组件结构。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | components/tasks-screen/DragCalendarOverlay.tsx | untracked | migration_active | 新增 screen 分层组件，疑似替代旧大组件结构。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | components/tasks-screen/InboxTaskList.tsx | untracked | migration_active | 新增 screen 分层组件，疑似替代旧大组件结构。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | components/tasks-screen/ScheduledTaskList.tsx | untracked | migration_active | 新增 screen 分层组件，疑似替代旧大组件结构。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | components/tasks-screen/SmartInputRecoveryController.tsx | untracked | migration_active | 新增 screen 分层组件，疑似替代旧大组件结构。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | components/tasks-screen/TaskModalCoordinator.tsx | untracked | migration_active | 新增 screen 分层组件，疑似替代旧大组件结构。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | components/tasks-screen/TasksFilterBar.tsx | untracked | migration_active | 新增 screen 分层组件，疑似替代旧大组件结构。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | components/tasks-screen/TasksHeader.tsx | untracked | migration_active | 新增 screen 分层组件，疑似替代旧大组件结构。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/__tests__/account-scope.test.mjs | untracked | migration_active | 新增 core test，当前 test:core 已通过；属于 test-guarded 迁移证据。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/__tests__/base-url.test.mjs | untracked | migration_active | 新增 core test，当前 test:core 已通过；属于 test-guarded 迁移证据。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/__tests__/boundary-cards.test.mjs | untracked | migration_active | 新增 core test，当前 test:core 已通过；属于 test-guarded 迁移证据。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/__tests__/calendar-repository-core.test.mjs | untracked | migration_active | 新增 core test，当前 test:core 已通过；属于 test-guarded 迁移证据。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/__tests__/consult-context-adapter.test.mjs | untracked | migration_active | 新增 core test，当前 test:core 已通过；属于 test-guarded 迁移证据。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/__tests__/consult-context.test.mjs | untracked | migration_active | 新增 core test，当前 test:core 已通过；属于 test-guarded 迁移证据。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/__tests__/consult-thread-context.test.mjs | untracked | migration_active | 新增 core test，当前 test:core 已通过；属于 test-guarded 迁移证据。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/__tests__/create-task-association.test.mjs | untracked | migration_active | 新增 core test，当前 test:core 已通过；属于 test-guarded 迁移证据。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/__tests__/current-focus-core.test.mjs | untracked | migration_active | 新增 core test，当前 test:core 已通过；属于 test-guarded 迁移证据。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/__tests__/date.test.mjs | untracked | migration_active | 新增 core test，当前 test:core 已通过；属于 test-guarded 迁移证据。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/__tests__/focus-selectors.test.mjs | untracked | migration_active | 新增 core test，当前 test:core 已通过；属于 test-guarded 迁移证据。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/__tests__/legacy-upload-pseudo-op-core.test.mjs | untracked | migration_active | 新增 core test，当前 test:core 已通过；属于 test-guarded 迁移证据。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/__tests__/legacy-upload-runner-core.test.mjs | untracked | migration_active | 新增 core test，当前 test:core 已通过；属于 test-guarded 迁移证据。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/__tests__/pending-op-policy.test.mjs | untracked | migration_active | 新增 core test，当前 test:core 已通过；属于 test-guarded 迁移证据。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/__tests__/record-note-flow-core.test.mjs | untracked | migration_active | 新增 core test，当前 test:core 已通过；属于 test-guarded 迁移证据。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/__tests__/runtime-controller.test.mjs | untracked | migration_active | 新增 core test，当前 test:core 已通过；属于 test-guarded 迁移证据。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/__tests__/scope-storage-core.test.mjs | untracked | migration_active | 新增 core test，当前 test:core 已通过；属于 test-guarded 迁移证据。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/__tests__/smart-input-queue-core.test.mjs | untracked | migration_active | 新增 core test，当前 test:core 已通过；属于 test-guarded 迁移证据。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/__tests__/smart-input-recovery.test.mjs | untracked | migration_active | 新增 core test，当前 test:core 已通过；属于 test-guarded 迁移证据。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/__tests__/sync-freeze-core.test.mjs | untracked | migration_active | 新增 core test，当前 test:core 已通过；属于 test-guarded 迁移证据。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/__tests__/task-board-store.test.mjs | untracked | migration_active | 新增 core test，当前 test:core 已通过；属于 test-guarded 迁移证据。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/__tests__/task-sync-policy.test.mjs | untracked | migration_active | 新增 core test，当前 test:core 已通过；属于 test-guarded 迁移证据。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/__tests__/task-sync-presentation.test.mjs | untracked | migration_active | 新增 core test，当前 test:core 已通过；属于 test-guarded 迁移证据。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/__tests__/task-understanding.test.mjs | untracked | migration_active | 新增 core test，当前 test:core 已通过；属于 test-guarded 迁移证据。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/__tests__/week-signal.test.mjs | untracked | migration_active | 新增 core test，当前 test:core 已通过；属于 test-guarded 迁移证据。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/account-scope.ts | untracked | migration_active | 移动端未跟踪迁移文件，不能仅凭未入库判断可删。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/base-url.ts | untracked | migration_active | 移动端未跟踪迁移文件，不能仅凭未入库判断可删。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/boundary-cards.ts | untracked | migration_active | 移动端未跟踪迁移文件，不能仅凭未入库判断可删。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/calendar-repository-core.ts | untracked | migration_active | 新增 local-first/store/repository/sync 迁移代码，当前归入 migration_active。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/calendar-repository.ts | untracked | migration_active | 新增 local-first/store/repository/sync 迁移代码，当前归入 migration_active。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/calendar-selectors.ts | untracked | migration_active | 移动端未跟踪迁移文件，不能仅凭未入库判断可删。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/client-intel-store.ts | untracked | migration_active | 新增 local-first/store/repository/sync 迁移代码，当前归入 migration_active。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/consult-context-adapter.ts | untracked | migration_active | 移动端未跟踪迁移文件，不能仅凭未入库判断可删。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/consult-context.ts | untracked | migration_active | 移动端未跟踪迁移文件，不能仅凭未入库判断可删。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/consult-thread-context.ts | untracked | migration_active | 移动端未跟踪迁移文件，不能仅凭未入库判断可删。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/create-task-association.ts | untracked | migration_active | 移动端未跟踪迁移文件，不能仅凭未入库判断可删。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/create-task-resources.ts | untracked | migration_active | 移动端未跟踪迁移文件，不能仅凭未入库判断可删。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/create-task-service.ts | untracked | migration_active | 新增 local-first/store/repository/sync 迁移代码，当前归入 migration_active。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/current-focus-core.ts | untracked | migration_active | 移动端未跟踪迁移文件，不能仅凭未入库判断可删。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/current-focus-store.ts | untracked | migration_active | 新增 local-first/store/repository/sync 迁移代码，当前归入 migration_active。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/date.ts | untracked | migration_active | 移动端未跟踪迁移文件，不能仅凭未入库判断可删。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/dev-log.ts | untracked | migration_active | 移动端未跟踪迁移文件，不能仅凭未入库判断可删。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/event-line-client-transfer.ts | untracked | migration_active | 移动端未跟踪迁移文件，不能仅凭未入库判断可删。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/focus-selectors.ts | untracked | migration_active | 移动端未跟踪迁移文件，不能仅凭未入库判断可删。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/legacy-upload-ops.ts | untracked | migration_active | 移动端未跟踪迁移文件，不能仅凭未入库判断可删。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/legacy-upload-pseudo-op-core.ts | untracked | migration_active | 移动端未跟踪迁移文件，不能仅凭未入库判断可删。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/legacy-upload-runner-core.ts | untracked | migration_active | 移动端未跟踪迁移文件，不能仅凭未入库判断可删。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/legacy-upload-runner.ts | untracked | migration_active | 移动端未跟踪迁移文件，不能仅凭未入库判断可删。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/local-db.ts | untracked | migration_active | 新增 local-first/store/repository/sync 迁移代码，当前归入 migration_active。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/local-ids.ts | untracked | migration_active | 新增 local-first/store/repository/sync 迁移代码，当前归入 migration_active。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/pending-op-policy.ts | untracked | migration_active | 移动端未跟踪迁移文件，不能仅凭未入库判断可删。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/record-note-flow-core.ts | untracked | migration_active | 移动端未跟踪迁移文件，不能仅凭未入库判断可删。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/record-note-service.ts | untracked | migration_active | 新增 local-first/store/repository/sync 迁移代码，当前归入 migration_active。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/runtime-controller.ts | untracked | migration_active | 新增 local-first/store/repository/sync 迁移代码，当前归入 migration_active。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/runtime-flags.ts | untracked | migration_active | 新增 local-first/store/repository/sync 迁移代码，当前归入 migration_active。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/runtime.ts | untracked | migration_active | 新增 local-first/store/repository/sync 迁移代码，当前归入 migration_active。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/scope-storage-core.ts | untracked | migration_active | 移动端未跟踪迁移文件，不能仅凭未入库判断可删。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/smart-input-queue-core.ts | untracked | migration_active | 移动端未跟踪迁移文件，不能仅凭未入库判断可删。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/smart-input-recovery.ts | untracked | migration_active | 移动端未跟踪迁移文件，不能仅凭未入库判断可删。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/sync-engine.ts | untracked | migration_active | 新增 local-first/store/repository/sync 迁移代码，当前归入 migration_active。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/sync-errors.ts | untracked | migration_active | 新增 local-first/store/repository/sync 迁移代码，当前归入 migration_active。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/sync-freeze-core.ts | untracked | migration_active | 新增 local-first/store/repository/sync 迁移代码，当前归入 migration_active。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/system-health.ts | untracked | migration_active | 移动端未跟踪迁移文件，不能仅凭未入库判断可删。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/task-board-store-core.ts | untracked | migration_active | 新增 local-first/store/repository/sync 迁移代码，当前归入 migration_active。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/task-board-store.ts | untracked | migration_active | 新增 local-first/store/repository/sync 迁移代码，当前归入 migration_active。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/task-detail-service.ts | untracked | migration_active | 新增 local-first/store/repository/sync 迁移代码，当前归入 migration_active。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/task-query-service.ts | untracked | migration_active | 新增 local-first/store/repository/sync 迁移代码，当前归入 migration_active。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/task-repository.ts | untracked | migration_active | 新增 local-first/store/repository/sync 迁移代码，当前归入 migration_active。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/task-review-service.ts | untracked | migration_active | 新增 local-first/store/repository/sync 迁移代码，当前归入 migration_active。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/task-sync-policy.ts | untracked | migration_active | 移动端未跟踪迁移文件，不能仅凭未入库判断可删。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/task-sync-presentation.ts | untracked | migration_active | 移动端未跟踪迁移文件，不能仅凭未入库判断可删。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/task-understanding.ts | untracked | migration_active | 移动端未跟踪迁移文件，不能仅凭未入库判断可删。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/use-render-count.ts | untracked | migration_active | 移动端未跟踪迁移文件，不能仅凭未入库判断可删。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | lib/week-signal.ts | untracked | migration_active | 移动端未跟踪迁移文件，不能仅凭未入库判断可删。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | scripts/android-rc-blocker-checklist.md | untracked | migration_active | 移动端迁移验证/RC 脚本或测试配置。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | scripts/check-no-direct-task-api-writes.mjs | untracked | migration_active | 移动端迁移验证/RC 脚本或测试配置。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | scripts/checkpoint-snapshot.md | untracked | migration_active | 移动端迁移验证/RC 脚本或测试配置。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | scripts/list-direct-api-usage.mjs | untracked | migration_active | 移动端迁移验证/RC 脚本或测试配置。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | scripts/mobile-blocker-ledger.md | untracked | migration_active | 移动端迁移验证/RC 脚本或测试配置。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | scripts/pr4a-dod.md | untracked | migration_active | 移动端迁移验证/RC 脚本或测试配置。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | scripts/round1-confirmation-blocker-flow.md | untracked | migration_active | 移动端迁移验证/RC 脚本或测试配置。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | scripts/run-android-rc-gates.sh | untracked | migration_active | 移动端迁移验证/RC 脚本或测试配置。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | scripts/run-mobile-core-tests.mjs | untracked | migration_active | 移动端迁移验证/RC 脚本或测试配置。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | scripts/run-mobile-stability-scan.sh | untracked | migration_active | 移动端迁移验证/RC 脚本或测试配置。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | scripts/verify-mobile-stability.md | untracked | migration_active | 移动端迁移验证/RC 脚本或测试配置。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | scripts/write-checkpoint-snapshot.mjs | untracked | migration_active | 移动端迁移验证/RC 脚本或测试配置。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
| mobile | tsconfig.tests.json | untracked | migration_active | 移动端迁移验证/RC 脚本或测试配置。 | 先按入口/调用/测试覆盖建账，再决定是否提交。 |
