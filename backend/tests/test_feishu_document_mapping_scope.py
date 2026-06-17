from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent


def test_feishu_document_mapping_remains_one_to_one_without_pull_copy_entrypoints() -> None:
    backend_main = (ROOT / "app" / "main.py").read_text(encoding="utf-8")
    renderer_app = (REPO_ROOT / "src" / "renderer" / "App.tsx").read_text(encoding="utf-8")

    assert "feishu-pull" not in backend_main
    assert "feishu_pull" not in backend_main
    assert "拉取飞书版本" not in renderer_app
    assert "拉取飞书版本到本地" not in renderer_app


def test_local_backend_exposes_feishu_delivery_profile_proxy() -> None:
    backend_main = (ROOT / "app" / "main.py").read_text(encoding="utf-8")

    assert '@app.get("/api/v1/me/feishu-delivery-profile"' in backend_main
    assert '@app.post("/api/v1/me/feishu-delivery-profile"' in backend_main
