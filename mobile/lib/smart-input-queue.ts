import AsyncStorage from "@react-native-async-storage/async-storage";
import * as FileSystem from "expo-file-system/legacy";
import * as api from "./api";
import * as localDb from "./local-db";
import {
  buildScopedDirectoryPath,
  buildScopedStorageKey,
  resolveScopedStorageNamespace,
} from "./scope-storage-core";
import { reconcileQueuedSmartInputItems } from "./smart-input-queue-core";
import type { SmartTaskDraftResponse } from "./types";

const SMART_INPUT_QUEUE_KEY_PREFIX = "yiyu_smart_input_audio_queue:";
const SMART_INPUT_QUEUE_BASE_DIR = `${FileSystem.documentDirectory ?? ""}smart-input-queue`;

interface QueuedSmartInputAudio {
  id: string;
  uri: string;
  name: string;
  type: string;
  referenceDate?: string | null;
  transcriptText?: string | null;
  createdAt: string;
}

type UploadableUriFile = {
  uri: string;
  name: string;
  type: string;
};

const flushInFlightByScope = new Map<string, Promise<SmartTaskDraftResponse[]>>();

function getCurrentScopeKey(): string | null {
  return localDb.getActiveAccountScopeKey();
}

function buildSmartInputQueueStorageKey(
  scopeKey: string | null | undefined = getCurrentScopeKey(),
): string {
  return buildScopedStorageKey(SMART_INPUT_QUEUE_KEY_PREFIX, "items", scopeKey);
}

function buildSmartInputQueueDirectory(
  scopeKey: string | null | undefined = getCurrentScopeKey(),
): string {
  return buildScopedDirectoryPath(SMART_INPUT_QUEUE_BASE_DIR, scopeKey);
}

export function isRetriableSmartInputQueueError(error: unknown): boolean {
  if (error instanceof api.ApiError) {
    return error.status >= 500 || error.status === 408 || error.status === 429;
  }
  if (error instanceof Error) {
    const lowered = error.message.toLowerCase();
    return (
      lowered.includes("network request failed") ||
      lowered.includes("network error") ||
      lowered.includes("timed out") ||
      lowered.includes("fetch")
    );
  }
  return true;
}

export function explainSmartInputQueueError(error: unknown): string {
  if (error instanceof api.ApiError) {
    try {
      const parsed = JSON.parse(error.body);
      if (typeof parsed?.detail === "string" && parsed.detail.trim()) {
        return parsed.detail.trim();
      }
    } catch {}
    return error.body || "暂存语音补传失败。";
  }
  return error instanceof Error ? error.message : "暂存语音补传失败。";
}

function normalizeUploadableFile(file: api.UploadableFile): UploadableUriFile | null {
  if (typeof File !== "undefined" && file instanceof File) {
    return null;
  }
  if (!file || typeof file !== "object" || !("uri" in file)) {
    return null;
  }
  if (!file.uri) {
    return null;
  }
  return {
    uri: file.uri,
    name: file.name || `smart-input-${Date.now()}.m4a`,
    type: file.type || "audio/m4a",
  };
}

function inferExtension(file: UploadableUriFile): string {
  const fromName = file.name.split(".").pop()?.trim().toLowerCase();
  if (fromName) {
    return fromName;
  }
  const cleanUri = file.uri.split("?")[0].toLowerCase();
  const fromUri = cleanUri.split(".").pop()?.trim();
  if (fromUri) {
    return fromUri;
  }
  if (file.type.includes("wav")) return "wav";
  if (file.type.includes("mpeg") || file.type.includes("mp3")) return "mp3";
  if (file.type.includes("ogg")) return "ogg";
  if (file.type.includes("aac")) return "aac";
  return "m4a";
}

async function ensureQueueDirectory(scopeKey: string | null | undefined): Promise<void> {
  if (!FileSystem.documentDirectory) {
    throw new Error("当前设备不支持离线暂存。");
  }
  await FileSystem.makeDirectoryAsync(buildSmartInputQueueDirectory(scopeKey), { intermediates: true });
}

async function persistAudioFile(
  itemId: string,
  file: UploadableUriFile,
  scopeKey: string | null | undefined,
): Promise<UploadableUriFile> {
  await ensureQueueDirectory(scopeKey);
  const extension = inferExtension(file);
  const destinationUri = `${buildSmartInputQueueDirectory(scopeKey)}${itemId}.${extension}`;
  if (file.uri !== destinationUri) {
    await FileSystem.copyAsync({ from: file.uri, to: destinationUri });
  }
  return {
    uri: destinationUri,
    name: `smart-input-${itemId}.${extension}`,
    type: file.type,
  };
}

async function removePersistedAudio(uri: string): Promise<void> {
  try {
    await FileSystem.deleteAsync(uri, { idempotent: true });
  } catch {}
}

