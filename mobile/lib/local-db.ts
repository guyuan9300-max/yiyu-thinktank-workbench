/**
 * local-db.ts — SQLite 本地数据库层
 *
 * 采用 expo-sqlite (同步 API) 提供结构化的本地存储，
 * 替代 AsyncStorage 的 JSON 大块读写，实现毫秒级查询。
 *
 * 表设计:
 *   tasks          — 任务主表，与云端 TaskRecord 一一对应
 *   task_lists     — 任务清单
 *   event_lines    — 事件线/项目线
 *   clients        — 客户摘要
 *   sync_meta      — 同步元数据（水位标记、版本号）
 *   pending_ops    — 离线操作队列（乐观写入，等待上传）
 *   recording_sessions / recording_segments — 本地录音与文本同步状态
 */

import * as SQLite from "expo-sqlite";
import { NO_ACCOUNT_SCOPE_KEY, normalizeAccountScopeKey } from "./account-scope";
import { formatLocalDateKey } from "./date";
import { measureDevSync } from "./dev-log";
import { foldPendingOps, type PendingOpDraft } from "./pending-op-policy";
import { shouldSkipCloudTaskSweep, shouldWarnLargeSweep } from "./cloud-sweep-policy";
import { getTaskCalendarDateKey } from "./task-time";
import { decideTaskServerAckAction } from "./task-sync-policy";
import type {
  RecordingSegment,
  RecordingSession,
  RecordingSessionStatus,
  RecordingSyncStatus,
  RecordingTargetType,
} from "./recording-session-core";
import type {
  PendingOpLane,
  PendingOpOperation,
  PendingOpRecord,
  PendingOpSummary,
  PendingOpVisibilityScope,
  RemoteMutationState,
  SyncReasonCode,
  HealthLaneDiagnostic,
  TaskConflictDiagnostic,
  TaskServerShadowRecord,
  TaskRecord,
  TaskBoardResponse,
  TaskListRecord,
  EventLineRecord,
  ClientSummaryRecord,
} from "./types";

// ─── Database Instance ──────────────────────────

let _db: SQLite.SQLiteDatabase | null = null;
let _activeAccountScopeKey: string | null = null;

const CURRENT_SCHEMA_VERSION = 7;
const META_ACCOUNT_SCOPE_KEY = "account_scope_key";
const META_INTEGRITY_STATUS = "sync_integrity_status";
const META_INTEGRITY_REASON = "sync_integrity_reason";

export function getDb(): SQLite.SQLiteDatabase {
  if (!_db) {
    _db = SQLite.openDatabaseSync("yiyu_local.db");
  }
  return _db;
}

// ─── Schema Migration ───────────────────────────

function getTableColumnNames(db: SQLite.SQLiteDatabase, tableName: string): Set<string> {
  const rows = db.getAllSync(`PRAGMA table_info(${tableName});`);
  return new Set(rows.map((row: any) => row.name as string));
}

function ensureColumn(
  db: SQLite.SQLiteDatabase,
  tableName: string,
  columnName: string,
  ddl: string,
): void {
  const columns = getTableColumnNames(db, tableName);
  if (!columns.has(columnName)) {
    db.execSync(`ALTER TABLE ${tableName} ADD COLUMN ${ddl};`);
  }
}

function ensureRecordingTables(db: SQLite.SQLiteDatabase): void {
  db.execSync(`
    CREATE TABLE IF NOT EXISTS recording_sessions (
      id TEXT PRIMARY KEY,
      scope_key TEXT NOT NULL,
      source TEXT NOT NULL,
      target_type TEXT NOT NULL,
      target_local_id TEXT,
      target_remote_id TEXT,
      client_id TEXT,
      event_line_id TEXT,
      task_id TEXT,
      meeting_id TEXT,
      audio_path TEXT,
      duration_seconds REAL,
      mime_type TEXT,
      audio_hash TEXT,
      raw_transcript_path TEXT,
      clean_transcript_path TEXT,
      summary_json TEXT,
      status TEXT NOT NULL DEFAULT 'local_saved',
      sync_status TEXT NOT NULL DEFAULT 'local_only',
      last_error TEXT,
      latitude REAL,
      longitude REAL,
      place_label TEXT,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS recording_segments (
      id TEXT PRIMARY KEY,
      recording_id TEXT NOT NULL,
      segment_index INTEGER NOT NULL,
      start_ms INTEGER NOT NULL DEFAULT 0,
      end_ms INTEGER,
      text TEXT NOT NULL,
      confidence REAL,
      is_final INTEGER NOT NULL DEFAULT 1,
      created_at TEXT NOT NULL,
      FOREIGN KEY(recording_id) REFERENCES recording_sessions(id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_recording_sessions_scope ON recording_sessions(scope_key, created_at);
    CREATE INDEX IF NOT EXISTS idx_recording_sessions_sync ON recording_sessions(sync_status, updated_at);
    CREATE INDEX IF NOT EXISTS idx_recording_sessions_target
      ON recording_sessions(target_type, target_local_id, target_remote_id);
    CREATE INDEX IF NOT EXISTS idx_recording_segments_recording
      ON recording_segments(recording_id, segment_index);
  `);
}

function setSyncMetaWithDb(db: SQLite.SQLiteDatabase, key: string, value: string): void {
  db.runSync(
    `INSERT OR REPLACE INTO sync_meta (key, value, updated_at)
     VALUES (?, ?, datetime('now'))`,
    [key, value],
  );
}

function clearSessionDataWithDb(db: SQLite.SQLiteDatabase): void {
  try {
    db.runSync("DELETE FROM recording_segments");
    db.runSync("DELETE FROM recording_sessions");
  } catch {
    // Databases older than v5 do not have recording tables yet.
  }
  db.runSync("DELETE FROM tasks");
  db.runSync("DELETE FROM task_lists");
  db.runSync("DELETE FROM event_lines");
  db.runSync("DELETE FROM clients");
  db.runSync("DELETE FROM pending_ops");
  db.runSync("DELETE FROM task_server_shadow");
  db.runSync(
    "DELETE FROM sync_meta WHERE key NOT IN (?, ?, ?)",
    [META_ACCOUNT_SCOPE_KEY, META_INTEGRITY_STATUS, META_INTEGRITY_REASON],
  );
}

