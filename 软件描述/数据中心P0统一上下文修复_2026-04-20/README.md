# 数据中心 P0 改动说明（README）

## 1. 我改了哪些东西（已完成）
- 新增统一上下文服务：`backend/app/services/analysis_context.py`
  - `infer_page_intent`
  - `build_client_page_context_pack`
  - `build_task_page_context_pack`
  - `compute_context_quality`
  - `decide_answer_policy`
  - `build_answer_material`
  - `build_fallback_user_answer`
- 在后端主路由中新增 page-context API：
  - `GET /api/v1/clients/{client_id}/page-context`
  - `GET /api/v1/tasks/{task_id}/page-context`
- 把 workspace chat 接入统一 PageContextPack/AnswerPolicy 路由，并保持旧响应字段兼容。
- 修复回答质量关键路由：
  - 状态问题回到 state-first
  - official registry 维持 registry-only
  - intro/evidence/drilldown 保持证据优先
  - hybrid 在有 linked evidence 时不强制 raw fallback
  - AI 失败回退仍可读
- 任务 understanding 在无缓存时返回 lightweight understanding（保留 `_pending=true`）。
- 新增并补齐回归测试：
  - `backend/tests/test_analysis_context_p0.py`
  - `backend/tests/test_workspace_chat_regression.py`（补断言）

## 2. 还有哪些东西没有做（按 P0 边界故意不做）
- 没做完整“虚拟公司 2.0”自治控制面（heartbeat/预算治理/全自动值班等）。
- 没有自动写入 `approved judgment`（只保留 candidate/draft/awaiting_review 边界）。
- 没有绕过 analysis/approval/resolver 边界直接写 official layer。
- 没有实现无限制外部联网抓取（External Evidence Card Phase 2 才做）。
- 没有大规模重写前端（只做最小 API/types 接入并保留旧接口并存）。
- meeting_detail / mobile_consult / topic_radar / strategic_cockpit 的 page-context 本阶段未完整接入（仅预留）。

## 3. 你要看的源码在哪
- 先看 `INDEX.md`。
- 代码已全部转为 Markdown。
- `backend/app/main.py` 体积过大，已拆分为多个 part 文件。

## 4. 说明
- 本目录收录的是“本次数据中心 P0 改动相关文件的完整当前源码”，不是整个平台所有文件。
