/**
 * sync-engine.ts — 双数据库后台同步引擎
 *
 * 核心架构：
 *   ┌────────────┐     ┌──────────────┐     ┌────────────┐
 *   │  UI 层     │ ──▶ │  本地 SQLite  │ ──▶ │  云端 API   │
 *   │ (即时响应)  │ ◀── │  (真实数据源)  │ ◀── │  (远程数据源) │
 *   └────────────┘     └──────────────┘     └────────────┘
 *
 * 数据流：
 *   1. 读取: UI 始终从 SQLite 读取 → 毫秒级响应
 *   2. 写入: 先写 SQLite（乐观更新） → 排入 pending_ops 队列
 *   3. 同步: 后台双向同步
 *      - 上行：将 pending_ops 中的操作推送到云端
 *      - 下行：从云端拉取最新数据写入 SQLite
 *   4. 后台: App 进入后台后通过 BackgroundFetch 定期同步
 *
 * 冲突策略: 服务端权威 (server-wins)
 *   - 上行推送失败时保留本地版本，下次重试
 *   - 下行拉取的数据覆盖本地已同步的记录
 *   - 本地未同步的修改不会被覆盖
 */

import { AppState, type AppStateStatus } from "react-native";
import * as BackgroundFetch from "expo-background-fetch";
import * as TaskManager from "expo-task-manager";
import * as api from "./api";
import { processQueuedLegacyUploadPseudoOps } from "./legacy-upload-runner";
import * as localDb from "./local-db";
import { devLog } from "./dev-log";
import { mapSyncErrorToReasonCode } from "./sync-errors";
import { isSyncFreezeBlocked, isSyncFreezePaused } from "./sync-freeze-core";
import { cancelTaskReminder, rescheduleAllReminders, scheduleTaskReminder } from "./task-reminder-scheduler";
import {
  completeTaskWithReviewLocalFirst as commitCompleteTaskWithReviewLocalFirst,
  createTaskLocalFirst as commitCreateTaskLocalFirst,
  deleteTaskLocalFirst as commitDeleteTaskLocalFirst,
  updateTaskLocalFirst as commitUpdateTaskLocalFirst,
} from "./task-repository";
import { tagsToStringArray, type MutationReceipt, type SyncFreezeState, type TaskRecord } from "./types";

// ─── Constants ──────────────────────────────────

const BACKGROUND_SYNC_TASK = "YIYU_BACKGROUND_SYNC";
const SYNC_INTERVAL_MS = 2 * 60 * 1000; // 前台自动同步间隔：2分钟
const MAX_OP_RETRIES = 5;

// ─── Sync State ─────────────────────────────────

type SyncStatus = "idle" | "syncing" | "error";
type SyncListener = (status: SyncStatus, lastSyncTime: string | null) => void;
export interface SyncEventLogRecord {
  id: string;
  level: "info" | "error";
  event: string;
  createdAt: string;
  payload?: Record<string, unknown>;
}

let _syncStatus: SyncStatus = "idle";
let _lastSyncTime: string | null = null;
let _listeners: Set<SyncListener> = new Set();
let _syncTimer: ReturnType<typeof setInterval> | null = null;
let _appStateSubscription: any = null;
let _isSyncing = false;
// 尾随合并标志:同步进行期间被 _isSyncing 挡掉的 performSync 请求会置位它，
// 当前轮结束后补跑一轮——否则慢网下"同步进行中的那段时间里用户改的内容"
// 要等下一个定时器 / 前后台切换才上行。
let _syncRerunRequested = false;
let _isStarted = false;
let _startPromise: Promise<void> | null = null;
let _backgroundSyncRegistered = false;
let _taskBoardFetchCount = 0;
let _syncFreezeState: SyncFreezeState = "ready";
let _syncFreezeDetail: string | null = null;
let _syncEventCounter = 0;
let _recentSyncEvents: SyncEventLogRecord[] = [];
// 每次 stopSyncEngine 自增，让此前已经在 await 中飞行的 performSync 在恢复执行
// 时识别出"我属于旧账号/旧引擎实例"，跳过对本地 DB 的写入。否则用户快速切账号
// 时旧的 pullFromCloud 会把旧账号数据写进新账号的 SQLite。
let _syncGeneration = 0;