export function initDatabase(): void {
  const db = getDb();

  // Enable WAL mode for better concurrent read/write performance
  db.execSync("PRAGMA journal_mode = WAL;");
  db.execSync("PRAGMA foreign_keys = ON;");

  const row = db.getFirstSync<{ user_version: number }>("PRAGMA user_version;");
  const version = row?.user_version ?? 0;

  if (version < 1) {
    db.execSync(`
      CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY,
        remote_id TEXT,
        title TEXT NOT NULL DEFAULT '',
        description TEXT,
        due_date TEXT,
        duration_minutes INTEGER,
        deadline_at TEXT,
        scheduled_start_at TEXT,
        scheduled_end_at TEXT,
        completed_at TEXT,
        reminder_minutes_before INTEGER,
        priority TEXT NOT NULL DEFAULT 'normal',
        progress_status TEXT NOT NULL DEFAULT 'inbox',
        tags TEXT,
        client_id TEXT,
        client_name TEXT,
        event_line_id TEXT,
        event_line_name TEXT,
        list_id TEXT,
        list_name TEXT,
        owner_id TEXT,
        owner_name TEXT,
        business_category TEXT,
        current_blocker TEXT,
        next_action TEXT,
        recent_decision TEXT,
        completion_note TEXT,
        attachments_json TEXT,
        collaborators_json TEXT,
        viewer_inbox_status TEXT,
        created_at TEXT,
        updated_at TEXT,
        local_version INTEGER NOT NULL DEFAULT 0,
        base_remote_version INTEGER,
        server_version INTEGER,
        local_state TEXT NOT NULL DEFAULT 'local_committed',
        remote_state TEXT NOT NULL DEFAULT 'synced',
        sync_reason_code TEXT,
        deleted_at TEXT,
        -- 同步元数据
        _synced INTEGER NOT NULL DEFAULT 1,
        _local_updated_at TEXT,
        _deleted INTEGER NOT NULL DEFAULT 0
      );

      CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON tasks(due_date);
      CREATE INDEX IF NOT EXISTS idx_tasks_deadline_at ON tasks(deadline_at);
      CREATE INDEX IF NOT EXISTS idx_tasks_scheduled_start_at ON tasks(scheduled_start_at);
      CREATE INDEX IF NOT EXISTS idx_tasks_progress_status ON tasks(progress_status);
      CREATE INDEX IF NOT EXISTS idx_tasks_synced ON tasks(_synced);
      CREATE INDEX IF NOT EXISTS idx_tasks_list_id ON tasks(list_id);
      CREATE INDEX IF NOT EXISTS idx_tasks_event_line_id ON tasks(event_line_id);
      CREATE INDEX IF NOT EXISTS idx_tasks_remote_id ON tasks(remote_id);

      CREATE TABLE IF NOT EXISTS task_lists (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL DEFAULT '',
        color TEXT,
        is_default INTEGER NOT NULL DEFAULT 0,
        _synced INTEGER NOT NULL DEFAULT 1
      );

      CREATE TABLE IF NOT EXISTS event_lines (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL DEFAULT '',
        primary_client_id TEXT,
        primary_client_name TEXT,
        summary TEXT,
        current_blocker TEXT,
        next_step TEXT,
        recent_decision TEXT,
        stage TEXT,
        status TEXT,
        _synced INTEGER NOT NULL DEFAULT 1
      );

      CREATE TABLE IF NOT EXISTS clients (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL DEFAULT '',
        alias TEXT,
        _synced INTEGER NOT NULL DEFAULT 1
      );

      CREATE TABLE IF NOT EXISTS sync_meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
      );

      CREATE TABLE IF NOT EXISTS pending_ops (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_op_id TEXT NOT NULL UNIQUE,
        entity_type TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        entity_remote_id TEXT,
        operation TEXT NOT NULL,
        payload TEXT,
        lane TEXT NOT NULL DEFAULT 'interactive',
        status TEXT NOT NULL DEFAULT 'queued',
        visibility_scope TEXT NOT NULL DEFAULT 'team_shared',
        local_version INTEGER NOT NULL DEFAULT 0,
        base_remote_version INTEGER,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        retry_count INTEGER NOT NULL DEFAULT 0,
        last_error TEXT,
        reason_code TEXT
      );

      CREATE INDEX IF NOT EXISTS idx_pending_ops_entity ON pending_ops(entity_type, entity_id);
      CREATE INDEX IF NOT EXISTS idx_pending_ops_lane ON pending_ops(lane, created_at);

      CREATE TABLE IF NOT EXISTS task_server_shadow (
        task_id TEXT PRIMARY KEY,
        remote_id TEXT,
        server_version INTEGER,
        payload_json TEXT NOT NULL,
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
      );
    `);
  }

  if (version < 2) {
    ensureColumn(db, "tasks", "remote_id", "remote_id TEXT");
    ensureColumn(db, "tasks", "local_version", "local_version INTEGER NOT NULL DEFAULT 0");
    ensureColumn(db, "tasks", "base_remote_version", "base_remote_version INTEGER");
    ensureColumn(db, "tasks", "server_version", "server_version INTEGER");
    ensureColumn(db, "tasks", "local_state", "local_state TEXT NOT NULL DEFAULT 'local_committed'");
    ensureColumn(db, "tasks", "remote_state", "remote_state TEXT NOT NULL DEFAULT 'synced'");
    ensureColumn(db, "tasks", "sync_reason_code", "sync_reason_code TEXT");
    ensureColumn(db, "tasks", "deleted_at", "deleted_at TEXT");
    db.execSync("CREATE INDEX IF NOT EXISTS idx_tasks_remote_id ON tasks(remote_id);");

    ensureColumn(db, "pending_ops", "client_op_id", "client_op_id TEXT");
    ensureColumn(db, "pending_ops", "entity_remote_id", "entity_remote_id TEXT");
    ensureColumn(db, "pending_ops", "lane", "lane TEXT NOT NULL DEFAULT 'interactive'");
    ensureColumn(db, "pending_ops", "status", "status TEXT NOT NULL DEFAULT 'queued'");
    ensureColumn(db, "pending_ops", "visibility_scope", "visibility_scope TEXT NOT NULL DEFAULT 'team_shared'");
    ensureColumn(db, "pending_ops", "local_version", "local_version INTEGER NOT NULL DEFAULT 0");
    ensureColumn(db, "pending_ops", "base_remote_version", "base_remote_version INTEGER");
    ensureColumn(db, "pending_ops", "updated_at", "updated_at TEXT NOT NULL DEFAULT (datetime('now'))");
    ensureColumn(db, "pending_ops", "reason_code", "reason_code TEXT");
    db.execSync("CREATE INDEX IF NOT EXISTS idx_pending_ops_lane ON pending_ops(lane, created_at);");

    db.runSync(
      "UPDATE tasks SET remote_id = id WHERE remote_id IS NULL AND _synced = 1 AND _deleted = 0",
    );
    db.runSync(
      "UPDATE tasks SET local_state = 'local_committed' WHERE local_state IS NULL OR local_state = ''",
    );
    db.runSync(
      "UPDATE tasks SET remote_state = CASE WHEN _synced = 1 THEN 'synced' ELSE 'queued' END WHERE remote_state IS NULL OR remote_state = ''",
    );
    db.runSync(
      "UPDATE pending_ops SET client_op_id = 'migrated_op_' || id WHERE client_op_id IS NULL OR client_op_id = ''",
    );
    db.runSync(
      "UPDATE pending_ops SET lane = 'interactive' WHERE lane IS NULL OR lane = ''",
    );
    db.runSync(
      "UPDATE pending_ops SET status = 'queued' WHERE status IS NULL OR status = ''",
    );
    db.runSync(
      "UPDATE pending_ops SET visibility_scope = 'team_shared' WHERE visibility_scope IS NULL OR visibility_scope = ''",
    );
    db.runSync(
      "UPDATE pending_ops SET updated_at = created_at WHERE updated_at IS NULL OR updated_at = ''",
    );
    db.execSync("CREATE UNIQUE INDEX IF NOT EXISTS idx_pending_ops_client_op_id ON pending_ops(client_op_id);");
  }

  if (version < 3) {
    db.execSync(`
      CREATE TABLE IF NOT EXISTS task_server_shadow (
        task_id TEXT PRIMARY KEY,
        remote_id TEXT,
        server_version INTEGER,
        payload_json TEXT NOT NULL,
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
      );
    `);
  }

  if (version < 4) {
    ensureColumn(db, "tasks", "deadline_at", "deadline_at TEXT");
    ensureColumn(db, "tasks", "scheduled_start_at", "scheduled_start_at TEXT");
    ensureColumn(db, "tasks", "scheduled_end_at", "scheduled_end_at TEXT");
    ensureColumn(db, "tasks", "completed_at", "completed_at TEXT");
    db.execSync("CREATE INDEX IF NOT EXISTS idx_tasks_deadline_at ON tasks(deadline_at);");
    db.execSync("CREATE INDEX IF NOT EXISTS idx_tasks_scheduled_start_at ON tasks(scheduled_start_at);");
    db.runSync("UPDATE tasks SET deadline_at = due_date WHERE deadline_at IS NULL AND due_date IS NOT NULL AND instr(due_date, 'T') = 0");
    db.runSync("UPDATE tasks SET scheduled_start_at = due_date WHERE scheduled_start_at IS NULL AND due_date IS NOT NULL AND instr(due_date, 'T') > 0");
    db.runSync("UPDATE tasks SET completed_at = COALESCE(NULLIF(updated_at, ''), datetime('now')) WHERE completed_at IS NULL AND progress_status = 'done'");
  }

  if (version < 5) {
    ensureRecordingTables(db);
  }

  if (version < 6) {
    // 录音定位：现场记录可选记录经纬度 + 反查地名，便于归档时辨认现场。
    ensureColumn(db, "recording_sessions", "latitude", "latitude REAL");
    ensureColumn(db, "recording_sessions", "longitude", "longitude REAL");
    ensureColumn(db, "recording_sessions", "place_label", "place_label TEXT");
  }

  if (version < 7) {
    // 任务提醒：提前量(分钟)，跨端共享同一字段。0=准时 5=提前5分 null=不提醒。
    ensureColumn(db, "tasks", "reminder_minutes_before", "reminder_minutes_before INTEGER");
  }

  db.execSync(`PRAGMA user_version = ${CURRENT_SCHEMA_VERSION};`);
}

export function getActiveAccountScopeKey(): string | null {
  return _activeAccountScopeKey ?? normalizeAccountScopeKey(getSyncMeta(META_ACCOUNT_SCOPE_KEY));
}

export function getDataIntegrityState(): {
  accountScopeKey: string;
  integrityStatus: "ok" | "blocked";
  integrityReason: string | null;
} {
  const accountScopeKey =
    normalizeAccountScopeKey(getSyncMeta(META_ACCOUNT_SCOPE_KEY)) ?? NO_ACCOUNT_SCOPE_KEY;
  const integrityStatus = getSyncMeta(META_INTEGRITY_STATUS) === "blocked" ? "blocked" : "ok";
  const integrityReason = getSyncMeta(META_INTEGRITY_REASON) || null;
  return {
    accountScopeKey,
    integrityStatus,
    integrityReason,
  };
}

export function validateDatabaseIntegrity(): {
  integrityStatus: "ok" | "blocked";
  integrityReason: string | null;
} {
  initDatabase();
  const db = getDb();
  const orphanTaskPendingOps = db.getFirstSync<{ cnt: number }>(
    `SELECT COUNT(*) as cnt
       FROM pending_ops po
       LEFT JOIN tasks t
         ON po.entity_type = 'task'
        AND po.entity_id = t.id
      WHERE po.entity_type = 'task'
        AND t.id IS NULL`,
  )?.cnt ?? 0;

  const orphanTaskShadows = db.getFirstSync<{ cnt: number }>(
    `SELECT COUNT(*) as cnt
       FROM task_server_shadow shadow
       LEFT JOIN tasks t ON shadow.task_id = t.id
      WHERE t.id IS NULL`,
  )?.cnt ?? 0;

  const integrityReason =
    orphanTaskPendingOps > 0
      ? "orphan_task_pending_ops"
      : orphanTaskShadows > 0
        ? "orphan_task_server_shadow"
        : null;
  const integrityStatus = integrityReason ? "blocked" : "ok";

  setSyncMetaWithDb(db, META_INTEGRITY_STATUS, integrityStatus);
  setSyncMetaWithDb(db, META_INTEGRITY_REASON, integrityReason ?? "");

  return {
    integrityStatus,
    integrityReason,
  };
}

export function prepareDatabaseForAccountScope(scopeKey: string): {
  scopeChanged: boolean;
  integrityStatus: "ok" | "blocked";
  integrityReason: string | null;
} {
  initDatabase();
  const db = getDb();
  const normalizedScopeKey = normalizeAccountScopeKey(scopeKey) ?? NO_ACCOUNT_SCOPE_KEY;
  const storedScopeKey = normalizeAccountScopeKey(getSyncMeta(META_ACCOUNT_SCOPE_KEY));
  const legacyPendingOpsCount = db.getFirstSync<{ cnt: number }>(
    "SELECT COUNT(*) as cnt FROM pending_ops",
  )?.cnt ?? 0;
  const scopeChanged = Boolean(storedScopeKey && storedScopeKey !== normalizedScopeKey);
  const shouldClearLegacyQueue = !storedScopeKey && legacyPendingOpsCount > 0;

  db.withTransactionSync(() => {
    if (scopeChanged || shouldClearLegacyQueue) {
      clearSessionDataWithDb(db);
    }
    setSyncMetaWithDb(db, META_ACCOUNT_SCOPE_KEY, normalizedScopeKey);
  });

  _activeAccountScopeKey = normalizedScopeKey;
  const integrity = validateDatabaseIntegrity();
  return {
    scopeChanged,
    integrityStatus: integrity.integrityStatus,
    integrityReason: integrity.integrityReason,
  };
}

