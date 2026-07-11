# Sandbox 0.28.1 全量执行验收（2026-07-11）

## 目标

与同事的 0.28.1 沙箱化方向合并：数据、账号、AI 配置、异步任务、附件和所有直接 ID 操作不得跨组织或跨活动沙箱；旧数据只有存在唯一且可验证的父链时才允许迁移回填，不猜测归属。

## 已关闭的边界

- 任务、事件线、叙事、分析、知识库、对象存储配置和组织 AI 配置按活动沙箱或组织冻结 scope。
- 异步任务在入队时冻结沙箱，执行、重试、落库和回收均复核；缺 scope 或 scope 漂移时 fail-closed。
- `smart-import` session/file/chunk 的 14 个入口在读取请求体、文件、幂等记录、审计记录或触发 LLM 前先验证父链；幂等 key 按 sandbox + session 隔离。
- `import_story_sessions.sandbox_id` 迁移只通过指向真实 sandbox 的唯一 client 父链回填；无父项或父项无效的旧行保持隔离，迁移可重复执行。
- 云端任务附件下载/缩略图/文本/OCR/转写需要认证并验证组织与成员；路径解析、符号链接、大小和临时文件生命周期均 fail-closed。
- 桌面附件云代理统一转发当前沙箱 Bearer，token 不进入 URL/日志；无 token 时零匿名网络请求。
- 链接导入同时执行 URL 规范化、私网/回环阻断和重定向目标复核。
- OCR/AI 只使用当前组织自己的 `org_ai_config`，不回退到全局环境 key。

## 迁移与兼容原则

1. 已有行只有在父资源唯一证明 sandbox 时回填。
2. 无法证明归属的旧行不绑定当前 sandbox，也不因用户当前登录状态获得访问权。
3. 直接 ID 跨沙箱统一返回 404，且在文件读取、网络请求、LLM、审计与幂等写之前终止。
4. 缓存 key/目录必须包含规范化 sandbox；旧无 scope 缓存不再命中。

## 最终复验

| 门禁 | 最终结果 |
| --- | --- |
| Desktop 后端全量 | 依赖升级后最终重跑：`640 passed, 2 skipped, 10 xfailed, 703 warnings in 165.44s`，退出码 0，无 FAILED、无意外 XPASS |
| Cloud 后端全量 | 依赖升级、PyJWT 迁移及版本对齐后最终重跑：`246 passed, 3746 warnings in 113.26s`，退出码 0，无 failed/skip/xfail/XPASS |
| 四文件竞态安全组合 | 最终依赖状态下连续两轮 `44/44`、`44/44`，分别 29.30s、29.21s |
| 目标路径独立矩阵 | auth 4、慢 AI/direct-ID 7、mirror sync 5、云附件父级/direct-ID 45、幂等两文件 37，全部通过 |
| `scripts/audit_sandbox_contract.py` | `Sandbox contract audit passed.` |
| `scripts/audit_sandbox_queries.py` | `Sandbox query audit passed. Legacy unscoped query debt reduced by 37.`；新增未隔离查询 0 |
| `npm run audit:python-deps` | Desktop lock 0 漏洞；Cloud lock 仅精确忽略上游无修复的 `PYSEC-2026-311`，且 Chroma 嵌入式隔离门禁先通过 |
| `npm audit --audit-level=high --registry=https://registry.npmjs.org` | `found 0 vulnerabilities` |
| Electron 43.1.0 兼容门 | build、calendar 7/7、collab merge、source cleanliness、`dist:mac-local` 与包内 Python startup smoke 全部通过；未安装、未发布 |
| 0.28.1 版本一致性 | 根 package/lock、Desktop runtime、两个 Python project/lock、Cloud FastAPI 与 `/health`、DMG 默认产物名均已对齐 `0.28.1`；两个 `uv lock --check` 通过 |
| 全部已改 Python 文件 `py_compile` | 通过 |
| `git diff --check` | 通过 |

此处的 10 个 xfail 仍是 `_known_failing.py` 里显式登记的历史债务；2 个 skip 分别是废弃 NarrativeKernel 占位测试和 macOS 上不适用的 Windows Credential Manager 测试。原有的 1 个稳定 XPASS 已连续独立通过后从历史 xfail 清单中精准移除，最终全量已是普通 PASS，没有意外 XPASS。

warnings 为 FastAPI `on_event`、Starlette TestClient 迁移提示、passlib `crypt`、SWIG 类型与 pytest collection 弃用/收集警告，本轮无由警告隐藏的失败。查询审计证明本轮没有新增未基线化的无 scope SQL，不代表历史通用 evidence resolver 等旧授权债务已全部清零。

## 依赖安全判定

- Desktop Python 锁文件已经过冻结导出审计，允许例外数为 0。
- Cloud 从 `python-jose` 迁移到固定 `HS256` 的 PyJWT，移除了未使用但存在无修复时序攻击的 `ecdsa` 传递依赖；JWT 正反向回归 5/5 通过。
- ChromaDB 1.5.9 是当前可用最新版，但上游尚未修复 `PYSEC-2026-311`。本应用只在 `knowledge_store.py` 懒加载嵌入式 `PersistentClient`，不挂载 Chroma HTTP/server/API，也禁止 `trust_remote_code`；`audit_chromadb_isolation.py` 先验证这一边界，随后依赖审计只允许忽略这一个精确 ID。该结论是攻击路径隔离，不冒充上游已修复。
- 不采用 ChromaDB 0.x 盲降，因为真实 1.x 持久化数据未经备份副本的恢复与查询兼容验证；安全边界和移除例外步骤见 `cloud_backend/DEPENDENCY_SECURITY.md`。

## 非阻断架构债务

1. 静态基线仍含历史未隔离查询：baseline 396 行（347 个稳定 identity），当前 352 条（311 个 identity），本轮新增 0。门禁的“reduced by 37”不能解释成全仓历史债务归零。
2. 某些旧 `client_resource_users` 关系表没有 `sandbox_id`；当 client 已删除且无法重建父链时，只能 fail-closed，无法安全清理其陈旧关联。
3. 幂等 claim、业务写入和 complete 尚未位于同一数据库事务；极端情况下若进程在业务提交后、complete 前崩溃，TTL 后重试仍可能重复创建。当前正常重试、并发 claim 与作用域隔离回归均已通过，后续应以 outbox/同事务完成态彻底消除窗口。

本轮目标路径经独立复核为 confirmed P0=0、P1=0、P2=0；以上三项按全代码口径单独保留，不能被“本轮全绿”掩盖。

## 交付边界

- 分支：`fix/cloud-task-scope-0281`
- 不推 `main`，不部署生产，不修改线上活库。
- 最终以本地 HEAD 与 `git ls-remote origin refs/heads/fix/cloud-task-scope-0281` 完全一致为交付完成证据。