function pushSyncEvent(
  level: "info" | "error",
  event: string,
  payload?: Record<string, unknown>,
): void {
  _syncEventCounter += 1;
  _recentSyncEvents = [
    {
      id: `sync_evt_${_syncEventCounter}`,
      level,
      event,
      createdAt: new Date().toISOString(),
      payload,
    },
    ..._recentSyncEvents,
  ].slice(0, 50);
}

function setSyncFreezeState(
  state: SyncFreezeState,
  detail: string | null = null,
): void {
  const changed = _syncFreezeState !== state || _syncFreezeDetail !== detail;
  _syncFreezeState = state;
  _syncFreezeDetail = detail;
  if (changed) {
    pushSyncEvent("info", "freeze_state_changed", {
      state,
      detail,
    });
  }
  notifyListeners();
}

function notifyListeners(): void {
  for (const listener of _listeners) {
    try {
      listener(_syncStatus, _lastSyncTime);
    } catch {}
  }
}

function setSyncStatus(status: SyncStatus): void {
  _syncStatus = status;
  notifyListeners();
}

// ─── Data Change Listeners ──────────────────────

type DataChangeListener = () => void;
let _dataChangeListeners: Set<DataChangeListener> = new Set();

function notifyDataChanged(): void {
  for (const listener of _dataChangeListeners) {
    try {
      listener();
    } catch {}
  }
}

/**
 * 订阅数据变化通知（同步完成后触发）
 * 返回取消订阅函数
 */
export function onDataChanged(listener: DataChangeListener): () => void {
  _dataChangeListeners.add(listener);
  return () => {
    _dataChangeListeners.delete(listener);
  };
}

export function emitDataChanged(): void {
  notifyDataChanged();
}

// ─── Public API ─────────────────────────────────

/**
 * 订阅同步状态变化
 */
export function onSyncStatusChange(listener: SyncListener): () => void {
  _listeners.add(listener);
  // 立即通知当前状态
  listener(_syncStatus, _lastSyncTime);
  return () => {
    _listeners.delete(listener);
  };
}

/**
 * 获取当前同步状态
 */
export function getSyncStatus(): { status: SyncStatus; lastSyncTime: string | null } {
  return { status: _syncStatus, lastSyncTime: _lastSyncTime };
}

export function getRecentSyncEvents(limit = 20): SyncEventLogRecord[] {
  return _recentSyncEvents.slice(0, limit);
}

export function getSyncControlState(): {
  freezeState: SyncFreezeState;
  isPaused: boolean;
  blockedReason: string | null;
  detail: string | null;
} {
  return {
    freezeState: _syncFreezeState,
    isPaused: isSyncFreezePaused(_syncFreezeState),
    blockedReason: isSyncFreezeBlocked(_syncFreezeState) ? _syncFreezeDetail : null,
    detail: _syncFreezeDetail,
  };
}

export function isSyncPaused(): boolean {
  return isSyncFreezePaused(_syncFreezeState);
}

export function setSyncPaused(paused: boolean): void {
  if (!paused && isSyncFreezeBlocked(_syncFreezeState)) {
    devLog("sync", "resume.skipped_blocked", { blockedReason: _syncFreezeDetail });
    return;
  }
  if (paused) {
    stopForegroundSync();
    if (_syncStatus === "syncing") {
      setSyncStatus("idle");
    }
    setSyncFreezeState("paused_by_user");
    devLog("sync", "paused");
    pushSyncEvent("info", "paused_by_user");
    return;
  }
  setSyncFreezeState("ready");
  devLog("sync", "resumed");
  pushSyncEvent("info", "resumed_by_user");
  if (_isStarted) {
    startForegroundSync();
    void performSync();
  }
}

export function setSyncFreezeStateForRuntime(
  state: SyncFreezeState,
  detail: string | null = null,
): void {
  if (state === "paused_by_user") {
    setSyncPaused(true);
    return;
  }
  stopForegroundSync();
  if (_syncStatus === "syncing") {
    setSyncStatus("idle");
  }
  setSyncFreezeState(state, detail);
  pushSyncEvent("info", "runtime_freeze_applied", { state, detail });
  devLog("sync", "freeze_state.runtime", { state, detail });
}

/**
 * 初始化同步引擎
 * 应在 App 启动、用户登录成功后调用
 */