// ─── Task CRUD ──────────────────────────────────

function taskToRow(task: TaskRecord) {
  return {
    $id: task.id,
    $remote_id: task.remoteId ?? null,
    $title: task.title,
    $description: task.description ?? null,
    $due_date: task.dueDate ?? null,
    $duration_minutes: task.durationMinutes ?? null,
    $deadline_at: task.deadlineAt ?? null,
    $scheduled_start_at: task.scheduledStartAt ?? null,
    $scheduled_end_at: task.scheduledEndAt ?? null,
    $completed_at: task.completedAt ?? null,
    $reminder_minutes_before: task.reminderMinutesBefore ?? null,
    $priority: task.priority,
    $progress_status: task.progressStatus,
    $tags: task.tags ? JSON.stringify(task.tags) : null,
    $client_id: task.clientId ?? null,
    $client_name: task.clientName ?? null,
    $event_line_id: task.eventLineId ?? null,
    $event_line_name: task.eventLineName ?? null,
    $list_id: task.listId ?? null,
    $list_name: task.listName ?? null,
    $owner_id: task.ownerId ?? null,
    $owner_name: task.ownerName ?? null,
    $business_category: task.businessCategory ?? null,
    $current_blocker: task.currentBlocker ?? null,
    $next_action: task.nextAction ?? null,
    $recent_decision: task.recentDecision ?? null,
    $completion_note: task.completionNote ?? null,
    $attachments_json: task.attachments ? JSON.stringify(task.attachments) : null,
    $collaborators_json: task.collaborators ? JSON.stringify(task.collaborators) : null,
    $viewer_inbox_status: task.viewerInboxStatus ?? null,
    $created_at: task.createdAt ?? null,
    $updated_at: task.updatedAt ?? null,
    $local_version: task.localVersion ?? 0,
    $base_remote_version: task.baseRemoteVersion ?? null,
    $server_version: task.serverVersion ?? null,
    $local_state: task.localState ?? "local_committed",
    $remote_state: task.remoteState ?? "synced",
    $sync_reason_code: task.syncReasonCode ?? null,
    $deleted_at: task.deletedAt ?? null,
  };
}

// JSON 列（tags / attachments / collaborators）历史上可能被磁盘满、强杀等场景写成
// 损坏字符串。rowToTask 是任务列表 / board 的核心映射函数，每一行都经过它——
// 这里裸 JSON.parse 一旦抛 SyntaxError 会让整个任务视图崩溃。沿用本文件
// getTaskServerShadow(L1002) 已验证的范式：损坏时 warn + 降级为默认值，让该行
// 仍能渲染，而不是拖垮整页。fallback 与历史默认值（null / undefined）保持一致。
function parseJsonColumn<T>(raw: unknown, fallback: T, column: string): T {
  if (typeof raw !== "string" || raw.length === 0) {
    return fallback;
  }
  try {
    return JSON.parse(raw) as T;
  } catch (error) {
    console.warn("[local-db] rowToTask: JSON 列损坏，降级为默认值", {
      column,
      error: error instanceof Error ? error.message : String(error),
    });
    return fallback;
  }
}

function rowToTask(row: any): TaskRecord {
  return {
    id: row.id,
    remoteId: row.remote_id,
    title: row.title,
    description: row.description,
    dueDate: row.due_date,
    durationMinutes: row.duration_minutes,
    deadlineAt: row.deadline_at,
    scheduledStartAt: row.scheduled_start_at,
    scheduledEndAt: row.scheduled_end_at,
    completedAt: row.completed_at,
    reminderMinutesBefore: row.reminder_minutes_before ?? null,
    priority: row.priority,
    progressStatus: row.progress_status,
    tags: parseJsonColumn<TaskRecord["tags"]>(row.tags, null, "tags"),
    clientId: row.client_id,
    clientName: row.client_name,
    eventLineId: row.event_line_id,
    eventLineName: row.event_line_name,
    listId: row.list_id,
    listName: row.list_name,
    ownerId: row.owner_id,
    ownerName: row.owner_name,
    businessCategory: row.business_category,
    currentBlocker: row.current_blocker,
    nextAction: row.next_action,
    recentDecision: row.recent_decision,
    completionNote: row.completion_note,
    attachments: parseJsonColumn<TaskRecord["attachments"]>(
      row.attachments_json,
      undefined,
      "attachments",
    ),
    collaborators: parseJsonColumn<TaskRecord["collaborators"]>(
      row.collaborators_json,
      undefined,
      "collaborators",
    ),
    viewerInboxStatus: row.viewer_inbox_status,
    localVersion: row.local_version ?? 0,
    baseRemoteVersion: row.base_remote_version,
    serverVersion: row.server_version,
    localState: row.local_state ?? "local_committed",
    remoteState: row.remote_state ?? "synced",
    syncReasonCode: row.sync_reason_code ?? null,
    deletedAt: row.deleted_at ?? null,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  };
}

function upsertTaskRow(
  db: SQLite.SQLiteDatabase,
  task: TaskRecord,
  options: {
    synced: boolean;
    deleted: boolean;
    localUpdatedAt: string | null;
  },
): void {
  db.runSync(`
    INSERT OR REPLACE INTO tasks (
      id, remote_id, title, description, due_date, duration_minutes,
      deadline_at, scheduled_start_at, scheduled_end_at, completed_at,
      reminder_minutes_before,
      priority, progress_status, tags, client_id, client_name,
      event_line_id, event_line_name, list_id, list_name,
      owner_id, owner_name, business_category, current_blocker,
      next_action, recent_decision, completion_note,
      attachments_json, collaborators_json, viewer_inbox_status,
      created_at, updated_at, local_version, base_remote_version,
      server_version, local_state, remote_state, sync_reason_code,
      deleted_at, _synced, _local_updated_at, _deleted
    ) VALUES (
      $id, $remote_id, $title, $description, $due_date, $duration_minutes,
      $deadline_at, $scheduled_start_at, $scheduled_end_at, $completed_at,
      $reminder_minutes_before,
      $priority, $progress_status, $tags, $client_id, $client_name,
      $event_line_id, $event_line_name, $list_id, $list_name,
      $owner_id, $owner_name, $business_category, $current_blocker,
      $next_action, $recent_decision, $completion_note,
      $attachments_json, $collaborators_json, $viewer_inbox_status,
      $created_at, $updated_at, $local_version, $base_remote_version,
      $server_version, $local_state, $remote_state, $sync_reason_code,
      $deleted_at, $synced, $local_updated_at, $deleted
    )
  `, {
    ...taskToRow(task),
    $synced: options.synced ? 1 : 0,
    $local_updated_at: options.localUpdatedAt,
    $deleted: options.deleted ? 1 : 0,
  });
}

function upsertTaskServerShadowWithDb(
  db: SQLite.SQLiteDatabase,
  taskId: string,
  serverTask: TaskRecord,
): void {
  db.runSync(
    `INSERT OR REPLACE INTO task_server_shadow (
      task_id, remote_id, server_version, payload_json, updated_at
    ) VALUES (?, ?, ?, ?, datetime('now'))`,
    [
      taskId,
      serverTask.remoteId ?? serverTask.id,
      serverTask.serverVersion ?? null,
      JSON.stringify(serverTask),
    ],
  );
}

function clearTaskServerShadowWithDb(db: SQLite.SQLiteDatabase, taskId: string): void {
  db.runSync("DELETE FROM task_server_shadow WHERE task_id = ?", [taskId]);
}

/**
 * 批量写入从云端拉取的任务（全量同步）。
 * 使用事务保证原子性，先标记所有为已删除，再 upsert 活跃任务。
 */
