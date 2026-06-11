import { NO_ACCOUNT_SCOPE_KEY, normalizeAccountScopeKey } from "./account-scope";

export function resolveScopedStorageNamespace(scopeKey: string | null | undefined): string {
  return encodeURIComponent(normalizeAccountScopeKey(scopeKey) ?? NO_ACCOUNT_SCOPE_KEY);
}

export function buildScopedStorageKey(
  prefix: string,
  key: string,
  scopeKey: string | null | undefined,
): string {
  return `${prefix}${resolveScopedStorageNamespace(scopeKey)}:${key}`;
}

export function buildScopedDirectoryPath(
  baseDirectory: string,
  scopeKey: string | null | undefined,
): string {
  const normalizedBase = baseDirectory.endsWith("/") ? baseDirectory : `${baseDirectory}/`;
  return `${normalizedBase}${resolveScopedStorageNamespace(scopeKey)}/`;
}
