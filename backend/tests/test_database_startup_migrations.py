from __future__ import annotations

import os
import shutil
import sqlite3
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import app.db as db_module  # noqa: E402
import app.database_guard as guard_module  # noqa: E402
from app.db import Database  # noqa: E402


def _create_current_database(path: Path) -> None:
    db = Database(path)
    db.conn.close()


def _insert_scope_parents(conn: sqlite3.Connection) -> None:
    for sandbox_id, legacy, last_active in (
        ("sbx_active", 0, "2026-07-10T02:00:00Z"),
        ("sbx_list", 1, "2026-07-10T01:00:00Z"),
    ):
        conn.execute(
            """
            INSERT OR REPLACE INTO sandboxes(
                id, kind, name, status, is_legacy_default,
                created_at, updated_at, last_active_at
            ) VALUES(?, 'organization', ?, 'active', ?, ?, ?, ?)
            """,
            (sandbox_id, sandbox_id, legacy, "2026-07-10T00:00:00Z", "2026-07-10T00:00:00Z", last_active),
        )
    conn.execute(
        "INSERT OR REPLACE INTO settings(key, value) VALUES('active_sandbox_id', 'sbx_active')"
    )
    for operator_id in ("op_current", "op_backup"):
        conn.execute(
            """
            INSERT OR REPLACE INTO operators(
                id, name, role, team, color, is_current, created_at, updated_at
            ) VALUES(?, ?, 'member', 'test', '#000000', 0, '', '')
            """,
            (operator_id, operator_id),
        )
    conn.execute(
        """
        INSERT OR REPLACE INTO task_lists(id, sandbox_id, name, color)
        VALUES('list-sbx-list', 'sbx_list', '收集箱', '#000000')
        """
    )