export function upsertTasksFromCloud(tasks: TaskRecord[]): void {
  const db = getDb();

  db.withTransactionSync(() => {
    // 进入 sweep 前先记下本地已同步任务总数，用于「空响应 / 异常缩量」护栏。
    const localSyncedCount =
      db.getFirstSync<{ c: number }>("SELECT COUNT(*) AS c FROM tasks WHERE _synced = 1")?.c ?? 0;

    // 标记所有现有记录为 "可能已删除"
    db.runSync("UPDATE tasks SET _deleted = 1 WHERE _synced = 1");

    for (const task of tasks) {
      const remoteId = task.remoteId ?? task.id;
      const existing = db.getFirstSync<{
        id: string;
        local_version: number | null;
        _synced: number;
        remote_id: string | null;
      }>(
        "SELECT id, local_version, _synced, remote_id FROM tasks WHERE COALESCE(remote_id, id) = ? LIMIT 1",
        [remoteId],
      );
      if (existing && existing._synced === 0) {
        upsertTaskServerShadowWithDb(db, existing.id, {
          ...task,
          remoteId,
        });
        db.runSync(
          `UPDATE tasks
              SET remote_id = COALESCE(remote_id, ?),
                  server_version = COALESCE(?, server_version)
            WHERE id = ?`,
          [remoteId, task.serverVersion ?? null, existing.id],
        );
        continue;
      }
      upsertTaskRow(
        db,
        {
          ...task,
          id: existing?.id ?? remoteId,
          remoteId,
          localVersion: existing?.local_version ?? task.localVersion ?? 0,
          localState: "local_committed",
          remoteState: "synced",
          syncReasonCode: null,
          deletedAt: null,
        },
        { synced: true, deleted: false, localUpdatedAt: null },
      );
      clearTaskServerShadowWithDb(db, existing?.id ?? remoteId);
    }

    // 空响应护栏（C2）：本地有已同步任务、云端却返回 0 条——几乎一定是后端异常
    // （空数组 / 鉴权过滤 / 部署抖动），而非用户真的删光所有任务。一次坏响应不能
    // 清空本地，放弃本轮 sweep 并复原删除标记，让下一轮正常拉取重建。
    if (shouldSkipCloudTaskSweep(localSyncedCount, tasks.length)) {
      db.runSync("UPDATE tasks SET _deleted = 0 WHERE _synced = 1");
      console.warn(
        "[local-db] upsertTasksFromCloud: 云端返回 0 任务但本地有已同步任务，跳过删除以防清空(疑似后端异常)",
        { localSyncedCount },
      );
      return;
    }

    // 在途保护（C3）：sweep 时排除仍有未完成 pending op 的任务。create ack 后仍有
    // update/complete op 排队的任务，其云端快照可能尚未包含它们；直接删会让用户看到
    // "刚建/刚改的任务闪一下就没了"，并产生指向已不存在行的孤儿 op。
    const pendingGuard =
      "id NOT IN (SELECT DISTINCT entity_id FROM pending_ops WHERE entity_type = 'task')";

    // 诊断（C2 部分返回）：客户端无法区分"云端少返回一半"与"用户真删一半"，根治需
    // 后端提供显式 deletedIds 增量。这里不擅自跳过（避免误伤真实批量删除），但当单轮
    // 删除占比异常高时留痕，便于排查后端"部分返回"类异常。
    const toDelete =
      db.getFirstSync<{ c: number }>(
        `SELECT COUNT(*) AS c FROM tasks WHERE _deleted = 1 AND _synced = 1 AND ${pendingGuard}`,
      )?.c ?? 0;
    if (shouldWarnLargeSweep(toDelete, localSyncedCount)) {
      console.warn(
        "[local-db] upsertTasksFromCloud: 本轮将删除较多已同步任务，请确认云端返回完整",
        { toDelete, localSyncedCount, cloudCount: tasks.length },
      );
    }

    // 清除被标记、本地无未上传修改、且不在途的记录
    db.runSync(`DELETE FROM tasks WHERE _deleted = 1 AND _synced = 1 AND ${pendingGuard}`);
  });

  // 更新同步水位
  setSyncMeta("tasks_last_sync", new Date().toISOString());
}

/**
 * 本地创建/更新任务（乐观写入），标记为未同步
 */
export function upsertTaskLocally(task: TaskRecord): void {
  const db = getDb();
  upsertTaskRow(
    db,
    {
      ...task,
      localState: task.localState ?? "local_committed",
      remoteState: task.remoteState ?? "queued",
    },
    {
      synced: false,
      deleted: Boolean(task.deletedAt),
      localUpdatedAt: new Date().toISOString(),
    },
  );
}

/**
 * 标记任务已同步成功
 */
export function markTaskSynced(taskId: string): void {
  const db = getDb();
  db.runSync(
    "UPDATE tasks SET _synced = 1, _local_updated_at = NULL, remote_state = 'synced', sync_reason_code = NULL WHERE id = ?",
    [taskId],
  );
}

export function getTaskById(taskId: string): TaskRecord | null {
  const db = getDb();
  const row = db.getFirstSync("SELECT * FROM tasks WHERE id = ? LIMIT 1", [taskId]);
  return row ? rowToTask(row) : null;
}

function rowToRecordingSession(row: any): RecordingSession {
  return {
    id: row.id,
    scopeKey: row.scope_key,
    source: row.source,
    targetType: row.target_type as RecordingTargetType,
    targetLocalId: row.target_local_id ?? null,
    targetRemoteId: row.target_remote_id ?? null,
    clientId: row.client_id ?? null,
    eventLineId: row.event_line_id ?? null,
    taskId: row.task_id ?? null,
    meetingId: row.meeting_id ?? null,
    audioPath: row.audio_path ?? null,
    durationSeconds: row.duration_seconds ?? null,
    mimeType: row.mime_type ?? null,
    audioHash: row.audio_hash ?? null,
    rawTranscriptPath: row.raw_transcript_path ?? null,
    cleanTranscriptPath: row.clean_transcript_path ?? null,
    summaryJson: row.summary_json ?? null,
    status: row.status as RecordingSessionStatus,
    syncStatus: row.sync_status as RecordingSyncStatus,
    lastError: row.last_error ?? null,
    latitude: row.latitude ?? null,
    longitude: row.longitude ?? null,
    placeLabel: row.place_label ?? null,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  };
}

function rowToRecordingSegment(row: any): RecordingSegment {
  return {
    id: row.id,
    recordingId: row.recording_id,
    segmentIndex: Number(row.segment_index ?? 0),
    startMs: Number(row.start_ms ?? 0),
    endMs: row.end_ms == null ? null : Number(row.end_ms),
    text: row.text ?? "",
    confidence: row.confidence == null ? null : Number(row.confidence),
    isFinal: Number(row.is_final ?? 1) === 1,
    createdAt: row.created_at,
  };
}

export function upsertRecordingSession(session: RecordingSession): void {
  const db = getDb();
  db.runSync(
    `INSERT OR REPLACE INTO recording_sessions (
      id, scope_key, source, target_type, target_local_id, target_remote_id,
      client_id, event_line_id, task_id, meeting_id, audio_path, duration_seconds,
      mime_type, audio_hash, raw_transcript_path, clean_transcript_path, summary_json,
      status, sync_status, last_error, latitude, longitude, place_label, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    [
      session.id,
      session.scopeKey,
      session.source,
      session.targetType,
      session.targetLocalId ?? null,
      session.targetRemoteId ?? null,
      session.clientId ?? null,
      session.eventLineId ?? null,
      session.taskId ?? null,
      session.meetingId ?? null,
      session.audioPath ?? null,
      session.durationSeconds ?? null,
      session.mimeType ?? null,
      session.audioHash ?? null,
      session.rawTranscriptPath ?? null,
      session.cleanTranscriptPath ?? null,
      session.summaryJson ?? null,
      session.status,
      session.syncStatus,
      session.lastError ?? null,
      session.latitude ?? null,
      session.longitude ?? null,
      session.placeLabel ?? null,
      session.createdAt,
      session.updatedAt,
    ],
  );
}

export function patchRecordingSession(
  recordingId: string,
  updates: Partial<Omit<RecordingSession, "id" | "createdAt">>,
): RecordingSession | null {
  const existing = getRecordingSessionById(recordingId);
  if (!existing) {
    return null;
  }
  const next: RecordingSession = {
    ...existing,
    ...updates,
    scopeKey: updates.scopeKey ?? existing.scopeKey,
    targetType: updates.targetType ?? existing.targetType,
    status: updates.status ?? existing.status,
    syncStatus: updates.syncStatus ?? existing.syncStatus,
    updatedAt: updates.updatedAt ?? new Date().toISOString(),
  };
  upsertRecordingSession(next);
  return next;
}

export function replaceRecordingSegments(recordingId: string, segments: RecordingSegment[]): void {
  const db = getDb();
  // 整体放进事务：避免崩溃/强杀时只删了旧 segments 还没写入新的，导致音频转写永久丢失。
  db.withTransactionSync(() => {
    db.runSync("DELETE FROM recording_segments WHERE recording_id = ?", [recordingId]);
    for (const segment of segments) {
      db.runSync(
        `INSERT OR REPLACE INTO recording_segments (
          id, recording_id, segment_index, start_ms, end_ms, text, confidence, is_final, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        [
          segment.id,
          segment.recordingId,
          segment.segmentIndex,
          segment.startMs,
          segment.endMs ?? null,
          segment.text,
          segment.confidence ?? null,
          segment.isFinal ? 1 : 0,
          segment.createdAt,
        ],
      );
    }
  });
}

export function getRecordingSessionById(recordingId: string): RecordingSession | null {
  const db = getDb();
  const row = db.getFirstSync("SELECT * FROM recording_sessions WHERE id = ? LIMIT 1", [recordingId]);
  return row ? rowToRecordingSession(row) : null;
}

export function getRecordingSegments(recordingId: string): RecordingSegment[] {
  const db = getDb();
  const rows = db.getAllSync(
    "SELECT * FROM recording_segments WHERE recording_id = ? ORDER BY segment_index ASC",
    [recordingId],
  );
  return rows.map(rowToRecordingSegment);
}

export function listRecordingSessionsForTarget(
  targetType: RecordingTargetType,
  targetLocalId?: string | null,
  targetRemoteId?: string | null,
): RecordingSession[] {
  const db = getDb();
  const rows = db.getAllSync(
    `SELECT * FROM recording_sessions
      WHERE target_type = ?
        AND (
          (? IS NOT NULL AND target_local_id = ?)
          OR (? IS NOT NULL AND target_remote_id = ?)
        )
      ORDER BY created_at DESC`,
    [
      targetType,
      targetLocalId ?? null,
      targetLocalId ?? null,
      targetRemoteId ?? null,
      targetRemoteId ?? null,
    ],
  );
  return rows.map(rowToRecordingSession);
}

export function deleteRecordingSession(recordingId: string): void {
  const db = getDb();
  // 先删段(防 FK pragma 未开时残留)，再删主记录。文件清理在 service 层做。
  db.runSync("DELETE FROM recording_segments WHERE recording_id = ?", [recordingId]);
  db.runSync("DELETE FROM recording_sessions WHERE id = ?", [recordingId]);
}

export function listUnboundRecordingSessions(limit: number = 20): RecordingSession[] {
  const db = getDb();
  const scopeKey = getActiveAccountScopeKey() ?? NO_ACCOUNT_SCOPE_KEY;
  const rows = db.getAllSync(
    `SELECT * FROM recording_sessions
      WHERE target_type = 'unbound'
        AND scope_key = ?
      ORDER BY created_at DESC
      LIMIT ?`,
    [scopeKey, Math.max(1, limit)],
  );
  return rows.map(rowToRecordingSession);
}

