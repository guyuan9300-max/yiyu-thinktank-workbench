"""v2.2 Phase 1 F1.7 · ClientRepository stage audit + cloud sync 守门测试

服务: V2.2_NORTH_STAR.md
- N1 功能顺畅 (修 v1.0 客户 bug #1: frozen 被云端覆盖)
- N3 接入预留 A1: actor_type/actor_id 字段在 audit 表上, 3.0 AI agent 可直接复用

跑法:
    cd backend && .venv/bin/python3 -m pytest tests/test_v22_f17_stage_audit.py -v
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db import Database  # noqa: E402
from app.modules.client.repository import ClientRepository  # noqa: E402
from app.modules.client.types import ClientCreatePayload  # noqa: E402


@pytest.fixture
def repo(tmp_path: Path) -> ClientRepository:
    db = Database(tmp_path / "app.db")
    db.conn.execute("PRAGMA foreign_keys=OFF")
    return ClientRepository(db)


@pytest.fixture
def repo_with_client(repo: ClientRepository) -> tuple[ClientRepository, str]:
    """带一个 active 客户的 repo"""
    record = repo.create(ClientCreatePayload(
        name="测试客户",
        alias="test",
        domain="项目",
        type="项目",
        intro="",
        stage="active",
        color="#5B7BFE",
    ))
    return repo, record.id


# ────────────────────────────────────────────────────────────────
# 1. client_stage_audit 表 schema 落地
# ────────────────────────────────────────────────────────────────


def test_client_stage_audit_table_exists(repo: ClientRepository):
    """schema 加载后 client_stage_audit 表存在"""
    row = repo._db.fetchone(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='client_stage_audit'"
    )
    assert row is not None
    assert row["name"] == "client_stage_audit"


def test_client_stage_audit_columns_complete(repo: ClientRepository):
    """N3 预留: actor_type / actor_id 字段必须在"""
    rows = repo._db.fetchall("PRAGMA table_info(client_stage_audit)")
    col_names = {r["name"] for r in rows}
    required = {
        "id", "client_id", "old_stage", "new_stage",
        "actor_type", "actor_id", "reason", "guard_action", "changed_at",
    }
    missing = required - col_names
    assert not missing, f"missing columns: {missing}"


# ────────────────────────────────────────────────────────────────
# 2. freeze/unfreeze/archive 写 audit log
# ────────────────────────────────────────────────────────────────


def test_freeze_writes_audit_log(repo_with_client):
    repo, client_id = repo_with_client
    repo.freeze(client_id, reason="客户暂停合作", actor_id="user_guyuanyuan")
    audits = repo.list_stage_audit(client_id)
    assert len(audits) == 1
    assert audits[0]["old_stage"] == "active"
    assert audits[0]["new_stage"] == "frozen"
    assert audits[0]["actor_type"] == "human"
    assert audits[0]["actor_id"] == "user_guyuanyuan"
    assert audits[0]["reason"] == "客户暂停合作"
    assert audits[0]["guard_action"] == "applied"


def test_freeze_idempotent_no_duplicate_audit(repo_with_client):
    """重复冻结同一客户不应重复写 audit"""
    repo, client_id = repo_with_client
    repo.freeze(client_id, reason="首次", actor_id="u1")
    repo.freeze(client_id, reason="重复", actor_id="u1")  # 已冻结, 应幂等
    audits = repo.list_stage_audit(client_id)
    assert len(audits) == 1  # 只有第一次的


def test_unfreeze_writes_audit_log(repo_with_client):
    repo, client_id = repo_with_client
    repo.freeze(client_id, actor_id="u1")
    repo.unfreeze(client_id, reason="恢复合作", actor_id="u2")
    audits = repo.list_stage_audit(client_id)
    assert len(audits) == 2  # freeze + unfreeze
    # audits 按 changed_at DESC, 最新在前
    assert audits[0]["new_stage"] == "active"
    assert audits[0]["reason"] == "恢复合作"
    assert audits[0]["actor_id"] == "u2"


def test_archive_writes_audit_log(repo_with_client):
    repo, client_id = repo_with_client
    repo.archive(client_id, reason="项目结束", actor_id="u1")
    audits = repo.list_stage_audit(client_id)
    assert len(audits) == 1
    assert audits[0]["new_stage"] == "archived"
    assert audits[0]["reason"] == "项目结束"


# ────────────────────────────────────────────────────────────────
# 3. ★ v1.0 bug 修复核心: cloud sync 不覆盖 frozen
# ────────────────────────────────────────────────────────────────


def test_cloud_sync_cannot_overwrite_frozen(repo_with_client):
    """★ v1.0 bug 修法: local frozen + 云端 active → 守门拒绝"""
    repo, client_id = repo_with_client
    # 本地用户冻结
    repo.freeze(client_id, reason="本地用户主动冻结", actor_id="u_local")

    # 云端同步过来 stage='active' — 应该被守门拒绝
    applied, msg = repo.apply_cloud_stage_change(client_id, "active")
    assert applied is False
    assert "local frozen" in msg
    assert "rejected" in msg

    # 客户 stage 仍是 frozen
    client = repo.get_by_id(client_id)
    assert client.stage == "frozen"

    # audit log 记录了这次守门
    audits = repo.list_stage_audit(client_id)
    guarded = [a for a in audits if a["guard_action"] == "guarded"]
    assert len(guarded) == 1
    assert guarded[0]["new_stage"] == "active"  # 云端想改的目标
    assert "rejected" in guarded[0]["reason"]
    assert guarded[0]["actor_id"] == "cloud_sync"


def test_cloud_sync_can_freeze_when_local_active(repo_with_client):
    """local active + 云端 frozen → 允许应用 (用户在别的端冻结)"""
    repo, client_id = repo_with_client
    applied, msg = repo.apply_cloud_stage_change(client_id, "frozen")
    assert applied is True
    assert msg == ""
    client = repo.get_by_id(client_id)
    assert client.stage == "frozen"


def test_cloud_sync_same_stage_noop(repo_with_client):
    """local 和 cloud 同 stage → 无变化, 不写 audit"""
    repo, client_id = repo_with_client
    applied, _ = repo.apply_cloud_stage_change(client_id, "active")
    assert applied is True
    audits = repo.list_stage_audit(client_id)
    assert len(audits) == 0  # 同 stage, 不写 audit


def test_cloud_sync_normal_stage_change_logged(repo_with_client):
    """local active + 云端 archived → 应用且记 audit"""
    repo, client_id = repo_with_client
    applied, msg = repo.apply_cloud_stage_change(client_id, "archived")
    assert applied is True
    audits = repo.list_stage_audit(client_id)
    assert len(audits) == 1
    assert audits[0]["new_stage"] == "archived"
    assert audits[0]["actor_type"] == "system"
    assert audits[0]["actor_id"] == "cloud_sync"
    assert audits[0]["guard_action"] == "applied"


def test_cloud_sync_unknown_client_passes(repo: ClientRepository):
    """云端有但本地没有的客户 → 不守门 (会在新建路径走)"""
    applied, _ = repo.apply_cloud_stage_change("nonexistent_id", "active")
    assert applied is True


# ────────────────────────────────────────────────────────────────
# 4. list_stage_audit 过滤功能
# ────────────────────────────────────────────────────────────────


def test_list_stage_audit_guarded_only(repo_with_client):
    """guarded_only=True 只返回被守门挡下的记录"""
    repo, client_id = repo_with_client
    repo.freeze(client_id, actor_id="u1")
    # 1 次正常 freeze + 2 次云端尝试覆盖
    repo.apply_cloud_stage_change(client_id, "active")
    repo.apply_cloud_stage_change(client_id, "archived")
    all_audits = repo.list_stage_audit(client_id)
    assert len(all_audits) == 3
    guarded = repo.list_stage_audit(client_id, guarded_only=True)
    assert len(guarded) == 2
    assert all(a["guard_action"] == "guarded" for a in guarded)


def test_list_stage_audit_limit(repo_with_client):
    """limit 控制返回数量"""
    repo, client_id = repo_with_client
    # 触发 4 次 stage 变化
    repo.freeze(client_id, actor_id="u1")
    repo.unfreeze(client_id, actor_id="u1")
    repo.archive(client_id, actor_id="u1")
    audits = repo.list_stage_audit(client_id, limit=2)
    assert len(audits) == 2


# ────────────────────────────────────────────────────────────────
# 5. N3 接入预留: ai_agent actor_type 工作
# ────────────────────────────────────────────────────────────────


def test_ai_agent_can_freeze_as_actor(repo_with_client):
    """N3 预留: 3.0 AI agent 调 freeze 时 actor_type='ai_agent' 写入"""
    repo, client_id = repo_with_client
    repo.freeze(
        client_id,
        reason="AI 自动判断客户长期无互动",
        actor_type="ai_agent",
        actor_id="ai_session_2026_05_22",
    )
    audits = repo.list_stage_audit(client_id)
    assert len(audits) == 1
    assert audits[0]["actor_type"] == "ai_agent"
    assert audits[0]["actor_id"] == "ai_session_2026_05_22"