export async function startSyncEngine(): Promise<void> {
  if (_isStarted) {
    devLog("sync", "start.skipped_already_started");
    return;
  }
  if (_startPromise) {
    devLog("sync", "start.reused_inflight");
    await _startPromise;
    return;
  }

  _startPromise = (async () => {
    localDb.initDatabase();
    const integrity = localDb.getDataIntegrityState();
    setSyncFreezeState(
      integrity.integrityStatus === "blocked" ? "blocked_by_integrity" : "ready",
      integrity.integrityReason,
    );
    _lastSyncTime = localDb.getSyncMeta("tasks_last_sync");

    startForegroundSync();

    if (!_appStateSubscription) {
      _appStateSubscription = AppState.addEventListener("change", handleAppStateChange);
    }

    await registerBackgroundSync();
    _isStarted = true;
    pushSyncEvent("info", "sync_engine_started", {
      lastSyncTime: _lastSyncTime,
      freezeState: _syncFreezeState,
      blockedReason: _syncFreezeDetail,
    });
    devLog("sync", "start.completed", {
      lastSyncTime: _lastSyncTime,
      blockedReason: _syncFreezeDetail,
      freezeState: _syncFreezeState,
    });
    if (!isSyncFreezeBlocked(_syncFreezeState)) {
      void performSync();
    }
  })().finally(() => {
    _startPromise = null;
  });

  await _startPromise;
}

/**
 * 停止同步引擎（登出时调用）
 */
export async function stopSyncEngine(): Promise<void> {
  if (_startPromise) {
    await _startPromise.catch(() => {});
  }

  stopForegroundSync();

  if (_appStateSubscription) {
    _appStateSubscription.remove();
    _appStateSubscription = null;
  }

  _isStarted = false;
  _isSyncing = false;
  _syncRerunRequested = false;
  _syncGeneration += 1;
  setSyncFreezeState("ready");
  _syncStatus = "idle";
  _lastSyncTime = null;
  pushSyncEvent("info", "sync_engine_stopped");
  notifyListeners();

  if (_backgroundSyncRegistered) {
    try {
      await BackgroundFetch.unregisterTaskAsync(BACKGROUND_SYNC_TASK);
    } catch {}
    _backgroundSyncRegistered = false;
  }

  devLog("sync", "stop.completed");
}

/**
 * 手动触发一次完整同步（下拉刷新时调用）
 */
export async function triggerSync(): Promise<void> {
  if (isSyncFreezeBlocked(_syncFreezeState)) {
    devLog("sync", "trigger.skipped_blocked", { blockedReason: _syncFreezeDetail });
    pushSyncEvent("error", "trigger_skipped_blocked", { blockedReason: _syncFreezeDetail });
    return;
  }
  if (isSyncFreezePaused(_syncFreezeState)) {
    devLog("sync", "trigger.skipped_paused");
    pushSyncEvent("info", "trigger_skipped_paused");
    return;
  }
  if (!_isStarted) {
    await startSyncEngine();
  }
  await performSync();
}

// ─── Core Sync Logic ────────────────────────────