export function listPendingRecordingTextSync(limit: number = 20): RecordingSession[] {
  const db = getDb();
  const rows = db.getAllSync(
    `SELECT * FROM recording_sessions
      WHERE sync_status IN ('pending', 'failed')
        AND target_type <> 'unbound'
        AND clean_transcript_path IS NOT NULL
      ORDER BY updated_at ASC
      LIMIT ?`,
    [Math.max(1, limit)],
  );
  return rows.map(rowToRecordingSession);
}

export function markRecordingTextSyncState(
  recordingId: string,
  syncStatus: RecordingSyncStatus,
  lastError: string | null = null,
): RecordingSession | null {
  return patchRecordingSession(recordingId, {
    syncStatus,
    lastError,
    updatedAt: new Date().toISOString(),
  });
}

export function getRecordingDiagnostics(): {
  total: number;
  pendingTextSync: number;
  failedTextSync: number;
  needsAction: number;
  latestError: string | null;
} {
  const db = getDb();
  const total = db.getFirstSync<{ cnt: number }>("SELECT COUNT(*) as cnt FROM recording_sessions")?.cnt ?? 0;
  const pendingTextSync =
    db.getFirstSync<{ cnt: number }>(
      "SELECT COUNT(*) as cnt FROM recording_sessions WHERE sync_status IN ('pending', 'syncing')",
    )?.cnt ?? 0;
  const failedTextSync =
    db.getFirstSync<{ cnt: number }>(
      "SELECT COUNT(*) as cnt FROM recording_sessions WHERE sync_status = 'failed'",
    )?.cnt ?? 0;
  const needsAction =
    db.getFirstSync<{ cnt: number }>(
      "SELECT COUNT(*) as cnt FROM recording_sessions WHERE status IN ('asr_failed', 'needs_action')",
    )?.cnt ?? 0;
  const latestErrorRow = db.getFirstSync<{ last_error?: string | null }>(
    `SELECT last_error FROM recording_sessions
      WHERE last_error IS NOT NULL AND last_error <> ''
      ORDER BY updated_at DESC
      LIMIT 1`,
  );
  return {
    total,
    pendingTextSync,
    failedTextSync,
    needsAction,
    latestError: latestErrorRow?.last_error ?? null,
  };
}

export function getTaskServerShadow(taskId: string): TaskServerShadowRecord | null {
  const db = getDb();
  const row = db.getFirstSync(
    "SELECT * FROM task_server_shadow WHERE task_id = ? LIMIT 1",
    [taskId],
  ) as any;
  if (!row?.payload_json) {
    return null;
  }
  // payload_json 历史上有可能被磁盘满、强杀等场景写成损坏字符串。
  // 不在这里抛错——否则 reconcileTaskServerAck → pullFromCloud 会整个崩，
  // 任务会永远卡在 syncing。损坏时按 shadow 不存在处理，让下次拉取重建。
  let payload: TaskRecord;
  try {
    payload = JSON.parse(row.payload_json) as TaskRecord;
  } catch (error) {
    console.warn("[local-db] getTaskServerShadow: payload_json corrupted, treating as missing", {
      taskId,
      error: error instanceof Error ? error.message : String(error),
    });
    return null;
  }
  return {
    taskId: row.task_id,
    remoteId: row.remote_id ?? null,
    serverVersion: row.server_version ?? null,
    payload,
    updatedAt: row.updated_at,
  };
}

export function setTaskRemoteState(
  taskId: string,
  remoteState: RemoteMutationState,
  reasonCode: SyncReasonCode | null = null,
): void {
  const db = getDb();
  db.runSync(
    "UPDATE tasks SET remote_state = ?, sync_reason_code = ? WHERE id = ?",
    [remoteState, reasonCode, taskId],
  );
}

export function updateTaskSyncMetadata(
  taskId: string,
  updates: {
    remoteId?: string | null;
    serverVersion?: number | null;
    baseRemoteVersion?: number | null;
    remoteState?: RemoteMutationState;
    syncReasonCode?: SyncReasonCode | null;
    synced?: boolean;
  },
): void {
  const db = getDb();
  db.runSync(
    `UPDATE tasks
        SET remote_id = COALESCE(?, remote_id),
            server_version = COALESCE(?, server_version),
            base_remote_version = CASE
              WHEN ? IS NOT NULL THEN ?
              ELSE base_remote_version
            END,
            remote_state = COALESCE(?, remote_state),
            sync_reason_code = ?,
            _synced = CASE
              WHEN ? IS NULL THEN _synced
              WHEN ? = 1 THEN 1
              ELSE 0
            END
      WHERE id = ?`,
    [
      updates.remoteId ?? null,
      updates.serverVersion ?? null,
      updates.baseRemoteVersion ?? null,
      updates.baseRemoteVersion ?? null,
      updates.remoteState ?? null,
      updates.syncReasonCode ?? null,
      updates.synced == null ? null : updates.synced ? 1 : 0,
      updates.synced == null ? null : updates.synced ? 1 : 0,
      taskId,
    ],
  );
}

export function updatePendingOpsRemoteMapping(
  entityType: string,
  entityId: string,
  remoteId: string,
  options?: {
    promoteCreateToUpdate?: boolean;
    baseRemoteVersion?: number | null;
  },
): void {
  const db = getDb();
  db.runSync(
    `UPDATE pending_ops
        SET entity_remote_id = ?,
            operation = CASE
              WHEN ? = 1 AND operation = 'create' THEN 'update'
              ELSE operation
            END,
            base_remote_version = CASE
              WHEN ? IS NOT NULL THEN ?
              ELSE base_remote_version
            END,
            updated_at = datetime('now')
      WHERE entity_type = ?
        AND entity_id = ?`,
    [
      remoteId,
      options?.promoteCreateToUpdate ? 1 : 0,
      options?.baseRemoteVersion ?? null,
      options?.baseRemoteVersion ?? null,
      entityType,
      entityId,
    ],
  );
}

export function replaceTaskWithServerState(localTaskId: string, serverTask: TaskRecord): void {
  const db = getDb();
  const existing = getTaskById(localTaskId);
  upsertTaskRow(
    db,
    {
      ...(existing ?? {}),
      ...serverTask,
      id: localTaskId,
      remoteId: serverTask.remoteId ?? serverTask.id,
      localVersion: existing?.localVersion ?? 0,
      baseRemoteVersion: null,
      serverVersion: serverTask.serverVersion ?? existing?.serverVersion ?? null,
      localState: "local_committed",
      remoteState: "synced",
      syncReasonCode: null,
      deletedAt: null,
    },
    { synced: true, deleted: false, localUpdatedAt: null },
  );
  clearTaskServerShadowWithDb(db, localTaskId);
}

export function purgeTask(taskId: string): void {
  const db = getDb();
  db.runSync("DELETE FROM tasks WHERE id = ?", [taskId]);
  clearTaskServerShadowWithDb(db, taskId);
}

export function reconcileTaskServerAck(params: {
  taskId: string;
  clientOpId: string;
  operation: PendingOpOperation;
  ackLocalVersion: number | null;
  serverTask: TaskRecord;
}): {
  appliedServerState: boolean;
  shadowOnly: boolean;
} {
  const db = getDb();
  const existing = getTaskById(params.taskId);
  const pendingRows = db.getAllSync(
    `SELECT client_op_id, operation
       FROM pending_ops
      WHERE entity_type = 'task'
        AND entity_id = ?`,
    [params.taskId],
  ) as Array<{ client_op_id: string; operation: PendingOpOperation }>;
  const hasPendingOps = pendingRows.some((row) => row.client_op_id !== params.clientOpId);
  const pendingCreateExists = pendingRows.some(
    (row) => row.client_op_id !== params.clientOpId && row.operation === "create",
  );
  const decision = decideTaskServerAckAction({
    localTask: existing,
    ackLocalVersion: params.ackLocalVersion,
    hasPendingOps,
    pendingCreateExists,
  });
  const remoteId = params.serverTask.remoteId ?? params.serverTask.id;

  db.withTransactionSync(() => {
    if (decision.shouldUpdateShadowOnly) {
      upsertTaskServerShadowWithDb(db, params.taskId, {
        ...params.serverTask,
        remoteId,
      });
      updateTaskSyncMetadata(params.taskId, {
        remoteId,
        serverVersion: params.serverTask.serverVersion ?? null,
        remoteState: "queued",
        syncReasonCode: null,
        synced: false,
      });
      updatePendingOpsRemoteMapping("task", params.taskId, remoteId, {
        promoteCreateToUpdate: params.operation === "create" && decision.shouldPromotePendingCreate,
        baseRemoteVersion: params.serverTask.serverVersion ?? null,
      });
      return;
    }

    replaceTaskWithServerState(params.taskId, {
      ...params.serverTask,
      remoteId,
    });
  });

  return {
    appliedServerState: decision.shouldReplaceLocalTask,
    shadowOnly: decision.shouldUpdateShadowOnly,
  };
}

// ─── Task Queries ───────────────────────────────

/**
 * 获取所有活跃（非已删除）任务，等效于 fetchTaskBoard
 */
export function getAllTasks(options?: { syncedOnly?: boolean }): TaskRecord[] {
  return measureDevSync("local-db", "getAllTasks", () => {
    const db = getDb();
    const rows = db.getAllSync(
      `SELECT * FROM tasks
        WHERE _deleted = 0
          AND (? = 0 OR _synced = 1)
        ORDER BY COALESCE(scheduled_start_at, deadline_at, due_date) ASC, updated_at ASC, created_at ASC, id ASC`,
      [options?.syncedOnly ? 1 : 0],
    );
    return rows.map(rowToTask);
  });
}

/**
 * 获取指定日期的任务（日历核心查询）
 */
export function getTasksByDate(dateKey: string): TaskRecord[] {
  return measureDevSync("local-db", "getTasksByDate", () => {
    return getAllTasks().filter((task) => getTaskCalendarDateKey(task) === dateKey);
  });
}

