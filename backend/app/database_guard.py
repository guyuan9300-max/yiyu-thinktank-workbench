from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import time
from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.db import BACKEND_SCHEMA_VERSION, Database


DEFAULT_MIGRATION_BACKUPS_TO_KEEP = 3
DEFAULT_MIGRATION_LOCK_TIMEOUT_SECONDS = 20.0
_ATTEMPT_FORMAT_VERSION = 1
_PRIVATE_DIRECTORY_MODE = 0o700
_PRIVATE_FILE_MODE = 0o600
_RECOVERY_TABLES = (
    "task_tags__stage5_global_unique_backup",
    "task_settings__sandbox_scope_backup",
    "task_tags__scope_rebuild_new",
    "task_settings__scope_rebuild_new",
)


class DatabaseMigrationGuardError(RuntimeError):
    """The database cannot be opened without crossing a safe migration boundary."""


class DatabaseDowngradeBlockedError(DatabaseMigrationGuardError):
    """An older backend attempted to open a database with a newer schema."""


@dataclass(frozen=True)
class DatabaseMigrationInspection:
    exists: bool
    schema_version: int
    reasons: tuple[str, ...]

    @property
    def needs_migration(self) -> bool:
        return self.exists and bool(self.reasons)


def _path_identity(db_path: Path) -> str:
    return hashlib.sha256(str(db_path.resolve()).encode("utf-8")).hexdigest()[:12]


def _backup_prefix(db_path: Path) -> str:
    return f"{db_path.stem}-pre-migrate-"


def _backup_dir(data_dir: Path) -> Path:
    return data_dir / "backups" / "migrations"


def _attempt_path(data_dir: Path, db_path: Path) -> Path:
    return _backup_dir(data_dir) / f".{db_path.name}-migration-attempt-{_path_identity(db_path)}.json"


def _lock_path(data_dir: Path, db_path: Path) -> Path:
    return _backup_dir(data_dir) / f".{db_path.name}-migration-{_path_identity(db_path)}.lock"


def _ensure_private_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=_PRIVATE_DIRECTORY_MODE)
    path.chmod(_PRIVATE_DIRECTORY_MODE)


def _create_private_file(path: Path) -> None:
    flags = os.O_RDWR | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    descriptor = os.open(path, flags, _PRIVATE_FILE_MODE)
    os.close(descriptor)


def _sqlite_file_paths(db_path: Path) -> tuple[Path, ...]:
    return (
        db_path,
        db_path.with_name(f"{db_path.name}-wal"),
        db_path.with_name(f"{db_path.name}-shm"),
        db_path.with_name(f"{db_path.name}-journal"),
    )


def _harden_existing_sqlite_files(db_path: Path) -> None:
    for private_path in _sqlite_file_paths(db_path):
        try:
            private_path.chmod(_PRIVATE_FILE_MODE)
        except FileNotFoundError:
            pass


def _connect_read_only(db_path: Path) -> sqlite3.Connection:
    uri = f"{db_path.resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=5.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _table_columns(conn: sqlite3.Connection, table_name: str) -> dict[str, sqlite3.Row]:
    return {
        str(row["name"]): row
        for row in conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
    }


def _has_unique_index_on(
    conn: sqlite3.Connection,
    table_name: str,
    expected_columns: tuple[str, ...],
) -> bool:
    for row in conn.execute(f'PRAGMA index_list("{table_name}")').fetchall():
        if not bool(row["unique"]):
            continue
        index_name = str(row["name"])
        columns = tuple(
            str(item["name"])
            for item in conn.execute(f'PRAGMA index_info("{index_name}")').fetchall()
        )
        if columns == expected_columns:
            return True
    return False


def _task_settings_has_expected_foreign_keys(conn: sqlite3.Connection) -> bool:
    expected = {
        ("operator_id", "operators", "id", "CASCADE"),
        ("default_list_id", "task_lists", "id", "SET NULL"),
    }
    actual = {
        (
            str(row["from"]),
            str(row["table"]),
            str(row["to"]),
            str(row["on_delete"]).upper(),
        )
        for row in conn.execute('PRAGMA foreign_key_list("task_settings")').fetchall()
    }
    return expected.issubset(actual)