async function performSync(): Promise<void> {
  if (isSyncFreezeBlocked(_syncFreezeState)) return;
  if (isSyncFreezePaused(_syncFreezeState)) return;
  if (_isSyncing) {
    // 已有一轮在跑：记下"结束后需要再跑一轮"，不要丢掉这次请求。
    _syncRerunRequested = true;
    return;
  }
  _isSyncing = true;
  const myGeneration = _syncGeneration;
  const isAborted = (): boolean => _syncGeneration !== myGeneration;
  setSyncStatus("syncing");
  devLog("sync", "cycle.started");
  pushSyncEvent("info", "cycle_started");

  try {
    // 1. 上行：推送本地待上传操作
    await pushPendingOps(isAborted);
    if (isAborted()) {
      devLog("sync", "cycle.aborted_after_push");
      pushSyncEvent("info", "cycle_aborted_after_push");
      return;
    }

    // 2. 处理 legacy transfer lane 中已排队的附件/录音上传
    const legacyTransfer = await processQueuedLegacyUploadPseudoOps();
    if (isAborted()) {
      devLog("sync", "cycle.aborted_after_legacy_transfer");
      pushSyncEvent("info", "cycle_aborted_after_legacy_transfer");
      return;
    }
    if (legacyTransfer.attempted > 0) {
      pushSyncEvent("info", "legacy_transfer_processed", {
        attempted: legacyTransfer.attempted,
        completed: legacyTransfer.completed,
        stoppedByAuth: legacyTransfer.stoppedByAuth,
        stoppedByNetwork: legacyTransfer.stoppedByNetwork,
      });
      devLog("sync", "legacy_transfer.processed", {
        attempted: legacyTransfer.attempted,
        completed: legacyTransfer.completed,
        stoppedByAuth: legacyTransfer.stoppedByAuth,
        stoppedByNetwork: legacyTransfer.stoppedByNetwork,
      });
    }
    if (legacyTransfer.stoppedByAuth) {
      setSyncFreezeState("blocked_by_auth", "auth_expired");
      pushSyncEvent("error", "legacy_transfer_auth_blocked", {
        attempted: legacyTransfer.attempted,
        completed: legacyTransfer.completed,
        stoppedByAuth: legacyTransfer.stoppedByAuth,
        stoppedByNetwork: legacyTransfer.stoppedByNetwork,
      });
      throw new Error("Legacy transfer upload blocked by expired auth.");
    }

    // 3. 下行：从云端拉取最新数据
    await pullFromCloud(isAborted);
    if (isAborted()) {
      devLog("sync", "cycle.aborted_after_pull");
      pushSyncEvent("info", "cycle_aborted_after_pull");
      return;
    }

    _lastSyncTime = new Date().toISOString();
    setSyncStatus("idle");
    pushSyncEvent("info", "cycle_succeeded", { lastSyncTime: _lastSyncTime });
    devLog("sync", "cycle.succeeded", { lastSyncTime: _lastSyncTime });

    // 通知 UI 数据已更新
    notifyDataChanged();
  } catch (error) {
    if (isAborted()) {
      // 引擎已被 stop / 重启，吃掉这条本应作废的错误，不要把旧实例的状态写到全局。
      devLog("sync", "cycle.error_after_abort", {
        error: error instanceof Error ? error.message : String(error),
      });
      return;
    }
    console.warn("[SyncEngine] Sync failed:", error);
    devLog("sync", "cycle.failed", {
      error: error instanceof Error ? error.message : String(error),
    });
    pushSyncEvent("error", "cycle_failed", {
      error: error instanceof Error ? error.message : String(error),
    });
    setSyncStatus("error");

    // 即使同步失败，如果有部分数据更新也通知
    notifyDataChanged();
  } finally {
    // 旧引擎实例退出时，不要去碰 _isSyncing —— 新的 performSync 此时可能
    // 已经接管并把它设回 true。stopSyncEngine 自己负责重置该标志。
    if (!isAborted()) {
      _isSyncing = false;
      // 尾随合并:同步期间若有新的本地写入被挡掉，补跑一轮把它们带上去。
      if (_syncRerunRequested) {
        _syncRerunRequested = false;
        void performSync();
      }
    }
  }
}

/**
 * 上行推送：将本地待上传的操作发送到云端
 */