/**
 * 获取日期范围内的任务（月视图/周视图查询）
 */
export function getTasksByDateRange(startDate: string, endDate: string): TaskRecord[] {
  return measureDevSync("local-db", "getTasksByDateRange", () => {
    return getAllTasks().filter((task) => {
      const dateKey = getTaskCalendarDateKey(task);
      return Boolean(dateKey && dateKey >= startDate && dateKey < endDate);
    });
  });
}

/**
 * 获取待同步的任务
 */
export function getUnsyncedTasks(): TaskRecord[] {
  return measureDevSync("local-db", "getUnsyncedTasks", () => {
    const db = getDb();
    const rows = db.getAllSync("SELECT * FROM tasks WHERE _synced = 0 AND _deleted = 0");
    return rows.map(rowToTask);
  });
}

/**
 * 获取 inbox 计数和今日任务计数
 */
export function getTaskCounts(options?: { syncedOnly?: boolean }): { inboxCount: number; tasksTodayCount: number } {
  return measureDevSync("local-db", "getTaskCounts", () => {
    const db = getDb();
    const today = formatLocalDateKey(new Date());

    const inboxRow = db.getFirstSync<{ cnt: number }>(
      "SELECT COUNT(*) as cnt FROM tasks WHERE _deleted = 0 AND progress_status = 'inbox' AND (? = 0 OR _synced = 1)",
      [options?.syncedOnly ? 1 : 0],
    );
    const tasksTodayCount = getAllTasks(options).filter((task) => getTaskCalendarDateKey(task) === today).length;

    return {
      inboxCount: inboxRow?.cnt ?? 0,
      tasksTodayCount,
    };
  });
}

/**
 * 构建与云端 API 兼容的 TaskBoardResponse
 */
export function getLocalTaskBoard(options?: { syncedOnly?: boolean }): TaskBoardResponse {
  const tasks = getAllTasks(options);
  const counts = getTaskCounts(options);
  return {
    tasks,
    inboxCount: counts.inboxCount,
    tasksTodayCount: counts.tasksTodayCount,
  };
}

// ─── Event Lines ────────────────────────────────

export function upsertEventLinesFromCloud(lines: EventLineRecord[]): void {
  const db = getDb();
  db.withTransactionSync(() => {
    db.runSync("DELETE FROM event_lines WHERE _synced = 1");
    const stmt = db.prepareSync(`
      INSERT OR REPLACE INTO event_lines (id, name, primary_client_id, primary_client_name,
        summary, current_blocker, next_step, recent_decision, stage, status, _synced)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
    `);
    try {
      for (const l of lines) {
        stmt.executeSync([
          l.id, l.name, l.primaryClientId ?? null, l.primaryClientName ?? null,
          l.summary ?? null, l.currentBlocker ?? null, l.nextStep ?? null,
          l.recentDecision ?? null, l.stage ?? null, l.status ?? null,
        ]);
      }
    } finally {
      stmt.finalizeSync();
    }
  });
  setSyncMeta("event_lines_last_sync", new Date().toISOString());
}

export function getAllEventLines(): EventLineRecord[] {
  const db = getDb();
  const rows = db.getAllSync("SELECT * FROM event_lines");
  return rows.map((r: any) => ({
    id: r.id,
    name: r.name,
    primaryClientId: r.primary_client_id,
    primaryClientName: r.primary_client_name,
    summary: r.summary,
    currentBlocker: r.current_blocker,
    nextStep: r.next_step,
    recentDecision: r.recent_decision,
    stage: r.stage,
    status: r.status,
  }));
}

// ─── Clients ────────────────────────────────────

export function upsertClientsFromCloud(clients: ClientSummaryRecord[]): void {
  const db = getDb();
  db.withTransactionSync(() => {
    db.runSync("DELETE FROM clients WHERE _synced = 1");
    const stmt = db.prepareSync(
      "INSERT OR REPLACE INTO clients (id, name, alias, _synced) VALUES (?, ?, ?, 1)",
    );
    try {
      for (const c of clients) {
        stmt.executeSync([c.id, c.name, c.alias ?? null]);
      }
    } finally {
      stmt.finalizeSync();
    }
  });
  setSyncMeta("clients_last_sync", new Date().toISOString());
}

export function getAllClients(): ClientSummaryRecord[] {
  const db = getDb();
  const rows = db.getAllSync("SELECT * FROM clients");
  return rows.map((r: any) => ({ id: r.id, name: r.name, alias: r.alias }));
}

// ─── Task Lists ─────────────────────────────────

export function upsertTaskListsFromCloud(lists: TaskListRecord[]): void {
  const db = getDb();
  db.withTransactionSync(() => {
    db.runSync("DELETE FROM task_lists WHERE _synced = 1");
    const stmt = db.prepareSync(
      "INSERT OR REPLACE INTO task_lists (id, name, color, is_default, _synced) VALUES (?, ?, ?, ?, 1)",
    );
    try {
      for (const l of lists) {
        stmt.executeSync([l.id, l.name, l.color ?? null, l.isDefault ? 1 : 0]);
      }
    } finally {
      stmt.finalizeSync();
    }
  });
}

// ─── Pending Ops (离线操作队列) ─────────────────

function rowToPendingOp(row: any): PendingOpRecord {
  return {
    id: row.id,
    clientOpId: row.client_op_id,
    entityType: row.entity_type,
    entityId: row.entity_id,
    entityRemoteId: row.entity_remote_id,
    operation: row.operation,
    payload: row.payload,
    lane: row.lane,
    status: row.status,
    visibilityScope: row.visibility_scope,
    localVersion: row.local_version ?? 0,
    baseRemoteVersion: row.base_remote_version,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
    retryCount: row.retry_count,
    lastError: row.last_error,
    reasonCode: row.reason_code ?? null,
  };
}

function pendingOpToDraft(op: PendingOpRecord): PendingOpDraft {
  // op.payload 是 raw JSON 字符串。损坏时不抛错——否则 folding 链路会让整个
  // pushPendingOps 崩，所有 op 卡死。损坏时把 payload 设为 null，pushPendingOps
  // 自己会处理空 payload（创建/更新会因缺字段失败、标 needs_attention）。
  let payload: Record<string, unknown> | null = null;
  if (op.payload) {
    try {
      payload = JSON.parse(op.payload);
    } catch (error) {
      console.warn("[local-db] pendingOpToDraft: payload corrupted, dropping", {
        opId: op.id,
        entityType: op.entityType,
        entityId: op.entityId,
        error: error instanceof Error ? error.message : String(error),
      });
    }
  }
  return {
    clientOpId: op.clientOpId,
    entityType: op.entityType,
    entityId: op.entityId,
    entityRemoteId: op.entityRemoteId ?? null,
    operation: op.operation,
    payload,
    lane: op.lane,
    status: op.status,
    visibilityScope: op.visibilityScope,
    localVersion: op.localVersion,
    baseRemoteVersion: op.baseRemoteVersion ?? null,
  };
}

function replacePendingOpsForEntity(
  db: SQLite.SQLiteDatabase,
  entityType: string,
  entityId: string,
  drafts: readonly PendingOpDraft[],
): void {
  db.runSync(
    "DELETE FROM pending_ops WHERE entity_type = ? AND entity_id = ?",
    [entityType, entityId],
  );
  for (const op of drafts) {
    db.runSync(
      `INSERT INTO pending_ops (
        client_op_id, entity_type, entity_id, entity_remote_id, operation, payload,
        lane, status, visibility_scope, local_version, base_remote_version,
        created_at, updated_at, retry_count, last_error, reason_code
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'), 0, NULL, NULL)`,
      [
        op.clientOpId,
        op.entityType,
        op.entityId,
        op.entityRemoteId ?? null,
        op.operation,
        op.payload ? JSON.stringify(op.payload) : null,
        op.lane,
        op.status,
        op.visibilityScope,
        op.localVersion,
        op.baseRemoteVersion ?? null,
      ],
    );
  }
}

function getPendingOpDraftsForEntity(
  db: SQLite.SQLiteDatabase,
  entityType: string,
  entityId: string,
): PendingOpDraft[] {
  const rows = db.getAllSync(
    "SELECT * FROM pending_ops WHERE entity_type = ? AND entity_id = ? ORDER BY created_at ASC, id ASC",
    [entityType, entityId],
  );
  return rows.map((row: any) => pendingOpToDraft(rowToPendingOp(row)));
}

export function enqueueOp(
  entityType: string,
  entityId: string,
  operation: "create" | "update" | "delete",
  payload?: Record<string, unknown>,
  options?: {
    clientOpId?: string;
    entityRemoteId?: string | null;
    lane?: PendingOpLane;
    visibilityScope?: PendingOpVisibilityScope;
    localVersion?: number;
    baseRemoteVersion?: number | null;
  },
): void {
  const db = getDb();
  const nextDraft: PendingOpDraft = {
    clientOpId: options?.clientOpId ?? `legacy_${entityType}_${Date.now()}`,
    entityType,
    entityId,
    entityRemoteId: options?.entityRemoteId ?? null,
    operation,
    payload: payload ?? null,
    lane: options?.lane ?? "interactive",
    status: "queued",
    visibilityScope: options?.visibilityScope ?? "team_shared",
    localVersion: options?.localVersion ?? 0,
    baseRemoteVersion: options?.baseRemoteVersion ?? null,
  };
  const existing = getPendingOpDraftsForEntity(db, entityType, entityId);
  replacePendingOpsForEntity(db, entityType, entityId, foldPendingOps(existing, nextDraft));
}

export function getPendingOps(): PendingOpRecord[] {
  const db = getDb();
  const rows = db.getAllSync(
    `SELECT * FROM pending_ops
     WHERE status != 'needs_attention'
     ORDER BY
       CASE lane
         WHEN 'interactive' THEN 0
         WHEN 'transfer' THEN 1
         ELSE 2
       END ASC,
       created_at ASC,
       id ASC`,
  );
  return rows.map((row: any) => rowToPendingOp(row));
}

