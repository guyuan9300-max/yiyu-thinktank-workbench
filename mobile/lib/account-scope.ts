import type { SessionUser } from "./types";

export const NO_ACCOUNT_SCOPE_KEY = "no-org:no-user";

export function buildAccountScopeKey(
  user: Pick<SessionUser, "id" | "organizationId"> | null | undefined,
): string {
  const organizationId = user?.organizationId?.trim() || "no-org";
  const userId = user?.id?.trim() || "no-user";
  return `${organizationId}:${userId}`;
}

export function normalizeAccountScopeKey(value: string | null | undefined): string | null {
  const trimmed = value?.trim();
  if (!trimmed) {
    return null;
  }
  const [organizationId, userId] = trimmed.split(":");
  if (!organizationId || !userId) {
    return null;
  }
  return `${organizationId}:${userId}`;
}

export function redactAccountScopeKey(value: string | null | undefined): string {
  const normalized = normalizeAccountScopeKey(value) ?? NO_ACCOUNT_SCOPE_KEY;
  const [organizationId, userId] = normalized.split(":");
  return `${organizationId}:${userId.slice(0, 4)}***`;
}