async function pushPendingOps(isAborted: () => boolean = () => false): Promise<void> {
  const ops = localDb.getPendingOps();
  if (ops.length === 0) return;

  for (const op of ops) {
    if (isAborted()) {
      // 引擎已被 stop / 切账号，停止把旧账号的 op 推到云端，避免泄漏。
      return;
    }
    if (op.retryCount >= MAX_OP_RETRIES) {
      localDb.markOpFailed(op.id, op.lastError ?? "Max retries exceeded", op.reasonCode ?? "server_rejected", "needs_attention");
      if (op.entityType === "task") {
        localDb.setTaskRemoteState(op.entityId, "needs_attention", op.reasonCode ?? "server_rejected");
      }
      continue;
    }

    try {
      localDb.markOpSyncing(op.id);
      if (op.entityType === "task") {
        localDb.setTaskRemoteState(op.entityId, "syncing");
      }
      let payload: any = {};
      if (op.payload) {
        try {
          payload = JSON.parse(op.payload);
        } catch (parseError) {
          // op.payload 损坏（磁盘满 / 历史迁移残留）。不要让 SyntaxError 冒泡
          // 把整个 pushPendingOps 同步循环干掉——把这一条 op 标 needs_attention
          // 给上层显示，然后跳过推送，继续处理后续 op。
          const parseMessage =
            parseError instanceof Error ? parseError.message : String(parseError);
          localDb.markOpFailed(
            op.id,
            `corrupt_payload_json: ${parseMessage}`,
            "validation_failed",
            "needs_attention",
          );
          if (op.entityType === "task") {
            localDb.setTaskRemoteState(op.entityId, "needs_attention", "validation_failed");
          }
          pushSyncEvent("error", "push_op_payload_corrupt", {
            opId: op.id,
            entityType: op.entityType,
            entityId: op.entityId,
            error: parseMessage,
          });
          continue;
        }
      }

      switch (op.entityType) {
        case "task": {
          const localTask = localDb.getTaskById(op.entityId);
          const remoteTaskId = op.entityRemoteId ?? localTask?.remoteId ?? null;
          if (op.operation === "create") {
            const created = await api.createTask(payload);
            localDb.reconcileTaskServerAck({
              taskId: op.entityId,
              clientOpId: op.clientOpId,
              operation: op.operation,
              ackLocalVersion: op.localVersion,
              serverTask: created,
            });
          } else if (op.operation === "update") {
            if (!remoteTaskId) {
              throw new Error("Missing remote task id for update");
            }
            const updated = await api.updateTask(remoteTaskId, payload);
            localDb.reconcileTaskServerAck({
              taskId: op.entityId,
              clientOpId: op.clientOpId,
              operation: op.operation,
              ackLocalVersion: op.localVersion,
              serverTask: updated,
            });
          } else if (op.operation === "complete_with_review") {
            if (!remoteTaskId) {
              throw new Error("Missing remote task id for complete_with_review");
            }
            const reviewNote =
              typeof payload.reviewNote === "string" ? payload.reviewNote.trim() : "";
            if (!reviewNote) {
              throw new Error("Missing review note for complete_with_review");
            }
            const reviewedTask = await api.completeTaskWithReview(remoteTaskId, reviewNote);
            localDb.reconcileTaskServerAck({
              taskId: op.entityId,
              clientOpId: op.clientOpId,
              operation: op.operation,
              ackLocalVersion: op.localVersion,
              serverTask: reviewedTask,
            });
          } else if (op.operation === "delete") {
            if (remoteTaskId) {
              await api.deleteTask(remoteTaskId);
            }
            localDb.purgeTask(op.entityId);
          }
          break;
        }
        // 可以扩展其他实体类型...
      }

      localDb.removeOp(op.id);
    } catch (error: any) {
      const message = error?.message || "Unknown error";
      const reasonCode = mapSyncErrorToReasonCode(error);
      const nextStatus = op.retryCount + 1 >= MAX_OP_RETRIES ? "needs_attention" : "queued";
      localDb.markOpFailed(op.id, message, reasonCode, nextStatus);
      if (op.entityType === "task") {
        localDb.setTaskRemoteState(op.entityId, nextStatus, reasonCode);
      }

      // 如果是 401 错误，停止推送（需要重新登录）
      if (error instanceof api.ApiError && error.status === 401) {
        setSyncFreezeState("blocked_by_auth", "auth_expired");
        pushSyncEvent("error", "push_op_auth_blocked", {
          opId: op.id,
          entityType: op.entityType,
          operation: op.operation,
        });
        throw error;
      }
    }
  }
}

/**
 * 下行拉取：从云端获取最新数据写入本地 SQLite
 */