export function getPendingOpsForEntity(
  entityType: string,
  entityId: string,
): PendingOpRecord[] {
  const db = getDb();
  const rows = db.getAllSync(
    `SELECT * FROM pending_ops
     WHERE entity_type = ?
       AND entity_id = ?
     ORDER BY created_at ASC, id ASC`,
    [entityType, entityId],
  );
  return rows.map((row: any) => rowToPendingOp(row));
}

export function getPendingOpsSummary(): PendingOpSummary {
  const db = getDb();
  const rows = db.getAllSync("SELECT lane, status, reason_code FROM pending_ops");
  const summary: PendingOpSummary = {
    total: rows.length,
    queued: 0,
    syncing: 0,
    processing: 0,
    needsAttention: 0,
    byLane: {
      interactive: 0,
      transfer: 0,
      derived: 0,
    },
    byReasonCode: {},
  };

  for (const row of rows as any[]) {
    if (row.lane && row.lane in summary.byLane) {
      summary.byLane[row.lane as PendingOpLane] += 1;
    }
    if (row.status === "queued") summary.queued += 1;
    if (row.status === "syncing") summary.syncing += 1;
    if (row.status === "processing") summary.processing += 1;
    if (row.status === "needs_attention") summary.needsAttention += 1;
    if (row.reason_code) {
      summary.byReasonCode[row.reason_code as SyncReasonCode] =
        (summary.byReasonCode[row.reason_code as SyncReasonCode] ?? 0) + 1;
    }
  }

  return summary;
}

export function getPendingOpsLaneDiagnostics(
  now = Date.now(),
): Record<PendingOpLane, HealthLaneDiagnostic> {
  const diagnostics: Record<PendingOpLane, HealthLaneDiagnostic> = {
    interactive: {
      lane: "interactive",
      total: 0,
      oldestAgeMs: null,
      active: false,
      topReasonCode: null,
    },
    transfer: {
      lane: "transfer",
      total: 0,
      oldestAgeMs: null,
      active: false,
      topReasonCode: null,
    },
    derived: {
      lane: "derived",
      total: 0,
      oldestAgeMs: null,
      active: false,
      topReasonCode: null,
    },
  };
  const reasonCounts: Record<PendingOpLane, Record<string, number>> = {
    interactive: {},
    transfer: {},
    derived: {},
  };
  const db = getDb();
  const rows = db.getAllSync(
    "SELECT lane, status, reason_code, created_at, updated_at FROM pending_ops",
  ) as Array<{
    lane: PendingOpLane;
    status: string;
    reason_code: string | null;
    created_at: string;
    updated_at: string | null;
  }>;

  for (const row of rows) {
    if (!row.lane || !(row.lane in diagnostics)) {
      continue;
    }
    const entry = diagnostics[row.lane];
    entry.total += 1;
    if (row.status === "syncing" || row.status === "processing") {
      entry.active = true;
    }
    const ageBaseline = row.updated_at ?? row.created_at;
    const age = Math.max(0, now - new Date(ageBaseline).getTime());
    entry.oldestAgeMs = entry.oldestAgeMs == null ? age : Math.max(entry.oldestAgeMs, age);
    if (row.reason_code) {
      reasonCounts[row.lane][row.reason_code] =
        (reasonCounts[row.lane][row.reason_code] ?? 0) + 1;
    }
  }

  (Object.keys(reasonCounts) as PendingOpLane[]).forEach((lane) => {
    let topReasonCode: string | null = null;
    let topCount = 0;
    Object.entries(reasonCounts[lane]).forEach(([reasonCode, count]) => {
      if (count > topCount) {
        topReasonCode = reasonCode;
        topCount = count;
      }
    });
    diagnostics[lane].topReasonCode = topReasonCode;
  });

  return diagnostics;
}

export function getPendingOpsDebugList(limit = 20): PendingOpRecord[] {
  const db = getDb();
  const rows = db.getAllSync(
    "SELECT * FROM pending_ops ORDER BY updated_at DESC, created_at DESC LIMIT ?",
    [limit],
  );
  return rows.map((row: any) => rowToPendingOp(row));
}

export function getTaskRemoteStateSummary(): {
  total: number;
  byRemoteState: Record<RemoteMutationState, number>;
  byReasonCode: Partial<Record<SyncReasonCode, number>>;
  recentNeedsAttentionTasks: Array<{
    id: string;
    title: string;
    remoteState: RemoteMutationState;
    syncReasonCode: SyncReasonCode | null;
    updatedAt: string | null;
  }>;
} {
  const db = getDb();
  const rows = db.getAllSync(
    `SELECT id, title, remote_state, sync_reason_code, updated_at
       FROM tasks
      WHERE _deleted = 0`,
  ) as Array<{
    id: string;
    title: string;
    remote_state: RemoteMutationState;
    sync_reason_code: SyncReasonCode | null;
    updated_at: string | null;
  }>;

  const summary = {
    total: rows.length,
    byRemoteState: {
      queued: 0,
      syncing: 0,
      processing: 0,
      needs_attention: 0,
      synced: 0,
    } as Record<RemoteMutationState, number>,
    byReasonCode: {} as Partial<Record<SyncReasonCode, number>>,
    recentNeedsAttentionTasks: [] as Array<{
      id: string;
      title: string;
      remoteState: RemoteMutationState;
      syncReasonCode: SyncReasonCode | null;
      updatedAt: string | null;
    }>,
  };

  for (const row of rows) {
    if (row.remote_state in summary.byRemoteState) {
      summary.byRemoteState[row.remote_state] += 1;
    }
    if (row.sync_reason_code) {
      summary.byReasonCode[row.sync_reason_code] =
        (summary.byReasonCode[row.sync_reason_code] ?? 0) + 1;
    }
    if (row.remote_state === "needs_attention") {
      summary.recentNeedsAttentionTasks.push({
        id: row.id,
        title: row.title,
        remoteState: row.remote_state,
        syncReasonCode: row.sync_reason_code,
        updatedAt: row.updated_at,
      });
    }
  }

  summary.recentNeedsAttentionTasks.sort((left, right) =>
    (right.updatedAt ?? "").localeCompare(left.updatedAt ?? ""),
  );
  summary.recentNeedsAttentionTasks = summary.recentNeedsAttentionTasks.slice(0, 10);

  return summary;
}

export function getTaskServerShadowDiagnostics(): {
  total: number;
  stale: number;
} {
  const db = getDb();
  const total = db.getFirstSync<{ cnt: number }>(
    "SELECT COUNT(*) as cnt FROM task_server_shadow",
  )?.cnt ?? 0;
  const stale = db.getFirstSync<{ cnt: number }>(
    `SELECT COUNT(*) as cnt
       FROM task_server_shadow shadow
       LEFT JOIN pending_ops po
         ON po.entity_type = 'task'
        AND po.entity_id = shadow.task_id
      WHERE po.id IS NULL`,
  )?.cnt ?? 0;
  return { total, stale };
}

export function cleanupSafeSyncArtifacts(): {
  clearedTaskServerShadows: number;
} {
  const db = getDb();
  const diagnostics = getTaskServerShadowDiagnostics();
  if (diagnostics.stale > 0) {
    db.runSync(
      `DELETE FROM task_server_shadow
        WHERE task_id NOT IN (
          SELECT DISTINCT entity_id
            FROM pending_ops
           WHERE entity_type = 'task'
        )`,
    );
  }
  return {
    clearedTaskServerShadows: diagnostics.stale,
  };
}

export function getTaskConflictDiagnostics(limit = 10): TaskConflictDiagnostic[] {
  const db = getDb();
  const rows = db.getAllSync(
    `SELECT
        po.entity_id as task_id,
        po.operation as pending_operation,
        po.updated_at as pending_updated_at,
        po.last_error as last_error,
        po.reason_code as pending_reason_code,
        t.title as title,
        t.remote_state as remote_state,
        t.sync_reason_code as task_reason_code,
        shadow.updated_at as shadow_updated_at,
        shadow.server_version as shadow_server_version
      FROM pending_ops po
      INNER JOIN tasks t
        ON t.id = po.entity_id
      LEFT JOIN task_server_shadow shadow
        ON shadow.task_id = t.id
      WHERE po.entity_type = 'task'
        AND po.status = 'needs_attention'
        AND (
          po.reason_code = 'version_conflict'
          OR t.sync_reason_code = 'version_conflict'
        )
      ORDER BY po.updated_at DESC, po.id DESC`,
  ) as Array<{
    task_id: string;
    pending_operation: PendingOpOperation | null;
    pending_updated_at: string | null;
    last_error: string | null;
    pending_reason_code: SyncReasonCode | null;
    title: string | null;
    remote_state: RemoteMutationState;
    task_reason_code: SyncReasonCode | null;
    shadow_updated_at: string | null;
    shadow_server_version: number | null;
  }>;

  const diagnostics = new Map<string, TaskConflictDiagnostic>();

  for (const row of rows) {
    const existing = diagnostics.get(row.task_id);
    if (existing) {
      existing.pendingOpCount += 1;
      if (!existing.hasServerShadow && row.shadow_updated_at) {
        existing.hasServerShadow = true;
        existing.serverShadowUpdatedAt = row.shadow_updated_at;
        existing.serverVersion = row.shadow_server_version ?? null;
      }
      continue;
    }

    diagnostics.set(row.task_id, {
      taskId: row.task_id,
      title: row.title?.trim() || "未命名任务",
      remoteState: row.remote_state ?? "needs_attention",
      syncReasonCode: row.pending_reason_code ?? row.task_reason_code ?? null,
      pendingOperation: row.pending_operation ?? null,
      pendingUpdatedAt: row.pending_updated_at ?? null,
      pendingOpCount: 1,
      lastError: row.last_error ?? null,
      hasServerShadow: Boolean(row.shadow_updated_at),
      serverShadowUpdatedAt: row.shadow_updated_at ?? null,
      serverVersion: row.shadow_server_version ?? null,
    });
  }

  return Array.from(diagnostics.values()).slice(0, Math.max(0, limit));
}

