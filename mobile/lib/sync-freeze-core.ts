import type { SyncFreezeState } from "./types";

export function isSyncFreezeBlocked(state: SyncFreezeState): boolean {
  return state !== "ready" && state !== "paused_by_user";
}

export function isSyncFreezePaused(state: SyncFreezeState): boolean {
  return state === "paused_by_user";
}

export function describeSyncFreezeState(
  state: SyncFreezeState,
  detail: string | null,
): {
  summary: string;
  actionLabel: string | null;
  detail: string | null;
} {
  switch (state) {
    case "ready":
      return {
        summary: "同步正常",
        actionLabel: "暂停同步",
        detail: detail ?? null,
      };
    case "paused_by_user":
      return {
        summary: "同步已暂停",
        actionLabel: "恢复同步",
        detail: detail ?? null,
      };
    case "blocked_by_integrity":
      return {
        summary: "同步已冻结，需要处理本地数据完整性",
        actionLabel: null,
        detail: detail ?? "integrity_blocked",
      };
    case "blocked_by_scope_mismatch":
      return {
        summary: "同步已冻结，需要处理账号作用域切换",
        actionLabel: null,
        detail: detail ?? "scope_mismatch",
      };
    case "blocked_by_migration_failure":
      return {
        summary: "同步已冻结，需要处理本地迁移失败",
        actionLabel: null,
        detail: detail ?? "migration_failure",
      };
    case "blocked_by_auth":
      return {
        summary: "同步已冻结，需要重新登录",
        actionLabel: null,
        detail: detail ?? "auth_expired",
      };
    default:
      return {
        summary: "同步状态未知",
        actionLabel: null,
        detail,
      };
  }
}