async function pullFromCloud(isAborted: () => boolean = () => false): Promise<void> {
  _taskBoardFetchCount += 1;
  devLog("taskBoard", "fetch.from_sync_engine", { count: _taskBoardFetchCount });
  pushSyncEvent("info", "pull_started", { taskBoardFetchCount: _taskBoardFetchCount });

  // 并行拉取各类数据
  const [boardResult, eventLinesResult, clientsResult, taskListsResult] =
    await Promise.allSettled([
      api.fetchTaskBoard(),
      api.fetchEventLines(),
      api.fetchClients(),
      api.fetchTaskLists(),
    ]);

  // 关键护栏：拿到云端数据后、写本地 DB 前，确认引擎实例还没被切换。
  // 否则用户切账号时旧账号的数据会写进新账号的 SQLite。
  if (isAborted()) {
    devLog("sync", "pull.aborted_before_write");
    pushSyncEvent("info", "pull_aborted_before_write");
    return;
  }

  if (boardResult.status === "fulfilled") {
    localDb.upsertTasksFromCloud(boardResult.value.tasks);
    void rescheduleAllReminders();
  }

  if (eventLinesResult.status === "fulfilled") {
    localDb.upsertEventLinesFromCloud(eventLinesResult.value);
  }

  if (clientsResult.status === "fulfilled") {
    localDb.upsertClientsFromCloud(clientsResult.value);
  }

  if (taskListsResult.status === "fulfilled") {
    localDb.upsertTaskListsFromCloud(taskListsResult.value);
  }

  // 如果所有请求都失败了，抛出错误
  const allFailed = [boardResult, eventLinesResult, clientsResult, taskListsResult]
    .every((r) => r.status === "rejected");
  if (allFailed) {
    pushSyncEvent("error", "pull_failed_all_requests");
    throw new Error("All cloud sync requests failed");
  }

  pushSyncEvent("info", "pull_succeeded", {
    board: boardResult.status,
    eventLines: eventLinesResult.status,
    clients: clientsResult.status,
    taskLists: taskListsResult.status,
  });
}

// ─── Foreground Sync ────────────────────────────

function startForegroundSync(): void {
  stopForegroundSync();
  _syncTimer = setInterval(() => {
    void performSync();
  }, SYNC_INTERVAL_MS);
}

function stopForegroundSync(): void {
  if (_syncTimer) {
    clearInterval(_syncTimer);
    _syncTimer = null;
  }
}

function handleAppStateChange(nextState: AppStateStatus): void {
  if (!_isStarted) return;
  if (nextState === "active") {
    // App 回到前台，立即同步一次 + 恢复定时器
    void performSync();
    startForegroundSync();
  } else if (nextState === "background") {
    // 进入后台，停止前台定时器（交给 BackgroundFetch）
    stopForegroundSync();
  }
}

// ─── Background Sync ────────────────────────────

TaskManager.defineTask(BACKGROUND_SYNC_TASK, async () => {
  try {
    await performSync();
    return BackgroundFetch.BackgroundFetchResult.NewData;
  } catch {
    return BackgroundFetch.BackgroundFetchResult.Failed;
  }
});

async function registerBackgroundSync(): Promise<void> {
  if (_backgroundSyncRegistered) {
    return;
  }
  try {
    const status = await BackgroundFetch.getStatusAsync();
    if (status === BackgroundFetch.BackgroundFetchStatus.Denied) {
      console.warn("[SyncEngine] Background fetch is denied by the OS");
      return;
    }

    const alreadyRegistered = await TaskManager.isTaskRegisteredAsync(BACKGROUND_SYNC_TASK);
    if (!alreadyRegistered) {
      await BackgroundFetch.registerTaskAsync(BACKGROUND_SYNC_TASK, {
        minimumInterval: 15 * 60,
        stopOnTerminate: false,
        startOnBoot: true,
      });
    }
    _backgroundSyncRegistered = true;
  } catch (error) {
    console.warn("[SyncEngine] Failed to register background sync:", error);
  }
}

// ─── Offline-First Write Helpers ────────────────

/**
 * 离线优先的任务创建
 * 立即写入本地 SQLite → 排入上传队列 → 后台异步上传
 */
export function createTaskOfflineFirst(task: TaskRecord): MutationReceipt {
  const { task: createdTask, receipt } = commitCreateTaskLocalFirst({
    title: task.title,
    description: task.description ?? undefined,
    dueDate: task.dueDate ?? undefined,
    durationMinutes: task.durationMinutes ?? undefined,
    deadlineAt: task.deadlineAt ?? undefined,
    scheduledStartAt: task.scheduledStartAt ?? undefined,
    scheduledEndAt: task.scheduledEndAt ?? undefined,
    completedAt: task.completedAt ?? undefined,
    reminderMinutesBefore: task.reminderMinutesBefore ?? undefined,
    priority: task.priority,
    clientId: task.clientId ?? undefined,
    eventLineId: task.eventLineId ?? undefined,
    listId: task.listId ?? undefined,
    tags: tagsToStringArray(task.tags),
    businessCategory: task.businessCategory ?? undefined,
    currentBlocker: task.currentBlocker ?? undefined,
    nextAction: task.nextAction ?? undefined,
    recentDecision: task.recentDecision ?? undefined,
  });
  void scheduleTaskReminder(createdTask);
  notifyDataChanged();
  if (_isStarted && !isSyncFreezePaused(_syncFreezeState) && !isSyncFreezeBlocked(_syncFreezeState)) {
    void performSync();
  }
  return receipt;
}