export function removeOp(opId: number): void {
  const db = getDb();
  db.runSync("DELETE FROM pending_ops WHERE id = ?", [opId]);
}

export function markOpSyncing(opId: number): void {
  const db = getDb();
  db.runSync(
    "UPDATE pending_ops SET status = 'syncing', updated_at = datetime('now'), reason_code = NULL, last_error = NULL WHERE id = ?",
    [opId],
  );
}

export function markOpFailed(
  opId: number,
  error: string,
  reasonCode: SyncReasonCode,
  status: RemoteMutationState = "queued",
): void {
  const db = getDb();
  db.runSync(
    `UPDATE pending_ops
     SET retry_count = retry_count + 1,
         last_error = ?,
         reason_code = ?,
         status = ?,
         updated_at = datetime('now')
     WHERE id = ?`,
    [error, reasonCode, status, opId],
  );
}

export function requeueOp(opId: number): void {
  const db = getDb();
  const row = db.getFirstSync<{ entity_id: string; entity_type: string }>(
    "SELECT entity_id, entity_type FROM pending_ops WHERE id = ?",
    [opId],
  );
  db.runSync(
    // retry_count = 0：用户手动重试 = 给一次干净的重试额度。不清零的话 retry_count≥MAX_OP_RETRIES
    // 的 op 在 pushPendingOps 开头(:467)会被直接判失败跳过、根本不发起网络请求，requeue 形同虚设。
    "UPDATE pending_ops SET status = 'queued', retry_count = 0, reason_code = NULL, last_error = NULL, updated_at = datetime('now') WHERE id = ?",
    [opId],
  );
  if (row?.entity_type === "task") {
    setTaskRemoteState(row.entity_id, "queued", null);
  }
}

export function requeueAllNeedsAttentionOps(): void {
  const db = getDb();
  const rows = db.getAllSync(
    "SELECT entity_id, entity_type FROM pending_ops WHERE status = 'needs_attention'",
  );
  db.runSync(
    // retry_count = 0：见 requeueOp 注释——手动重试必须清零重试计数，否则会被 :467 直接跳过。
    "UPDATE pending_ops SET status = 'queued', retry_count = 0, reason_code = NULL, last_error = NULL, updated_at = datetime('now') WHERE status = 'needs_attention'",
  );
  for (const row of rows as any[]) {
    if (row.entity_type === "task") {
      setTaskRemoteState(row.entity_id, "queued", null);
    }
  }
}

export function requeueNeedsAttentionOpsForEntity(
  entityType: string,
  entityId: string,
): number {
  const db = getDb();
  const count = db.getFirstSync<{ cnt: number }>(
    `SELECT COUNT(*) as cnt
       FROM pending_ops
      WHERE entity_type = ?
        AND entity_id = ?
        AND status = 'needs_attention'`,
    [entityType, entityId],
  )?.cnt ?? 0;
  if (count === 0) {
    return 0;
  }

  db.runSync(
    // retry_count = 0：见 requeueOp 注释——手动重试必须清零重试计数，否则会被 :467 直接跳过。
    `UPDATE pending_ops
        SET status = 'queued',
            retry_count = 0,
            reason_code = NULL,
            last_error = NULL,
            updated_at = datetime('now')
      WHERE entity_type = ?
        AND entity_id = ?
        AND status = 'needs_attention'`,
    [entityType, entityId],
  );
  if (entityType === "task") {
    setTaskRemoteState(entityId, "queued", null);
  }
  return count;
}

export function restoreTaskFromServerShadow(taskId: string): {
  restored: boolean;
  clearedPendingOps: number;
} {
  const db = getDb();
  const shadow = getTaskServerShadow(taskId);
  if (!shadow) {
    return { restored: false, clearedPendingOps: 0 };
  }

  const clearedPendingOps = db.getFirstSync<{ cnt: number }>(
    `SELECT COUNT(*) as cnt
       FROM pending_ops
      WHERE entity_type = 'task'
        AND entity_id = ?`,
    [taskId],
  )?.cnt ?? 0;

  db.withTransactionSync(() => {
    db.runSync(
      `DELETE FROM pending_ops
        WHERE entity_type = 'task'
          AND entity_id = ?`,
      [taskId],
    );
    replaceTaskWithServerState(taskId, shadow.payload);
  });

  return {
    restored: true,
    clearedPendingOps,
  };
}

export function commitTaskMutation(params: {
  task: TaskRecord;
  operation: "create" | "update" | "delete";
  clientOpId: string;
  payload: Record<string, unknown> | null;
  lane?: PendingOpLane;
  visibilityScope?: PendingOpVisibilityScope;
}): void {
  const db = getDb();
  const deleted = params.operation === "delete";
  const localUpdatedAt = new Date().toISOString();

  db.withTransactionSync(() => {
    upsertTaskRow(
      db,
      {
        ...params.task,
        localState: "local_committed",
        remoteState: "queued",
        syncReasonCode: null,
        deletedAt: deleted ? params.task.deletedAt ?? localUpdatedAt : null,
      },
      { synced: false, deleted, localUpdatedAt },
    );

    const nextDraft: PendingOpDraft = {
      clientOpId: params.clientOpId,
      entityType: "task",
      entityId: params.task.id,
      entityRemoteId: params.task.remoteId ?? null,
      operation: params.operation,
      payload: params.payload,
      lane: params.lane ?? "interactive",
      status: "queued",
      visibilityScope: params.visibilityScope ?? "team_shared",
      localVersion: params.task.localVersion ?? 0,
      baseRemoteVersion: params.task.baseRemoteVersion ?? null,
    };
    const existing = getPendingOpDraftsForEntity(db, "task", params.task.id);
    const nextOps = foldPendingOps(existing, nextDraft);
    replacePendingOpsForEntity(db, "task", params.task.id, nextOps);
  });
}

export function commitTaskReviewMutation(params: {
  task: TaskRecord;
  clientOpId: string;
  reviewNote: string;
  visibilityScope?: PendingOpVisibilityScope;
}): void {
  const db = getDb();
  const localUpdatedAt = new Date().toISOString();

  db.withTransactionSync(() => {
    upsertTaskRow(
      db,
      {
        ...params.task,
        localState: "local_committed",
        remoteState: "queued",
        syncReasonCode: null,
        deletedAt: null,
      },
      { synced: false, deleted: false, localUpdatedAt },
    );

    const existingRows = db.getAllSync(
      `SELECT * FROM pending_ops
        WHERE entity_type = 'task'
          AND entity_id = ?
        ORDER BY created_at ASC`,
      [params.task.id],
    ) as any[];

    const hasDeletePending = existingRows.some((row) => row.operation === "delete");
    if (hasDeletePending) {
      return;
    }

    const baseOps = existingRows
      .map((row) => rowToPendingOp(row))
      .filter((op) => op.operation !== "complete_with_review");

    db.runSync(
      `DELETE FROM pending_ops
        WHERE entity_type = 'task'
          AND entity_id = ?
          AND operation = 'complete_with_review'`,
      [params.task.id],
    );

    if (baseOps.length === 0) {
      db.runSync(
        `INSERT INTO pending_ops (
          client_op_id, entity_type, entity_id, entity_remote_id, operation, payload,
          lane, status, visibility_scope, local_version, base_remote_version,
          created_at, updated_at, retry_count, last_error, reason_code
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'), 0, NULL, NULL)`,
        [
          params.clientOpId,
          "task",
          params.task.id,
          params.task.remoteId ?? null,
          "complete_with_review",
          JSON.stringify({ reviewNote: params.reviewNote }),
          "interactive",
          "queued",
          params.visibilityScope ?? "official",
          params.task.localVersion ?? 0,
          params.task.baseRemoteVersion ?? null,
        ],
      );
      return;
    }

    db.runSync(
      `INSERT INTO pending_ops (
        client_op_id, entity_type, entity_id, entity_remote_id, operation, payload,
        lane, status, visibility_scope, local_version, base_remote_version,
        created_at, updated_at, retry_count, last_error, reason_code
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'), 0, NULL, NULL)`,
      [
        params.clientOpId,
        "task",
        params.task.id,
        params.task.remoteId ?? null,
        "complete_with_review",
        JSON.stringify({ reviewNote: params.reviewNote }),
        "interactive",
        "queued",
        params.visibilityScope ?? "official",
        params.task.localVersion ?? 0,
        params.task.baseRemoteVersion ?? null,
      ],
    );
  });
}

// ─── Sync Meta ──────────────────────────────────

export function getSyncMeta(key: string): string | null {
  const db = getDb();
  const row = db.getFirstSync<{ value: string }>(
    "SELECT value FROM sync_meta WHERE key = ?",
    [key],
  );
  return row?.value ?? null;
}

export function setSyncMeta(key: string, value: string): void {
  const db = getDb();
  db.runSync(
    `INSERT OR REPLACE INTO sync_meta (key, value, updated_at)
     VALUES (?, ?, datetime('now'))`,
    [key, value],
  );
}

// ─── Cleanup ────────────────────────────────────

/**
 * 清除所有本地数据（登出时调用）
 */
export function clearAllData(): void {
  const db = getDb();
  db.withTransactionSync(() => {
    clearSessionDataWithDb(db);
    db.runSync("DELETE FROM sync_meta");
  });
  _activeAccountScopeKey = null;
}

/**
 * 检查本地数据库是否有数据（用于判断是否首次加载）
 */
export function hasLocalData(): boolean {
  const db = getDb();
  const row = db.getFirstSync<{ cnt: number }>(
    "SELECT COUNT(*) as cnt FROM tasks",
  );
  return (row?.cnt ?? 0) > 0;
}