def _structural_migration_reasons(conn: sqlite3.Connection) -> list[str]:
    reasons: list[str] = []
    table_names = {
        str(row["name"])
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    recovery_tables = sorted(table_names.intersection(_RECOVERY_TABLES))
    if recovery_tables:
        reasons.append(f"recovery_tables:{','.join(recovery_tables)}")

    if "task_tags" not in table_names:
        reasons.append("task_tags_missing")
    else:
        tag_columns = _table_columns(conn, "task_tags")
        if "operator_id" not in tag_columns:
            reasons.append("task_tags_operator_id_missing")
        if _has_unique_index_on(conn, "task_tags", ("name",)):
            reasons.append("task_tags_global_name_unique")

    if "task_settings" not in table_names:
        reasons.append("task_settings_missing")
    else:
        setting_columns = _table_columns(conn, "task_settings")
        has_composite_pk = (
            int(setting_columns.get("sandbox_id", {"pk": 0})["pk"] or 0) == 1
            and int(setting_columns.get("operator_id", {"pk": 0})["pk"] or 0) == 2
        )
        if not has_composite_pk:
            reasons.append("task_settings_composite_pk_missing")
        if not _task_settings_has_expected_foreign_keys(conn):
            reasons.append("task_settings_foreign_keys_incomplete")
    return reasons


def inspect_database_migration_state(
    db_path: Path,
    *,
    target_schema_version: int = BACKEND_SCHEMA_VERSION,
) -> DatabaseMigrationInspection:
    db_path = Path(db_path)
    if not db_path.exists():
        return DatabaseMigrationInspection(exists=False, schema_version=0, reasons=())
    try:
        with closing(_connect_read_only(db_path)) as conn:
            schema_version = int(conn.execute("PRAGMA user_version").fetchone()[0] or 0)
            reasons = _structural_migration_reasons(conn)
    except sqlite3.Error as exc:
        raise DatabaseMigrationGuardError(
            f"无法安全检查数据库迁移状态: {db_path}: {exc}"
        ) from exc
    if schema_version < target_schema_version:
        reasons.insert(0, f"schema_version:{schema_version}<{target_schema_version}")
    return DatabaseMigrationInspection(
        exists=True,
        schema_version=schema_version,
        reasons=tuple(reasons),
    )


def _fsync_file(path: Path) -> None:
    with path.open("rb") as file_obj:
        os.fsync(file_obj.fileno())


def _fsync_directory(path: Path) -> None:
    try:
        directory_fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_sqlite_snapshot(path: Path) -> None:
    try:
        with closing(_connect_read_only(path)) as conn:
            results = conn.execute("PRAGMA quick_check").fetchall()
    except sqlite3.Error as exc:
        raise DatabaseMigrationGuardError(f"迁移备份无法打开: {path}: {exc}") from exc
    if len(results) != 1 or str(results[0][0]).lower() != "ok":
        detail = "; ".join(str(row[0]) for row in results[:5]) if results else "no result"
        raise DatabaseMigrationGuardError(f"迁移备份 quick_check 失败: {path}: {detail}")


@contextmanager
def _exclusive_migration_lock(
    data_dir: Path,
    db_path: Path,
    *,
    timeout_seconds: float = DEFAULT_MIGRATION_LOCK_TIMEOUT_SECONDS,
):
    lock_path = _lock_path(data_dir, db_path)
    _ensure_private_directory(lock_path.parent)
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, _PRIVATE_FILE_MODE)
    acquired = False
    deadline = time.monotonic() + max(0.0, timeout_seconds)
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(descriptor, _PRIVATE_FILE_MODE)
        else:
            lock_path.chmod(_PRIVATE_FILE_MODE)
        if os.name == "nt":
            import msvcrt

            if os.fstat(descriptor).st_size == 0:
                os.write(descriptor, b"0")
            while True:
                try:
                    os.lseek(descriptor, 0, os.SEEK_SET)
                    msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
                    acquired = True
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        break
                    time.sleep(0.1)
        else:
            import fcntl

            while True:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        break
                    time.sleep(0.1)
        if not acquired:
            raise DatabaseMigrationGuardError(
                "数据库正在被另一个进程初始化或迁移，请稍候再试。"
            )
        yield
    finally:
        if acquired:
            if os.name == "nt":
                import msvcrt

                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    _ensure_private_directory(path.parent)
    temp_path = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        _create_private_file(temp_path)
        with temp_path.open("w", encoding="utf-8") as file_obj:
            json.dump(payload, file_obj, ensure_ascii=False, sort_keys=True, indent=2)
            file_obj.flush()
            os.fsync(file_obj.fileno())
        os.replace(temp_path, path)
        path.chmod(_PRIVATE_FILE_MODE)
        _fsync_directory(path.parent)
    finally:
        temp_path.unlink(missing_ok=True)