@pytest.mark.integration
def test_task_scope_rebuild_is_atomic_when_second_table_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "app.db"
    _create_current_database(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=OFF")
    _insert_scope_parents(conn)
    conn.execute("DROP TABLE task_tags")
    conn.execute(
        """
        CREATE TABLE task_tags(
            id TEXT PRIMARY KEY,
            sandbox_id TEXT NOT NULL DEFAULT '',
            name TEXT NOT NULL UNIQUE
        )
        """
    )
    conn.execute("INSERT INTO task_tags(id, sandbox_id, name) VALUES('tag-1', 'sbx_active', '唯一标签')")
    conn.execute("DROP TABLE task_settings")
    conn.execute(
        """
        CREATE TABLE task_settings(
            operator_id TEXT PRIMARY KEY,
            default_list_id TEXT,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "INSERT INTO task_settings(operator_id, default_list_id, updated_at) VALUES('op_current', NULL, '')"
    )
    conn.execute("PRAGMA user_version=0")
    conn.commit()
    conn.close()

    def fail_settings_rebuild(self: Database) -> None:
        raise RuntimeError("injected settings migration failure")

    monkeypatch.setattr(Database, "_rebuild_task_settings_with_sandbox_scope", fail_settings_rebuild)
    with pytest.raises(RuntimeError, match="injected settings migration failure"):
        Database(db_path)

    check = sqlite3.connect(db_path)
    sql = str(check.execute("SELECT sql FROM sqlite_master WHERE name='task_tags'").fetchone()[0]).lower()
    assert "unique" in sql
    assert check.execute("SELECT id, name FROM task_tags").fetchall() == [("tag-1", "唯一标签")]
    assert check.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='task_tags__stage5_global_unique_backup'"
    ).fetchone()[0] == 0
    check.close()


@pytest.mark.integration
def test_recovery_merges_current_and_backup_with_valid_scope(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    _create_current_database(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=OFF")
    _insert_scope_parents(conn)
    conn.execute(
        "INSERT INTO task_tags(id, sandbox_id, name) VALUES('tag-current', 'sbx_active', 'current')"
    )
    conn.execute(
        """
        CREATE TABLE task_tags__stage5_global_unique_backup(
            id TEXT PRIMARY KEY,
            sandbox_id TEXT NOT NULL DEFAULT '',
            name TEXT NOT NULL UNIQUE,
            color TEXT NOT NULL DEFAULT '#5B7BFE'
        )
        """
    )
    conn.executemany(
        "INSERT INTO task_tags__stage5_global_unique_backup(id, sandbox_id, name) VALUES(?, ?, ?)",
        (
            ("tag-current", "sbx_list", "backup-loses"),
            ("tag-backup", "sbx_list", "backup-supplement"),
        ),
    )
    conn.execute(
        """
        INSERT INTO task_settings(
            sandbox_id, operator_id, default_list_id, default_priority, updated_at
        ) VALUES('sbx_active', 'op_current', 'list-sbx-list', 'high', 'current')
        """
    )
    conn.execute(
        """
        CREATE TABLE task_settings__sandbox_scope_backup(
            operator_id TEXT PRIMARY KEY,
            default_list_id TEXT,
            default_priority TEXT NOT NULL DEFAULT 'normal',
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.executemany(
        """
        INSERT INTO task_settings__sandbox_scope_backup(
            operator_id, default_list_id, default_priority, updated_at
        ) VALUES(?, ?, ?, ?)
        """,
        (
            ("op_current", "list-sbx-list", "low", "backup-loses"),
            ("op_backup", "list-sbx-list", "urgent", "backup-supplement"),
            ("op_missing", "list-sbx-list", "normal", "invalid-parent"),
            ("op_qh", "list-sbx-list", "normal", "must-not-backfill"),
        ),
    )
    conn.execute("PRAGMA user_version=0")
    conn.commit()
    conn.close()

    db = Database(db_path)
    assert [tuple(row) for row in db.conn.execute(
        "SELECT id, sandbox_id, name FROM task_tags ORDER BY id"
    )] == [
        ("tag-backup", "sbx_list", "backup-supplement"),
        ("tag-current", "sbx_active", "current"),
    ]
    assert [tuple(row) for row in db.conn.execute(
        """
        SELECT sandbox_id, operator_id, default_list_id, default_priority, updated_at
        FROM task_settings ORDER BY operator_id, sandbox_id
        """
    )] == [
        ("sbx_list", "op_backup", "list-sbx-list", "urgent", "backup-supplement"),
        ("sbx_active", "op_current", None, "high", "current"),
        ("sbx_list", "op_current", "list-sbx-list", "low", "backup-loses"),
    ]
    leftovers = {
        row[0]
        for row in db.conn.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name IN (
                'task_tags__stage5_global_unique_backup',
                'task_settings__sandbox_scope_backup'
            )
            """
        )
    }
    assert leftovers == set()
    assert db.conn.execute("PRAGMA foreign_key_check(task_settings)").fetchall() == []
    db.conn.close()


@pytest.mark.integration
def test_recovery_restores_backup_only_half_state(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    _create_current_database(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=OFF")
    _insert_scope_parents(conn)
    conn.execute(
        "INSERT INTO task_tags(id, sandbox_id, name) VALUES('tag-backup-only', 'sbx_list', 'backup-only')"
    )
    conn.execute(
        """
        INSERT INTO task_settings(
            sandbox_id, operator_id, default_list_id, default_priority, updated_at
        ) VALUES('sbx_list', 'op_backup', 'list-sbx-list', 'urgent', 'backup-only')
        """
    )
    conn.execute("ALTER TABLE task_tags RENAME TO task_tags__stage5_global_unique_backup")
    conn.execute("ALTER TABLE task_settings RENAME TO task_settings__sandbox_scope_backup")
    conn.execute("PRAGMA user_version=0")
    conn.commit()
    conn.close()

    db = Database(db_path)
    assert tuple(db.conn.execute(
        "SELECT id, sandbox_id, name FROM task_tags WHERE id='tag-backup-only'"
    ).fetchone()) == ("tag-backup-only", "sbx_list", "backup-only")
    assert tuple(db.conn.execute(
        """
        SELECT sandbox_id, operator_id, default_list_id, default_priority, updated_at
        FROM task_settings WHERE operator_id='op_backup'
        """
    ).fetchone()) == (
        "sbx_list",
        "op_backup",
        "list-sbx-list",
        "urgent",
        "backup-only",
    )
    db.conn.close()


@pytest.mark.integration
def test_topic_seen_backfill_keeps_orphan_candidate_unseen(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    _create_current_database(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute(
        """
        INSERT INTO topic_candidates(
            id, radar_id, title, summary, source, source_url,
            status, created_at, updated_at
        ) VALUES('candidate-orphan', 'missing-radar', '孤儿', '', 'source', 'https://orphan', 'new', '', '')
        """
    )
    conn.commit()
    conn.close()

    db = Database(db_path)
    assert db.conn.execute(
        "SELECT COUNT(*) FROM topic_candidates WHERE id='candidate-orphan'"
    ).fetchone()[0] == 1
    assert db.conn.execute(
        "SELECT COUNT(*) FROM topic_candidate_seen WHERE id='seen_candidate-orphan'"
    ).fetchone()[0] == 0
    db.conn.close()


@pytest.mark.integration
def test_topic_seen_backfill_preserves_primary_key_collision_and_creates_new_seen_row(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    _create_current_database(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO topic_radars(id, sandbox_id, title, prompt, time_range, created_at) VALUES('radar-1', '', '', '', '', '')"
    )
    conn.execute(
        """
        INSERT INTO topic_candidates(
            id, radar_id, title, summary, source, source_url,
            status, created_at, updated_at
        ) VALUES('candidate-1', 'radar-1', 'candidate', '', 'source', 'https://candidate', 'new', '', '')
        """
    )
    conn.execute(
        """
        INSERT INTO topic_candidate_seen(
            id, radar_id, source_url_key, title_source_key,
            source_url, title, source, created_at
        ) VALUES('seen_candidate-1', 'radar-1', 'https://other', 'other||source', 'https://other', 'other', 'source', '')
        """
    )
    conn.commit()
    conn.close()

    db = Database(db_path)
    rows = db.conn.execute(
        "SELECT id, source_url FROM topic_candidate_seen WHERE radar_id='radar-1' ORDER BY source_url"
    ).fetchall()
    assert len(rows) == 2
    assert [str(row["source_url"]) for row in rows] == ["https://candidate", "https://other"]
    assert len({str(row["id"]) for row in rows}) == 2
    db.conn.close()


@pytest.mark.integration
def test_legacy_operator_preferences_without_list_are_copied_to_active_sandboxes(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    _create_current_database(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=OFF")
    _insert_scope_parents(conn)
    conn.execute("UPDATE sandboxes SET status='archived' WHERE id='sbx_local_default'")
    conn.execute("DROP TABLE task_settings")
    conn.execute(
        """
        CREATE TABLE task_settings(
            operator_id TEXT PRIMARY KEY,
            default_list_id TEXT,
            default_priority TEXT NOT NULL DEFAULT 'normal',
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "INSERT INTO task_settings(operator_id, default_list_id, default_priority, updated_at) "
        "VALUES('op_current', NULL, 'high', 'legacy')"
    )
    conn.execute("PRAGMA user_version=0")
    conn.commit()
    conn.close()

    db = Database(db_path)
    rows = db.conn.execute(
        "SELECT sandbox_id, operator_id, default_list_id, default_priority FROM task_settings "
        "WHERE operator_id='op_current' ORDER BY sandbox_id"
    ).fetchall()
    assert [tuple(row) for row in rows] == [
        ("sbx_active", "op_current", None, "high"),
        ("sbx_list", "op_current", None, "high"),
    ]
    db.conn.close()


@pytest.mark.unit
def test_database_constructor_closes_connection_on_schema_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    opened: list[TrackingConnection] = []
    original_connect = sqlite3.connect

    class TrackingConnection(sqlite3.Connection):
        was_closed = False

        def close(self) -> None:
            self.was_closed = True
            super().close()

    def tracking_connect(*args: object, **kwargs: object) -> TrackingConnection:
        kwargs["factory"] = TrackingConnection
        connection = original_connect(*args, **kwargs)
        opened.append(connection)
        return connection

    def fail_schema(self: Database) -> None:
        raise RuntimeError("schema boom")

    monkeypatch.setattr(db_module.sqlite3, "connect", tracking_connect)
    monkeypatch.setattr(Database, "_init_schema", fail_schema)

    with pytest.raises(RuntimeError, match="schema boom"):
        Database(tmp_path / "app.db")

    assert len(opened) == 1
    assert opened[0].was_closed is True


@pytest.mark.integration
def test_create_app_uses_shared_database_migration_guard(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.database_guard as guard_module
    import app.main as main_module

    guarded_paths: list[Path] = []
    real_guard = guard_module.init_database_with_migration_guard

    def tracking_guard(data_dir: Path) -> tuple[Database, Path | None]:
        guarded_paths.append(Path(data_dir))
        return real_guard(data_dir)

    monkeypatch.setattr(guard_module, "init_database_with_migration_guard", tracking_guard)

    data_dir = tmp_path / "application"
    candidate = main_module.create_app(data_dir)
    try:
        assert guarded_paths == [data_dir]
    finally:
        candidate.state.app_state.db.conn.close()


@pytest.mark.unit
def test_migration_backup_artifacts_stay_private_with_permissive_umask(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    _create_current_database(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA user_version=0")

    previous_umask = os.umask(0o022)
    try:
        backup_path = guard_module.create_pre_migration_backup(tmp_path, db_path)
        assert backup_path is not None
        marker_path = backup_path.parent / ".permission-probe.json"
        guard_module._atomic_write_json(marker_path, {"probe": True})
    finally:
        os.umask(previous_umask)

    assert stat.S_IMODE(backup_path.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(backup_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(backup_path.with_suffix(".db.json").stat().st_mode) == 0o600
    assert stat.S_IMODE(marker_path.stat().st_mode) == 0o600


@pytest.mark.unit
def test_rollback_quarantine_artifacts_stay_private_with_permissive_umask(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "app.db"
    backup_path = tmp_path / "backup.db"
    _create_current_database(db_path)
    shutil.copy2(db_path, backup_path)
    db_path.chmod(0o644)
    backup_path.chmod(0o600)
    for suffix in ("-wal", "-shm", "-journal"):
        sidecar_path = db_path.with_name(f"{db_path.name}{suffix}")
        sidecar_path.write_bytes(b"rollback-permission-probe")
        sidecar_path.chmod(0o644)

    quarantine_modes: list[int] = []
    staged_modes: list[int] = []
    real_replace = guard_module.os.replace
    real_copyfile = guard_module.shutil.copyfile

    def tracking_copyfile(
        source: str | os.PathLike[str],
        destination: str | os.PathLike[str],
    ) -> str:
        destination_path = Path(destination)
        staged_modes.append(stat.S_IMODE(destination_path.stat().st_mode))
        return str(real_copyfile(source, destination))

    def tracking_replace(source: str | os.PathLike[str], destination: str | os.PathLike[str]) -> None:
        real_replace(source, destination)
        destination_path = Path(destination)
        if ".migration-restore-" in destination_path.name:
            quarantine_modes.append(stat.S_IMODE(destination_path.stat().st_mode))

    monkeypatch.setattr(guard_module.shutil, "copyfile", tracking_copyfile)
    monkeypatch.setattr(guard_module.os, "replace", tracking_replace)

    previous_umask = os.umask(0o022)
    try:
        guard_module.rollback_database_from_backup(db_path, backup_path)
    finally:
        os.umask(previous_umask)

    assert staged_modes == [0o600]
    assert quarantine_modes == [0o600, 0o600, 0o600, 0o600]
    assert stat.S_IMODE(db_path.stat().st_mode) == 0o600


@pytest.mark.integration
def test_guarded_database_file_stays_private_with_permissive_umask(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "app.db"
    constructor_entry_modes: list[int | None] = []
    real_database = guard_module.Database

    def tracking_database(path: Path) -> Database:
        candidate = Path(path)
        constructor_entry_modes.append(
            stat.S_IMODE(candidate.stat().st_mode) if candidate.exists() else None
        )
        return real_database(candidate)

    monkeypatch.setattr(guard_module, "Database", tracking_database)

    previous_umask = os.umask(0o022)
    try:
        db, backup_path = guard_module.open_database_with_migration_guard(
            db_path,
            data_dir=tmp_path,
        )
    finally:
        os.umask(previous_umask)

    try:
        assert backup_path is None
        assert constructor_entry_modes == [0o600]
        db.conn.execute("CREATE TABLE permission_probe(value TEXT NOT NULL)")
        db.conn.execute("INSERT INTO permission_probe(value) VALUES('private')")
        db.conn.commit()
        database_files = [
            db_path,
            db_path.with_name(f"{db_path.name}-wal"),
            db_path.with_name(f"{db_path.name}-shm"),
        ]
        assert all(path.exists() for path in database_files)
        assert [stat.S_IMODE(path.stat().st_mode) for path in database_files] == [
            0o600,
            0o600,
            0o600,
        ]
        journal_path = db_path.with_name(f"{db_path.name}-journal")
        assert not journal_path.exists() or stat.S_IMODE(journal_path.stat().st_mode) == 0o600
    finally:
        db.conn.close()


@pytest.mark.integration
def test_migration_guard_restores_backup_after_constructor_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "app.db"
    _create_current_database(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE migration_guard_probe(value TEXT NOT NULL)")
        conn.execute("INSERT INTO migration_guard_probe(value) VALUES('before')")
        conn.execute("PRAGMA user_version=0")

    class FailingDatabase:
        def __init__(self, path: Path) -> None:
            with sqlite3.connect(path) as conn:
                conn.execute("DELETE FROM migration_guard_probe")
                conn.execute("CREATE TABLE partial_migration(value TEXT)")
            raise RuntimeError("injected constructor failure")

    monkeypatch.setattr(guard_module, "Database", FailingDatabase)

    with pytest.raises(RuntimeError, match="injected constructor failure"):
        guard_module.open_database_with_migration_guard(db_path, data_dir=tmp_path)

    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT value FROM migration_guard_probe").fetchone() == ("before",)
        assert conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='partial_migration'"
        ).fetchone() == (0,)
        assert conn.execute("PRAGMA quick_check").fetchone() == ("ok",)
    assert not guard_module._attempt_path(tmp_path, db_path).exists()
    assert list(guard_module._backup_dir(tmp_path).glob("app-pre-migrate-*.db"))


@pytest.mark.integration
def test_migration_guard_blocks_newer_database_without_backup(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    _create_current_database(db_path)
    future_version = db_module.BACKEND_SCHEMA_VERSION + 1
    with sqlite3.connect(db_path) as conn:
        conn.execute(f"PRAGMA user_version={future_version}")

    with pytest.raises(guard_module.DatabaseDowngradeBlockedError):
        guard_module.open_database_with_migration_guard(db_path, data_dir=tmp_path)

    with sqlite3.connect(db_path) as conn:
        assert conn.execute("PRAGMA user_version").fetchone() == (future_version,)
        assert conn.execute("PRAGMA quick_check").fetchone() == ("ok",)
    assert not list(guard_module._backup_dir(tmp_path).glob("app-pre-migrate-*.db"))


def test_directory_fsync_is_skipped_on_windows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(guard_module.os, "name", "nt")

    def unexpected_open(*_args, **_kwargs):
        raise AssertionError("Windows must not open directories for os.fsync")

    monkeypatch.setattr(guard_module.os, "open", unexpected_open)
    guard_module._fsync_directory(tmp_path)


@pytest.mark.integration
def test_post_migration_quick_check_failure_restores_verified_backup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "app.db"
    _create_current_database(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE live_check_probe(value TEXT NOT NULL)")
        conn.execute("INSERT INTO live_check_probe(value) VALUES('before')")
        conn.execute("PRAGMA user_version=0")

    real_validate = guard_module._validate_sqlite_snapshot
    live_checks = 0

    def fail_first_live_check(path: Path) -> None:
        nonlocal live_checks
        if Path(path) == db_path:
            live_checks += 1
            if live_checks == 1:
                raise guard_module.DatabaseMigrationGuardError("injected live quick_check failure")
        real_validate(Path(path))

    monkeypatch.setattr(guard_module, "_validate_sqlite_snapshot", fail_first_live_check)
    with pytest.raises(guard_module.DatabaseMigrationGuardError, match="injected live quick_check failure"):
        guard_module.open_database_with_migration_guard(db_path, data_dir=tmp_path)

    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT value FROM live_check_probe").fetchone() == ("before",)
        assert conn.execute("PRAGMA user_version").fetchone() == (0,)
        assert conn.execute("PRAGMA quick_check").fetchone() == ("ok",)


@pytest.mark.integration
def test_interrupted_migration_does_not_accept_live_db_when_quick_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "app.db"
    _create_current_database(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE interrupted_probe(value TEXT NOT NULL)")
        conn.execute("INSERT INTO interrupted_probe(value) VALUES('backup')")
    inspection = guard_module.inspect_database_migration_state(db_path)
    backup_path = guard_module.create_pre_migration_backup(
        tmp_path,
        db_path,
        target_schema_version=db_module.BACKEND_SCHEMA_VERSION + 1,
        inspection=guard_module.DatabaseMigrationInspection(
            exists=True,
            schema_version=inspection.schema_version,
            reasons=("forced_test_migration",),
        ),
    )
    assert backup_path is not None
    marker_path = guard_module._attempt_path(tmp_path, db_path)
    guard_module._write_attempt_marker(
        marker_path,
        db_path=db_path,
        backup_path=backup_path,
        source_schema_version=inspection.schema_version,
        target_schema_version=db_module.BACKEND_SCHEMA_VERSION,
    )
    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE interrupted_probe SET value='damaged-live'")

    real_validate = guard_module._validate_sqlite_snapshot
    live_checks = 0

    def fail_first_live_check(path: Path) -> None:
        nonlocal live_checks
        if Path(path) == db_path:
            live_checks += 1
            if live_checks == 1:
                raise guard_module.DatabaseMigrationGuardError("injected interrupted quick_check failure")
        real_validate(Path(path))

    monkeypatch.setattr(guard_module, "_validate_sqlite_snapshot", fail_first_live_check)
    guard_module._recover_interrupted_migration(tmp_path, db_path)
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT value FROM interrupted_probe").fetchone() == ("backup",)
    assert not marker_path.exists()


@pytest.mark.integration
def test_migration_lock_rejects_a_second_process(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    _create_current_database(db_path)
    ready_path = tmp_path / "lock-ready"
    code = (
        "import sys,time; from pathlib import Path; "
        f"sys.path.insert(0, {str(ROOT)!r}); "
        "from app.database_guard import _exclusive_migration_lock; "
        f"data=Path({str(tmp_path)!r}); db=Path({str(db_path)!r}); ready=Path({str(ready_path)!r}); "
        "ctx=_exclusive_migration_lock(data, db, timeout_seconds=2); ctx.__enter__(); "
        "ready.write_text('ready'); time.sleep(5); ctx.__exit__(None,None,None)"
    )
    process = subprocess.Popen([sys.executable, "-c", code])
    try:
        deadline = time.monotonic() + 3
        while not ready_path.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert ready_path.exists()
        with pytest.raises(guard_module.DatabaseMigrationGuardError, match="另一个进程"):
            guard_module.open_database_with_migration_guard(
                db_path,
                data_dir=tmp_path,
                lock_timeout_seconds=0.2,
            )
    finally:
        process.terminate()
        process.wait(timeout=5)
