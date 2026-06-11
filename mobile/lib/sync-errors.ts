import { ApiError } from "./api";
import type { SyncReasonCode } from "./types";

export function mapSyncErrorToReasonCode(error: unknown): SyncReasonCode {
  if (error instanceof ApiError) {
    if (error.status === 401) return "auth_expired";
    if (error.status === 403) return "permission_denied";
    if (error.status === 409) return "version_conflict";
    if (error.status === 413 || error.status === 507) return "quota_exceeded";
    if (error.status === 400 || error.status === 422) return "validation_failed";
    return "server_rejected";
  }
  return "network_unavailable";
}