def _create_consistent_sqlite_backup(db_path: Path, backup_path: Path) -> str:
    _ensure_private_directory(backup_path.parent)
    temp_path = backup_path.with_name(f".{backup_path.name}.{uuid4().hex}.tmp")
    source: sqlite3.Connection | None = None
    destination: sqlite3.Connection | None = None
    try:
        _create_private_file(temp_path)
        source = _connect_read_only(db_path)
        destination = sqlite3.connect(temp_path, isolation_level=None)
        source.backup(destination)
        destination.close()
        destination = None
        source.close()
        source = None
        _validate_sqlite_snapshot(temp_path)
        _fsync_file(temp_path)
        os.replace(temp_path, backup_path)
        backup_path.chmod(_PRIVATE_FILE_MODE)
        _fsync_directory(backup_path.parent)
        return _sha256_file(backup_path)
    except (OSError, sqlite3.Error) as exc:
        raise DatabaseMigrationGuardError(
            f"创建一致性迁移备份失败: {db_path} -> {backup_path}: {exc}"
        ) from exc
    finally:
        if destination is not None:
            destination.close()
        if source is not None:
            source.close()
        temp_path.unlink(missing_ok=True)


def create_pre_migration_backup(
    data_dir: Path,
    db_path: Path,
    *,
    target_schema_version: int = BACKEND_SCHEMA_VERSION,
    inspection: DatabaseMigrationInspection | None = None,
) -> Path | None:
    data_dir = Path(data_dir)
    db_path = Path(db_path)
    state = inspection or inspect_database_migration_state(
        db_path,
        target_schema_version=target_schema_version,
    )
    if not state.exists:
        return None
    if state.schema_version > target_schema_version:
        raise DatabaseDowngradeBlockedError(
            "拒绝用旧版后端打开更高版本数据库: "
            f"database={state.schema_version}, backend={target_schema_version}. "
            "请使用同版本或更高版本程序；若必须回退程序，需人工恢复对应的迁移前备份。"
        )
    if not state.needs_migration:
        return None

    backup_dir = _backup_dir(data_dir)
    _ensure_private_directory(backup_dir)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    backup_path = backup_dir / (
        f"{_backup_prefix(db_path)}{stamp}-{_path_identity(db_path)}.db"
    )
    digest = _create_consistent_sqlite_backup(db_path, backup_path)
    _atomic_write_json(
        backup_path.with_suffix(".db.json"),
        {
            "format_version": 1,
            "database_path": str(db_path.resolve()),
            "backup_file": backup_path.name,
            "backup_sha256": digest,
            "source_schema_version": state.schema_version,
            "target_schema_version": target_schema_version,
            "migration_reasons": list(state.reasons),
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    return backup_path


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DatabaseMigrationGuardError(f"迁移恢复标记损坏: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise DatabaseMigrationGuardError(f"迁移恢复标记不是 JSON object: {path}")
    return payload


def _validate_attempt_payload(
    payload: dict[str, Any],
    *,
    marker_path: Path,
    db_path: Path,
) -> tuple[Path, int, str]:
    if int(payload.get("format_version") or 0) != _ATTEMPT_FORMAT_VERSION:
        raise DatabaseMigrationGuardError(f"不支持的迁移恢复标记版本: {marker_path}")
    if str(payload.get("database_path") or "") != str(db_path.resolve()):
        raise DatabaseMigrationGuardError(f"迁移恢复标记与数据库路径不匹配: {marker_path}")
    backup_name = str(payload.get("backup_file") or "")
    backup_path = (marker_path.parent / backup_name).resolve()
    if (
        backup_path.parent != marker_path.parent.resolve()
        or not backup_path.name.startswith(_backup_prefix(db_path))
        or backup_path.suffix != ".db"
    ):
        raise DatabaseMigrationGuardError(f"迁移恢复标记包含非法备份路径: {marker_path}")
    try:
        target_schema_version = int(payload["target_schema_version"])
    except (KeyError, TypeError, ValueError) as exc:
        raise DatabaseMigrationGuardError(f"迁移恢复标记缺少目标 schema: {marker_path}") from exc
    expected_digest = str(payload.get("backup_sha256") or "")
    if len(expected_digest) != 64:
        raise DatabaseMigrationGuardError(f"迁移恢复标记缺少备份校验值: {marker_path}")
    return backup_path, target_schema_version, expected_digest


def _quarantine_path(path: Path, restore_id: str) -> Path:
    return path.with_name(f".{path.name}.migration-restore-{restore_id}")


def rollback_database_from_backup(
    db_path: Path,
    backup_path: Path | None,
    *,
    expected_sha256: str | None = None,
) -> None:
    if not backup_path:
        return
    db_path = Path(db_path)
    backup_path = Path(backup_path)
    if not backup_path.exists():
        raise DatabaseMigrationGuardError(f"迁移备份不存在，拒绝恢复: {backup_path}")
    if expected_sha256 and _sha256_file(backup_path) != expected_sha256:
        raise DatabaseMigrationGuardError(f"迁移备份校验值不匹配，拒绝恢复: {backup_path}")
    _validate_sqlite_snapshot(backup_path)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    restore_id = uuid4().hex
    staged_path = db_path.with_name(f".{db_path.name}.restore-{restore_id}.tmp")
    current_files = _sqlite_file_paths(db_path)
    quarantined: list[tuple[Path, Path]] = []
    promoted = False
    try:
        _create_private_file(staged_path)
        shutil.copyfile(backup_path, staged_path)
        staged_path.chmod(_PRIVATE_FILE_MODE)
        _validate_sqlite_snapshot(staged_path)
        _fsync_file(staged_path)
        for current_path in current_files:
            if not current_path.exists():
                continue
            quarantine = _quarantine_path(current_path, restore_id)
            current_path.chmod(_PRIVATE_FILE_MODE)
            os.replace(current_path, quarantine)
            quarantine.chmod(_PRIVATE_FILE_MODE)
            quarantined.append((current_path, quarantine))
        os.replace(staged_path, db_path)
        db_path.chmod(_PRIVATE_FILE_MODE)
        promoted = True
        _fsync_directory(db_path.parent)
        _validate_sqlite_snapshot(db_path)
    except Exception:
        if promoted:
            db_path.unlink(missing_ok=True)
        for current_path, quarantine in reversed(quarantined):
            if quarantine.exists():
                os.replace(quarantine, current_path)
        _fsync_directory(db_path.parent)
        raise
    finally:
        staged_path.unlink(missing_ok=True)
    for _, quarantine in quarantined:
        quarantine.unlink(missing_ok=True)
    _fsync_directory(db_path.parent)


def _write_attempt_marker(
    marker_path: Path,
    *,
    db_path: Path,
    backup_path: Path,
    source_schema_version: int,
    target_schema_version: int,
) -> None:
    _atomic_write_json(
        marker_path,
        {
            "format_version": _ATTEMPT_FORMAT_VERSION,
            "database_path": str(db_path.resolve()),
            "backup_file": backup_path.name,
            "backup_sha256": _sha256_file(backup_path),
            "source_schema_version": source_schema_version,
            "target_schema_version": target_schema_version,
            "started_at": datetime.now(timezone.utc).isoformat(),
        },
    )


def _recover_interrupted_migration(data_dir: Path, db_path: Path) -> None:
    marker_path = _attempt_path(data_dir, db_path)
    if not marker_path.exists():
        return
    payload = _read_json_object(marker_path)
    backup_path, target_schema_version, expected_digest = _validate_attempt_payload(
        payload,
        marker_path=marker_path,
        db_path=db_path,
    )
    try:
        current = inspect_database_migration_state(
            db_path,
            target_schema_version=target_schema_version,
        )
    except DatabaseMigrationGuardError:
        current = DatabaseMigrationInspection(exists=True, schema_version=0, reasons=("inspection_failed",))
    if current.exists and current.schema_version >= target_schema_version and not current.reasons:
        try:
            _validate_sqlite_snapshot(db_path)
        except DatabaseMigrationGuardError:
            pass
        else:
            marker_path.unlink()
            _fsync_directory(marker_path.parent)
            return
    rollback_database_from_backup(
        db_path,
        backup_path,
        expected_sha256=expected_digest,
    )
    marker_path.unlink()
    _fsync_directory(marker_path.parent)


def _prune_migration_backups(
    data_dir: Path,
    db_path: Path,
    *,
    keep_backups: int,
) -> None:
    if keep_backups < 1:
        raise ValueError("keep_backups must be at least 1")
    backup_dir = _backup_dir(data_dir)
    if not backup_dir.exists():
        return
    marker_path = _attempt_path(data_dir, db_path)
    active_backup_name = ""
    if marker_path.exists():
        try:
            active_backup_name = str(_read_json_object(marker_path).get("backup_file") or "")
        except DatabaseMigrationGuardError:
            return
    backups = sorted(
        backup_dir.glob(f"{_backup_prefix(db_path)}*-{_path_identity(db_path)}.db"),
        key=lambda item: (item.stat().st_mtime_ns, item.name),
        reverse=True,
    )
    retained = 0
    for backup_path in backups:
        if backup_path.name == active_backup_name or retained < keep_backups:
            retained += 1
            continue
        backup_path.unlink(missing_ok=True)
        backup_path.with_suffix(".db.json").unlink(missing_ok=True)
        for suffix in ("-wal", "-shm", "-journal"):
            backup_path.with_name(f"{backup_path.name}{suffix}").unlink(missing_ok=True)
    _fsync_directory(backup_dir)


def _open_database_with_migration_guard_locked(
    db_path: Path,
    *,
    data_dir: Path | None = None,
    target_schema_version: int = BACKEND_SCHEMA_VERSION,
    keep_backups: int = DEFAULT_MIGRATION_BACKUPS_TO_KEEP,
) -> tuple[Database, Path | None]:
    db_path = Path(db_path)
    resolved_data_dir = Path(data_dir) if data_dir is not None else db_path.parent
    resolved_data_dir.mkdir(parents=True, exist_ok=True)
    _recover_interrupted_migration(resolved_data_dir, db_path)

    try:
        inspection = inspect_database_migration_state(
            db_path,
            target_schema_version=target_schema_version,
        )
    except DatabaseMigrationGuardError:
        # 状态不可判定时绝不进入会写 schema 的 Database 构造器。
        raise
    if inspection.exists and inspection.schema_version > target_schema_version:
        raise DatabaseDowngradeBlockedError(
            "拒绝用旧版后端打开更高版本数据库: "
            f"database={inspection.schema_version}, backend={target_schema_version}. "
            "程序回退不等于数据库回退；请使用兼容程序或人工恢复对应迁移前备份。"
        )

    backup_path = create_pre_migration_backup(
        resolved_data_dir,
        db_path,
        target_schema_version=target_schema_version,
        inspection=inspection,
    )
    marker_path = _attempt_path(resolved_data_dir, db_path)
    if backup_path is not None:
        _write_attempt_marker(
            marker_path,
            db_path=db_path,
            backup_path=backup_path,
            source_schema_version=inspection.schema_version,
            target_schema_version=target_schema_version,
        )

    if db_path.exists():
        _harden_existing_sqlite_files(db_path)
    else:
        _create_private_file(db_path)

    db: Database | None = None
    try:
        db = Database(db_path)
        _harden_existing_sqlite_files(db_path)
        _validate_sqlite_snapshot(db_path)
        if backup_path is not None:
            post_migration = inspect_database_migration_state(
                db_path,
                target_schema_version=target_schema_version,
            )
            if post_migration.schema_version != target_schema_version or post_migration.reasons:
                raise DatabaseMigrationGuardError(
                    "数据库构造器返回后迁移契约仍不完整: "
                    f"schema={post_migration.schema_version}, reasons={post_migration.reasons}"
                )
    except Exception:
        if db is not None:
            db.conn.close()
        if backup_path is not None:
            payload = _read_json_object(marker_path)
            _, _, expected_digest = _validate_attempt_payload(
                payload,
                marker_path=marker_path,
                db_path=db_path,
            )
            rollback_database_from_backup(
                db_path,
                backup_path,
                expected_sha256=expected_digest,
            )
            marker_path.unlink(missing_ok=True)
            _fsync_directory(marker_path.parent)
        _prune_migration_backups(
            resolved_data_dir,
            db_path,
            keep_backups=keep_backups,
        )
        raise

    marker_path.unlink(missing_ok=True)
    _fsync_directory(marker_path.parent)
    _prune_migration_backups(
        resolved_data_dir,
        db_path,
        keep_backups=keep_backups,
    )
    assert db is not None
    return db, backup_path


def open_database_with_migration_guard(
    db_path: Path,
    *,
    data_dir: Path | None = None,
    target_schema_version: int = BACKEND_SCHEMA_VERSION,
    keep_backups: int = DEFAULT_MIGRATION_BACKUPS_TO_KEEP,
    lock_timeout_seconds: float = DEFAULT_MIGRATION_LOCK_TIMEOUT_SECONDS,
) -> tuple[Database, Path | None]:
    db_path = Path(db_path)
    resolved_data_dir = Path(data_dir) if data_dir is not None else db_path.parent
    with _exclusive_migration_lock(
        resolved_data_dir,
        db_path,
        timeout_seconds=lock_timeout_seconds,
    ):
        return _open_database_with_migration_guard_locked(
            db_path,
            data_dir=resolved_data_dir,
            target_schema_version=target_schema_version,
            keep_backups=keep_backups,
        )


def init_database_with_migration_guard(
    data_dir: Path,
    *,
    keep_backups: int = DEFAULT_MIGRATION_BACKUPS_TO_KEEP,
) -> tuple[Database, Path | None]:
    data_dir = Path(data_dir)
    return open_database_with_migration_guard(
        data_dir / "app.db",
        data_dir=data_dir,
        keep_backups=keep_backups,
    )