/**
 * 离线优先的任务更新
 */
export function updateTaskOfflineFirst(
  taskId: string,
  updates: Partial<TaskRecord>,
): MutationReceipt {
  const hasDueDate = Object.prototype.hasOwnProperty.call(updates, "dueDate") && updates.dueDate !== undefined;
  const hasDurationMinutes =
    Object.prototype.hasOwnProperty.call(updates, "durationMinutes") && updates.durationMinutes !== undefined;
  const hasDeadlineAt = Object.prototype.hasOwnProperty.call(updates, "deadlineAt") && updates.deadlineAt !== undefined;
  const hasScheduledStartAt =
    Object.prototype.hasOwnProperty.call(updates, "scheduledStartAt") && updates.scheduledStartAt !== undefined;
  const hasScheduledEndAt =
    Object.prototype.hasOwnProperty.call(updates, "scheduledEndAt") && updates.scheduledEndAt !== undefined;
  const hasCompletedAt = Object.prototype.hasOwnProperty.call(updates, "completedAt") && updates.completedAt !== undefined;
  const hasReminder = Object.prototype.hasOwnProperty.call(updates, "reminderMinutesBefore") && updates.reminderMinutesBefore !== undefined;
  const { task: updatedTask, receipt } = commitUpdateTaskLocalFirst(taskId, {
    title: updates.title,
    description: updates.description ?? undefined,
    dueDate: hasDueDate ? updates.dueDate ?? null : undefined,
    durationMinutes: hasDurationMinutes ? updates.durationMinutes ?? null : undefined,
    deadlineAt: hasDeadlineAt ? updates.deadlineAt ?? null : undefined,
    scheduledStartAt: hasScheduledStartAt ? updates.scheduledStartAt ?? null : undefined,
    scheduledEndAt: hasScheduledEndAt ? updates.scheduledEndAt ?? null : undefined,
    completedAt: hasCompletedAt ? updates.completedAt ?? null : undefined,
    reminderMinutesBefore: hasReminder ? updates.reminderMinutesBefore ?? null : undefined,
    priority: updates.priority,
    clientId: updates.clientId ?? undefined,
    eventLineId: updates.eventLineId ?? undefined,
    listId: updates.listId ?? undefined,
    tags: tagsToStringArray(updates.tags),
    businessCategory: updates.businessCategory ?? undefined,
    currentBlocker: updates.currentBlocker ?? undefined,
    nextAction: updates.nextAction ?? undefined,
    recentDecision: updates.recentDecision ?? undefined,
    progressStatus: updates.progressStatus,
  });
  // 直接用本地提交返回的 task（含本次更新），避免多余一次 DB 读 + 消除 TOCTOU。
  if (updatedTask) void scheduleTaskReminder(updatedTask);
  notifyDataChanged();
  if (_isStarted && !isSyncFreezePaused(_syncFreezeState) && !isSyncFreezeBlocked(_syncFreezeState)) {
    void performSync();
  }
  return receipt;
}

/**
 * 离线优先的任务删除
 */
export function deleteTaskOfflineFirst(taskId: string): MutationReceipt {
  const { receipt } = commitDeleteTaskLocalFirst(taskId);
  void cancelTaskReminder(taskId);
  notifyDataChanged();
  if (_isStarted && !isSyncFreezePaused(_syncFreezeState) && !isSyncFreezeBlocked(_syncFreezeState)) {
    void performSync();
  }
  return receipt;
}

export function completeTaskWithReviewOfflineFirst(
  taskId: string,
  reviewNote: string,
): MutationReceipt {
  const { receipt } = commitCompleteTaskWithReviewLocalFirst(taskId, reviewNote);
  void cancelTaskReminder(taskId);
  notifyDataChanged();
  if (_isStarted && !isSyncFreezePaused(_syncFreezeState) && !isSyncFreezeBlocked(_syncFreezeState)) {
    void performSync();
  }
  return receipt;
}
