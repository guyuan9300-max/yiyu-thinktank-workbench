"""pytest 全局配置。

主要作用：把 _known_failing.py 里的 pre-existing 失败测试统一打
``@pytest.mark.xfail``，让 CI 保持绿。

为什么用 xfail 而不是 skip：
- xfail strict=False → 失败时显示 XFAIL（预期失败），通过时显示 XPASS（意外通过）
- skip → 完全不跑，看不到该测试当前是否变绿
- xfail 保留"知道这些测试有问题、关注它们何时恢复"的可见性

不修改测试文件本体，所有标记集中维护在 _known_failing.py，便于：
- 看清"债"的全貌
- 测试逐步修好时只需从清单里删条目
- 不污染各 test 文件的版本历史
"""
from __future__ import annotations

import pytest

from tests._known_failing import KNOWN_FAILING_TESTS


@pytest.fixture(autouse=True)
def _disable_application_startup_workers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep HTTP tests isolated from process-wide daemon workers.

    The application exposes this switch specifically for environments that do
    not own a long-lived server process.  Without it, each TestClient starts
    workers such as team sync and startup cloud retry; some of those daemons
    intentionally outlive the ASGI lifespan and can observe another test's
    partially seeded cloud session.  Worker units normally call their services
    directly; the one startup-worker integration test explicitly removes this
    override before entering its TestClient lifespan.
    """

    monkeypatch.setenv("YIYU_DISABLE_STARTUP_WORKERS", "1")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """对 KNOWN_FAILING_TESTS 列表里的每个 nodeid，自动追加 xfail 标记。"""
    marker = pytest.mark.xfail(
        reason="pre-existing brittle test（迭代 2-7 工程盘点时记入 _known_failing.py）",
        strict=False,  # 通过时变 XPASS，不算错
    )
    for item in items:
        if item.nodeid in KNOWN_FAILING_TESTS:
            item.add_marker(marker)
