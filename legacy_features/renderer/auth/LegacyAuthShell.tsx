/*
 * Legacy archive: old AuthShell / department-invite registration flow
 * Preserved on 2026-03-30 after the formal entry moved to:
 *   系统设置 -> 账号与同步
 *
 * Why archived:
 * - It enforced "部门邀请码 -> 待审核 -> bootstrap 管理员" as the primary login path.
 * - The new product direction is "本地模式直入，云端注册/登录可选开启".
 *
 * What used to happen:
 * - login tab: email + password + rememberMe
 * - register step 1: parse a department invite code
 * - register step 2: force department-bound signup with job title
 * - success path: pending approval, then manual admin approval
 *
 * Original live source was removed from src/renderer/App.tsx to avoid
 * future Codex sessions mistaking it for the active auth flow.
 *
 * The exact legacy logic kept here for reference:
 *
 * const createEmptyRegisterForm = (email = '') => ({
 *   email,
 *   fullName: '',
 *   password: '',
 *   departmentId: '',
 *   jobTitle: '',
 *   managerName: '',
 *   currentFocus: '',
 *   isDepartmentLead: false,
 * });
 *
 * States:
 * - mode: 'login' | 'register'
 * - registerStep: 1 | 2
 * - departmentInviteCode
 * - rememberMe
 * - submitting / message
 *
 * Legacy behaviors:
 * - parseDepartmentInviteCode(departmentInviteCode)
 * - buildDepartmentInviteCode(department.id)
 * - register(form) -> "你的账号已提交，正在等待管理员审核。"
 * - login({ email, password, rememberMe }) -> setAuthState(response); loadAll()
 *
 * Old copy:
 * - "普通成员请使用部门邀请码注册；组织管理员首次进入仍使用服务端 bootstrap 凭据登录。"
 * - "邮箱注册后自动进入待审核状态"
 * - "管理员可审批、驳回、停用并设置角色"
 *
 * If the team later wants to revive this legacy flow for a compatibility
 * build, recover it from git history before 2026-03-30 or rebuild from this
 * note instead of wiring it back into the default desktop startup path.
 */

export const LEGACY_AUTH_SHELL_ARCHIVED = true;
