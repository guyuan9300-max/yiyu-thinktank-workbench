import type { SyncReasonCode, TaskRecord } from "./types";

export type TaskSyncIndicatorTone = "info" | "warning" | "danger";

export interface TaskSyncIndicatorModel {
  readonly label: string;
  readonly detail: string | null;
  readonly tone: TaskSyncIndicatorTone;
}

export function formatTaskSyncReasonCode(reasonCode: SyncReasonCode | string | null | undefined): string {
  switch (reasonCode) {
    case "network_unavailable":
      return "网络不可用";
    case "auth_expired":
      return "登录已过期";
    case "permission_denied":
      return "没有权限";
    case "validation_failed":
      return "数据校验失败";
    case "version_conflict":
      return "服务器版本冲突";
    case "file_missing":
      return "原件缺失";
    case "quota_exceeded":
      return "存储空间不足";
    case "server_rejected":
      return "服务器拒绝";
    case "thermal_blocked":
      return "设备资源受限";
    case "model_unavailable":
      return "模型暂不可用";
    default:
      return "请稍后再试";
  }
}

export function buildTaskSyncIndicator(task: Pick<TaskRecord, "remoteState" | "syncReasonCode">): TaskSyncIndicatorModel | null {
  if (task.syncReasonCode === "version_conflict") {
    return {
      label: "冲突",
      detail: formatTaskSyncReasonCode(task.syncReasonCode),
      tone: "danger",
    };
  }
  if (task.remoteState === "needs_attention") {
    return {
      // 与"我的→系统健康"统一口径：needs_attention 对外统称"待处理"（仍保留 danger 红色 + 失败原因，
      // 让用户知道它需要手动点一下才会重试，不会自己好）。
      label: "待处理",
      detail: formatTaskSyncReasonCode(task.syncReasonCode),
      tone: "danger",
    };
  }
  if (task.remoteState === "queued") {
    return {
      label: "待同步",
      detail: "本地已保存，等待后台同步",
      tone: "info",
    };
  }
  if (task.remoteState === "syncing" || task.remoteState === "processing") {
    return {
      label: "处理中",
      detail: "后台正在处理本地修改",
      tone: "warning",
    };
  }
  return null;
}
