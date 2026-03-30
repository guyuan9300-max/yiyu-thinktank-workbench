# 旧功能归档

这个目录用于保存“暂不删除、但已经不接到当前主界面或主链路”的旧功能代码。

2026-03-30 已迁入：
- `renderer/components/workbench/PlatformDnaPanel.tsx`
- `renderer/components/workbench/platformDnaProfiles.ts`
- `renderer/components/workbench/DiagnosisEnginePanel.tsx`
- `renderer/components/tasks/ExecutiveReviewPanel.tsx`
- `renderer/components/settings/LegacyMigrationDemoPanel.tsx`
- `renderer/lib/legacySettingsApi.ts`
- `renderer/auth/LegacyAuthShell.tsx`

迁入原则：
- 当前主界面没有实际 import / 接线
- 先归档，后续如果确认彻底不再需要，再统一删除
- 归档代码尽量保持可读，不作为当前构建入口的一部分

暂未迁入、因为当前仍在主流程中运行的旧链路：
- bootstrap 管理员 / 内部种子账号
- 组织搭建中心里仍在使用的部门邀请码生成与分享逻辑
- 演示数据与旧数据导入的后端接口

以后如果用户明确说“旧功能先不删”，默认继续迁入这个目录，而不是直接删除。
