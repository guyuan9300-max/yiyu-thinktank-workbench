"""完成测试:_process_path_optimization_task 改用真实 _qwen_generate (P0-C4 完成)。

原状:调用从未实现的 ai_service.generate_local_model_json → 每个 path_opt
任务 AttributeError 失败,文档虚拟归类(virtual_path/tags/owner/project)产线
熄火,document_path_optimizations 表为空,数据中心搜索/内核读不到归类。

修法:套 card-gen 已验证的 _qwen_generate 模板 + 新增 _DOCUMENT_PATH_SCHEMA。

本测试 mock _qwen_generate 返回归类 payload,断言:① 不再 AttributeError;
② 调用走 _qwen_generate 且带 _DOCUMENT_PATH_SCHEMA;③ 归类正确流入
document_path_optimizations 并按 confidence 计算 apply_status。
"""
from __future__ import annotations

from typing import Any

import app.services.local_model_optimizer as mod


class _CaptureDb:
    def __init__(self) -> None:
        self.executed: list[tuple[str, tuple]] = []

    def execute(self, sql: str, params: tuple = ()) -> Any:
        self.executed.append((sql, params))
        return None


class _FakeAi:
    def __init__(self, captured: dict[str, Any]) -> None:
        self._captured = captured

    def _qwen_generate(self, prompt: str, system: str, schema: Any, **kwargs: Any) -> dict[str, Any]:
        self._captured["called"] = True
        self._captured["schema"] = schema
        self._captured["task_kind"] = kwargs.get("task_kind")
        return {
            "virtual_path": "客户A/项目与业务/项目报告",
            "classification_tags": ["项目报告"],
            "recommended_owner": "客户A",
            "recommended_project": "",
            "confidence": 0.81,
            "reason": "依据标题与正文给出虚拟归类。",
            "evidence": ["标题含项目报告"],
        }


def test_path_optimization_uses_qwen_generate_and_persists(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    monkeypatch.setattr(mod, "_load_document_context", lambda db, kid: {"client_id": "c1", "document_title": "X"})
    monkeypatch.setattr(mod, "get_local_model_optimization_settings", lambda db: {"parseModelMode": "online"})

    db = _CaptureDb()
    ai = _FakeAi(captured)
    task = {"knowledge_document_id": "kd1", "model_name": "qwen", "input_hash": "h1"}

    result = mod._process_path_optimization_task(db, ai, task)

    # ① 走了 _qwen_generate(旧代码会 AttributeError on generate_local_model_json)
    assert captured.get("called") is True
    # ② 用了正确的 path schema + 标准深读路由
    assert captured["schema"] is mod._DOCUMENT_PATH_SCHEMA
    assert captured["task_kind"] == "deep_analysis"
    # ③ 归类正确流入返回值 + apply_status 按 confidence(0.81>=0.72 且有路径)= applied
    assert result["virtualPath"] == "客户A/项目与业务/项目报告"
    assert result["classificationTags"] == ["项目报告"]
    assert result["applyStatus"] == "applied"
    # ④ 真的写了 document_path_optimizations
    assert any("document_path_optimizations" in sql for sql, _ in db.executed)
    insert_params = next(p for sql, p in db.executed if "INSERT INTO document_path_optimizations" in sql)
    assert "客户A/项目与业务/项目报告" in insert_params


def test_path_optimization_low_confidence_pending(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}
    monkeypatch.setattr(mod, "_load_document_context", lambda db, kid: {"client_id": "c1"})
    monkeypatch.setattr(mod, "get_local_model_optimization_settings", lambda db: {"parseModelMode": "online"})

    class _LowAi:
        def _qwen_generate(self, *a: Any, **k: Any) -> dict[str, Any]:
            captured["called"] = True
            return {"virtual_path": "X/Y", "confidence": 0.4, "classification_tags": [], "evidence": []}

    result = mod._process_path_optimization_task(_CaptureDb(), _LowAi(), {"knowledge_document_id": "kd2"})
    # 低置信度 → pending_confirmation(不自动应用)
    assert result["applyStatus"] == "pending_confirmation"
