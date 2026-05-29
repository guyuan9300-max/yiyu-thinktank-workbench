"""v2.2 N2 · 模块化 endpoint router 包.

定位:
    main.py 现在 27000+ 行 closure 风格. 本目录是"未来 endpoint 拆分模板".
    新 endpoint 先放这里, 旧的逐步迁移 (不强制).

约定:
    1. 每个 router 模块 export `router: APIRouter`
    2. state 通过 `get_app_state` Depends 注入 (见 deps.py)
    3. response 用 pydantic BaseModel, 入参用 Header/Query/Path
    4. service 调用走 backend/app/services/, router 只做 HTTP 层
"""
