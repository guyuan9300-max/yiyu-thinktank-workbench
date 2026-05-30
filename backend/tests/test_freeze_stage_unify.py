"""回归测试:freeze 双机制统一到 stage 真相源 (P0-freeze)。

根因(实证):
- /freeze 端点(UI)只写 frozen_at;ClientRepository.freeze() 只写 stage='frozen'。
- v_active_clients 视图按 frozen_at IS NULL 过滤;list_active 按 stage 过滤。
两套写 + 两套读各用不同字段 → 脱节:repo/云冻结(stage='frozen', frozen_at=NULL)
会被旧视图(frozen_at IS NULL)错误包含 → 冻结客户漏进组织/事件线/知识查询。

修法(stage = 云安全唯一真相源,见 repository.freeze 注释):
- 视图改 WHERE stage != 'frozen';
- /freeze、/unfreeze 端点兼写 stage;
- db.py 启动回填历史 frozen_at-only 行到 stage='frozen';
- isFrozen 从 stage 派生。

本测试覆盖视图过滤 + 回填的核心数据正确性逻辑。
"""
from __future__ import annotations

import sqlite3

import pytest


@pytest.fixture()
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE clients (id TEXT PRIMARY KEY, stage TEXT NOT NULL, frozen_at TEXT)")
    c.executemany(
        "INSERT INTO clients(id,stage,frozen_at) VALUES(?,?,?)",
        [
            ("active", "active", None),
            ("ui_frozen", "active", "2026-05-01T00:00"),   # 历史 UI 冻结:只写 frozen_at
            ("cloud_frozen", "frozen", None),               # repo/云冻结:只写 stage(旧视图会漏)
            ("archived", "archived", None),
            ("lost", "lost", None),
        ],
    )
    return c


_RECONCILE = (
    "UPDATE clients SET stage='frozen' "
    "WHERE frozen_at IS NOT NULL AND stage NOT IN ('frozen','archived','lost')"
)
_VIEW = "CREATE VIEW v_active_clients AS SELECT * FROM clients WHERE stage != 'frozen'"


def _active_ids(conn: sqlite3.Connection) -> set[str]:
    conn.execute(_RECONCILE)
    conn.execute("DROP VIEW IF EXISTS v_active_clients")
    conn.execute(_VIEW)
    return {r["id"] for r in conn.execute("SELECT id FROM v_active_clients")}


def test_both_freeze_paths_excluded_from_active_view(conn: sqlite3.Connection) -> None:
    active = _active_ids(conn)
    # 核心:两类冻结都被排除(修复前 cloud_frozen 会泄漏进来)
    assert "cloud_frozen" not in active
    assert "ui_frozen" not in active
    # 活跃保留;归档/丢失保持原视图行为(仍包含)
    assert active == {"active", "archived", "lost"}


def test_reconcile_is_idempotent(conn: sqlite3.Connection) -> None:
    conn.execute(_RECONCILE)
    before = conn.execute("SELECT count(*) FROM clients WHERE stage='frozen'").fetchone()[0]
    conn.execute(_RECONCILE)
    after = conn.execute("SELECT count(*) FROM clients WHERE stage='frozen'").fetchone()[0]
    assert before == after == 2  # ui_frozen(回填) + cloud_frozen


def test_reconcile_does_not_touch_archived_or_lost(conn: sqlite3.Connection) -> None:
    conn.execute(_RECONCILE)
    rows = {r["id"]: r["stage"] for r in conn.execute("SELECT id, stage FROM clients")}
    assert rows["archived"] == "archived"
    assert rows["lost"] == "lost"
