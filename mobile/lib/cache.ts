/**
 * Local data cache — stale-while-revalidate pattern.
 *
 * Every cacheable GET endpoint is stored as JSON in AsyncStorage.
 * On page load:
 *   1. Cached data is returned instantly → UI appears immediately
 *   2. A background network fetch runs in parallel
 *   3. When fresh data arrives, the cache is updated and `setter` is called again
 *
 * On write operations (create/update/delete), the relevant cache key is
 * invalidated so the next load always hits the network first.
 */

import AsyncStorage from "@react-native-async-storage/async-storage";
import * as localDb from "./local-db";
import { buildScopedStorageKey, resolveScopedStorageNamespace } from "./scope-storage-core";

// ─── Prefix ──────────────────────────────────────
const PREFIX = "yiyu_cache_";

interface CacheEntry<T> {
  data: T;
  ts: number; // Date.now() when stored
}

// Cache is considered "stale" after 30 minutes, but still usable while
// network fetch is in flight.  After 24 hours the entry is discarded.
const STALE_MS = 30 * 60 * 1000;
const EXPIRED_MS = 24 * 60 * 60 * 1000;

// ─── Low-level helpers ───────────────────────────

function buildCacheStorageKey(
  key: string,
  scopeKey: string | null | undefined = localDb.getActiveAccountScopeKey(),
): string {
  return buildScopedStorageKey(PREFIX, key, scopeKey);
}

async function getCache<T>(key: string): Promise<{ data: T; stale: boolean } | null> {
  try {
    const raw = await AsyncStorage.getItem(buildCacheStorageKey(key));
    if (!raw) return null;
    const entry: CacheEntry<T> = JSON.parse(raw);
    const age = Date.now() - entry.ts;
    if (age > EXPIRED_MS) {
      // Too old – discard
      void AsyncStorage.removeItem(buildCacheStorageKey(key));
      return null;
    }
    return { data: entry.data, stale: age > STALE_MS };
  } catch {
    return null;
  }
}

async function setCache<T>(key: string, data: T): Promise<void> {
  try {
    const entry: CacheEntry<T> = { data, ts: Date.now() };
    await AsyncStorage.setItem(buildCacheStorageKey(key), JSON.stringify(entry));
  } catch {
    // Storage write failure is non-critical — ignore silently
  }
}

async function removeCache(key: string): Promise<void> {
  try {
    await AsyncStorage.removeItem(buildCacheStorageKey(key));
  } catch {}
}

// ─── Public API ──────────────────────────────────

/**
 * Core stale-while-revalidate loader.
 *
 * @param cacheKey   Unique key for this data set
 * @param fetcher    Async function that fetches fresh data from the network
 * @param setter     Callback to push data into React state (may be called twice:
 *                   once with cached data, once with fresh data)
 * @param options.forceNetwork  Skip reading cache (for pull-to-refresh)
 */
export async function loadWithCache<T>(
  cacheKey: string,
  fetcher: () => Promise<T>,
  setter: (data: T) => void,
  options?: { forceNetwork?: boolean },
): Promise<void> {
  const skipCache = options?.forceNetwork === true;

  let hasCachedData = false;

  // 1. Try serving from cache first (instant)
  if (!skipCache) {
    const cached = await getCache<T>(cacheKey);
    if (cached) {
      setter(cached.data);
      hasCachedData = true;
    }
  }

  // 2. Fetch fresh data from network
  try {
    const fresh = await fetcher();
    await setCache(cacheKey, fresh);
    setter(fresh);
  } catch (error) {
    // If we had cached data, swallow network errors silently —
    // the user is already seeing something useful.
    if (!hasCachedData) throw error;
  }
}

/**
 * Invalidate one or more cache keys.
 * Call after write operations (create, update, delete).
 */
export function invalidate(...keys: string[]): void {
  for (const key of keys) {
    void removeCache(key);
  }
}

export async function clearScope(
  scopeKey: string | null | undefined = localDb.getActiveAccountScopeKey(),
): Promise<void> {
  try {
    const scopePrefix = `${PREFIX}${resolveScopedStorageNamespace(scopeKey)}:`;
    const allKeys = await AsyncStorage.getAllKeys();
    const scopedKeys = allKeys.filter((item) => item.startsWith(scopePrefix));
    if (scopedKeys.length > 0) {
      await AsyncStorage.multiRemove(scopedKeys);
    }
  } catch {}
}

/**
 * Clear all cache entries (e.g. on logout).
 */
export async function clearAll(): Promise<void> {
  try {
    const allKeys = await AsyncStorage.getAllKeys();
    const cacheKeys = allKeys.filter((k) => k.startsWith(PREFIX));
    if (cacheKeys.length > 0) {
      await AsyncStorage.multiRemove(cacheKeys);
    }
  } catch {}
}

// ─── Well-known cache keys ───────────────────────
export const KEYS = {
  taskBoard: "taskBoard",
  taskLists: "taskLists",
  clients: "clients",
  eventLines: "eventLines",
  taskSettings: "taskSettings",
  userProfile: "userProfile",
  consultKnowledgeRequests: "consultKnowledgeRequests",
} as const;
