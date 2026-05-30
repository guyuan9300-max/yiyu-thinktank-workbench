"""回归测试:recompute_brand_audit 引用未定义 brand_prop 修复(P0-C1)。

根因:一次没改干净的重命名重构。本地变量改名为 propositions(list),
但 compute_gap 调用处仍写 brand_proposition=brand_prop(旧名)→ NameError。
该调用包在 try/except Exception: pass 里,所以不是崩溃,而是【静默吞掉】:
凡客户有 propositions(常见),品牌审计的"定位差异/对齐"段就被悄悄丢失。

修法:删除多余的 brand_proposition=brand_prop 参数,与 main.py 中已验证
正确的 compute_gap 调用一致(compute_gap 内部用同一函数自算定位)。

本测试驱动 recompute_brand_audit 走到 propositions 非空分支,断言:
compute_gap 被真正调用、其返回的 alignments 被用上(传入 _build_audit_prompt
的 gap_alignments 非空)。旧代码此处 NameError 被吞 → gap_alignments 恒为
[] → 本测试必失败,因此能区分修没修好。
"""
from __future__ import annotations

from typing import Any

import app.services.intelligence_brand_audit as mod


class _Health:
    ready = True


class _AiService:
    def get_health(self) -> _Health:
        return _Health()


def test_compute_gap_alignments_flow_through(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    monkeypatch.setattr(mod, "list_themes", lambda *a, **k: [{"id": "t1"}, {"id": "t2"}])
    monkeypatch.setattr(
        mod,
        "infer_brand_proposition_from_data_center",
        lambda *a, **k: (["稳健可信"], "user"),
    )

    def _fake_compute_gap(*a: Any, **k: Any) -> dict[str, Any]:
        captured["compute_gap_called"] = True
        return {"ok": True, "alignments": [{"theme": "t1"}], "unexpectedThemes": [{"theme": "x"}]}

    monkeypatch.setattr(mod, "compute_gap", _fake_compute_gap)
    monkeypatch.setattr(mod, "_fetch_evidence_quotes", lambda *a, **k: [])

    def _fake_build_prompt(**k: Any) -> str:
        captured["gap_alignments"] = k.get("gap_alignments")
        captured["gap_unexpected"] = k.get("gap_unexpected")
        return "PROMPT"

    monkeypatch.setattr(mod, "_build_audit_prompt", _fake_build_prompt)
    monkeypatch.setattr(mod, "_invoke_llm", lambda *a, **k: "RAW")
    monkeypatch.setattr(
        mod,
        "_normalize_audit",
        lambda raw: {
            "headline": "H",
            "narrative_md": "N",
            "tensions": [],
            "recommendations": [],
            "content_angles": [],
        },
    )
    monkeypatch.setattr(mod, "_persist_audit", lambda *a, **k: {"id": "audit1"})

    result = mod.recompute_brand_audit(
        db=object(),
        ai_service=_AiService(),
        client_id="c1",
        project_module_id=None,
        target_name="某客户",
    )

    # ① 整个流程跑通(旧代码也能跑通,因为 NameError 被吞——所以这条不够,看 ②③)
    assert result["ok"] is True
    # ② compute_gap 真的被调用(旧代码会在构造其参数时 NameError,根本进不了函数体)
    assert captured.get("compute_gap_called") is True
    # ③ 关键:compute_gap 返回的 alignments 流到了 prompt(旧代码此处恒为 [])
    assert captured["gap_alignments"] == [{"theme": "t1"}]
    assert captured["gap_unexpected"] == [{"theme": "x"}]
