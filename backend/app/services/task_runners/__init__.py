"""本地推理 task runner 注册表。

每个 runner 模块实现 `process(db, ai_service, task) -> dict`，被
`local_model_optimizer.run_due_local_model_tasks` 按 task_type 调度。

设计原则：
- 每个 runner 自包含：拿 payload → 跑推理 → 写结果 → 返回 result_json
- 失败抛异常即可，外层负责 mark_failed + 重试
- runner 内部不做 governor 检查（调度器已经把关）
- runner 应当幂等：同 input_hash 的 task 重跑不会留下脏数据
"""
