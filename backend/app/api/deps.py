"""v2.2 N2 · FastAPI Depends · AppState 注入

main.py 把 AppState 挂在 `app.state.app_state`. 本 deps 拿出来给 router 用.

用法:
    from fastapi import Depends
    from app.api.deps import get_app_state

    @router.get(...)
    def my_endpoint(app_state = Depends(get_app_state)):
        rows = app_state.db.fetchall(...)
"""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request


def get_app_state(request: Request) -> Any:
    """从 request.app.state.app_state 拿 AppState (在 main.py create_app 注入)."""
    state = getattr(request.app.state, "app_state", None)
    if state is None:
        raise HTTPException(
            status_code=500,
            detail="AppState not initialized (request.app.state.app_state missing)",
        )
    return state