async function loadQueue(
  scopeKey: string | null | undefined = getCurrentScopeKey(),
): Promise<QueuedSmartInputAudio[]> {
  try {
    const raw = await AsyncStorage.getItem(buildSmartInputQueueStorageKey(scopeKey));
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed.filter((item): item is QueuedSmartInputAudio => {
      return Boolean(item && typeof item.id === "string" && typeof item.uri === "string");
    });
  } catch {
    return [];
  }
}

async function saveQueue(
  items: QueuedSmartInputAudio[],
  scopeKey: string | null | undefined = getCurrentScopeKey(),
): Promise<void> {
  await AsyncStorage.setItem(buildSmartInputQueueStorageKey(scopeKey), JSON.stringify(items));
}

export async function queueSmartInputAudio(
  file: api.UploadableFile,
  meta: { referenceDate?: string | null; transcriptText?: string | null } = {},
): Promise<void> {
  const scopeKey = getCurrentScopeKey();
  const normalized = normalizeUploadableFile(file);
  if (!normalized) {
    throw new Error("当前环境不支持暂存这条语音。");
  }
  const itemId = `smart_audio_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
  const persistedFile = await persistAudioFile(itemId, normalized, scopeKey);
  const queue = await loadQueue(scopeKey);
  queue.unshift({
    id: itemId,
    uri: persistedFile.uri,
    name: persistedFile.name,
    type: persistedFile.type,
    referenceDate: meta.referenceDate ?? null,
    transcriptText: meta.transcriptText?.trim() || null,
    createdAt: new Date().toISOString(),
  });
  await saveQueue(queue, scopeKey);
}

export async function getQueuedSmartInputCount(): Promise<number> {
  const queue = await loadQueue();
  return queue.length;
}

export async function clearSmartInputQueue(): Promise<number> {
  const scopeKey = getCurrentScopeKey();
  const queue = await loadQueue(scopeKey);
  for (const item of queue) {
    await removePersistedAudio(item.uri);
  }
  await saveQueue([], scopeKey);
  return queue.length;
}

export async function clearAllSmartInputQueueScopes(): Promise<void> {
  flushInFlightByScope.clear();
  const allKeys = await AsyncStorage.getAllKeys();
  const queueKeys = allKeys.filter((item) => item.startsWith(SMART_INPUT_QUEUE_KEY_PREFIX));
  if (queueKeys.length > 0) {
    await AsyncStorage.multiRemove(queueKeys);
  }
  if (FileSystem.documentDirectory) {
    await FileSystem.deleteAsync(`${SMART_INPUT_QUEUE_BASE_DIR}/`, { idempotent: true });
  }
}

export async function flushQueuedSmartInputDrafts(limit: number = 1): Promise<SmartTaskDraftResponse[]> {
  const scopeKey = getCurrentScopeKey();
  const scopeNamespace = resolveScopedStorageNamespace(scopeKey);
  const inflight = flushInFlightByScope.get(scopeNamespace);
  if (inflight) {
    return inflight;
  }

  const nextFlush = (async () => {
    const queue = await loadQueue(scopeKey);
    if (!queue.length) {
      return [];
    }

    const recovered: SmartTaskDraftResponse[] = [];
    const removeIds = new Set<string>();

    for (const item of queue) {
      if (recovered.length >= limit) {
        continue;
      }

      try {
        const info = await FileSystem.getInfoAsync(item.uri);
        if (!info.exists) {
          removeIds.add(item.id);
          continue;
        }

        const response = await api.generateSmartTaskDraft({
          transcriptText: item.transcriptText ?? undefined,
          audioFile: {
            uri: item.uri,
            name: item.name,
            type: item.type,
          },
          referenceDate: item.referenceDate ?? undefined,
        });
        recovered.push(response);
        removeIds.add(item.id);
        await removePersistedAudio(item.uri);
      } catch (error) {
        if (!isRetriableSmartInputQueueError(error)) {
          // 不可重试(文件损坏 / 失效、4xx 等)→ 丢弃这一条坏项并继续，绝不 throw 中断整批：
          // 否则单条坏项会永久堵死整个补传队列、它后面的暂存语音也再没机会上传。
          console.warn("[smart-input-queue] 丢弃不可重试的暂存项", {
            id: item.id,
            error: error instanceof Error ? error.message : String(error),
          });
          removeIds.add(item.id);
          await removePersistedAudio(item.uri).catch(() => undefined);
          continue;
        }
        // 可重试(网络 / 5xx / 超时)→ 保留该项，下次再试。
      }
    }

    const currentQueue = await loadQueue(scopeKey);
    await saveQueue(reconcileQueuedSmartInputItems(currentQueue, removeIds), scopeKey);
    return recovered;
  })();
  flushInFlightByScope.set(scopeNamespace, nextFlush);

  try {
    return await nextFlush;
  } finally {
    flushInFlightByScope.delete(scopeNamespace);
  }
}
