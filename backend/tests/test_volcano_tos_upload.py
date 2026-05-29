"""I1b · 火山 TOS upload_file 单测

覆盖：
- 必填字段缺失（ak/sk/bucket/object_key/local_path）抛 RuntimeError + 用户可读消息
- 上传成功：put_object_from_file 被正确调用、pre_signed_url 取到 signed_url、
  返回 StorageUploadResult 含 url / expires_at / size_bytes / object_key
- 上传失败：TosServerError 401/403/404 抛 RuntimeError 带定向提示
- 上传失败：其他异常被包成 RuntimeError 而不是原生类型泄漏
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.object_storage.volcano_tos_provider import (  # noqa: E402
    VolcanoTosObjectStorageProvider,
)


# ---- 测试用 stub：模拟 tos SDK 的最小表面 ----------------------------


class _FakeSignedUrl:
    def __init__(self, url: str) -> None:
        self.signed_url = url


class _FakeTosClient:
    """记录调用 + 可注入失败行为的 fake tos client。"""

    def __init__(self, ak: str, sk: str, endpoint: str, region: str) -> None:
        self.ak = ak
        self.sk = sk
        self.endpoint = endpoint
        self.region = region
        self.put_calls: list[tuple[str, str, str]] = []
        self.sign_calls: list[tuple[Any, str, str, int]] = []
        self.put_error: Exception | None = None
        self.sign_url = "https://fake-tos.example.com/yiyu/audio.webm?signed=1"

    def put_object_from_file(self, bucket: str, key: str, local_path: str) -> None:
        self.put_calls.append((bucket, key, local_path))
        if self.put_error is not None:
            raise self.put_error

    def pre_signed_url(self, method: Any, bucket: str, key: str, expires: int) -> _FakeSignedUrl:
        self.sign_calls.append((method, bucket, key, expires))
        return _FakeSignedUrl(self.sign_url)


class _FakeTosServerError(Exception):
    """模拟 tos.exceptions.TosServerError。"""

    def __init__(self, status_code: int, message: str, code: str = "FakeCode", request_id: str = "rid-1") -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.code = code
        self.request_id = request_id


class _FakeHttpMethodType:
    Http_Method_Get = "GET"


class _FakeTosExceptionsModule:
    TosServerError = _FakeTosServerError


class _FakeTosModule:
    """替换 sys.modules['tos'] 用的 fake，配合 monkeypatch.setitem。"""

    def __init__(self) -> None:
        self.last_client: _FakeTosClient | None = None
        self.HttpMethodType = _FakeHttpMethodType
        self.exceptions = _FakeTosExceptionsModule

    def TosClientV2(self, ak: str, sk: str, endpoint: str, region: str) -> _FakeTosClient:  # noqa: N802
        client = _FakeTosClient(ak, sk, endpoint, region)
        self.last_client = client
        return client


@pytest.fixture
def fake_tos(monkeypatch: pytest.MonkeyPatch) -> _FakeTosModule:
    fake = _FakeTosModule()
    monkeypatch.setitem(sys.modules, "tos", fake)
    return fake


@pytest.fixture
def tmp_audio_file() -> Path:
    fd, path = tempfile.mkstemp(suffix=".webm", prefix="yiyu-test-")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(b"FAKE_AUDIO_PAYLOAD_1234567890")
        yield Path(path)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


@pytest.fixture
def provider() -> VolcanoTosObjectStorageProvider:
    return VolcanoTosObjectStorageProvider()


def _full_creds() -> dict[str, str]:
    return {"access_key_id": "TEST_ACCESS_KEY_ID", "secret_access_key": "TEST_SECRET_ACCESS_KEY"}


def _full_extra() -> dict[str, str]:
    return {"endpoint": "tos-cn-beijing.volces.com", "region": "cn-beijing", "bucket": "yiyu-test-bucket"}


# ---- 必填字段缺失 --------------------------------------------------------


class TestUploadFileValidation:
    def test_missing_access_key_raises(self, provider, tmp_audio_file: Path) -> None:
        with pytest.raises(RuntimeError, match="Access Key"):
            provider.upload_file(
                local_path=str(tmp_audio_file),
                object_key="audio/test.webm",
                credentials={"secret_access_key": "SK"},
                extra_config=_full_extra(),
            )

    def test_missing_bucket_raises(self, provider, tmp_audio_file: Path) -> None:
        with pytest.raises(RuntimeError, match="Bucket"):
            provider.upload_file(
                local_path=str(tmp_audio_file),
                object_key="audio/test.webm",
                credentials=_full_creds(),
                extra_config={"endpoint": "x", "region": "y", "bucket": ""},
            )

    def test_missing_object_key_raises(self, provider, tmp_audio_file: Path) -> None:
        with pytest.raises(RuntimeError, match="object_key"):
            provider.upload_file(
                local_path=str(tmp_audio_file),
                object_key="",
                credentials=_full_creds(),
                extra_config=_full_extra(),
            )

    def test_missing_local_file_raises(self, provider) -> None:
        with pytest.raises(RuntimeError, match="本地文件"):
            provider.upload_file(
                local_path="/tmp/does-not-exist-xyz-yiyu.webm",
                object_key="audio/test.webm",
                credentials=_full_creds(),
                extra_config=_full_extra(),
            )


# ---- 上传成功 ------------------------------------------------------------


class TestUploadFileSuccess:
    def test_returns_signed_url_and_metadata(
        self, provider, fake_tos: _FakeTosModule, tmp_audio_file: Path
    ) -> None:
        result = provider.upload_file(
            local_path=str(tmp_audio_file),
            object_key="recordings/abc/chunk-001.webm",
            credentials=_full_creds(),
            extra_config=_full_extra(),
            expires_seconds=120,
        )
        assert result.object_key == "recordings/abc/chunk-001.webm"
        assert result.url.startswith("https://")
        assert result.expires_at  # ISO 字符串
        assert result.size_bytes == tmp_audio_file.stat().st_size

        # 调用面验证
        client = fake_tos.last_client
        assert client is not None
        assert client.put_calls == [("yiyu-test-bucket", "recordings/abc/chunk-001.webm", str(tmp_audio_file))]
        assert len(client.sign_calls) == 1
        method, bucket, key, expires = client.sign_calls[0]
        assert method == _FakeHttpMethodType.Http_Method_Get
        assert bucket == "yiyu-test-bucket"
        assert key == "recordings/abc/chunk-001.webm"
        assert expires == 120

    def test_uses_defaults_when_endpoint_region_missing(
        self, provider, fake_tos: _FakeTosModule, tmp_audio_file: Path
    ) -> None:
        provider.upload_file(
            local_path=str(tmp_audio_file),
            object_key="x.webm",
            credentials=_full_creds(),
            extra_config={"bucket": "b"},
        )
        client = fake_tos.last_client
        assert client is not None
        assert client.endpoint == "tos-cn-beijing.volces.com"
        assert client.region == "cn-beijing"


# ---- 上传失败 ------------------------------------------------------------


class TestUploadFileFailures:
    def test_tos_server_error_403_maps_to_runtime_error_with_hint(
        self, provider, fake_tos: _FakeTosModule, tmp_audio_file: Path
    ) -> None:
        def _trigger_403(*_args: Any, **_kw: Any) -> None:
            raise _FakeTosServerError(403, "AccessDenied")

        # patch FakeTosClient 上的 put_object_from_file
        orig_factory = fake_tos.TosClientV2

        def _factory(*args: Any, **kw: Any) -> _FakeTosClient:
            client = orig_factory(*args, **kw)
            client.put_error = _FakeTosServerError(403, "AccessDenied")
            return client

        fake_tos.TosClientV2 = _factory  # type: ignore[assignment]

        with pytest.raises(RuntimeError) as excinfo:
            provider.upload_file(
                local_path=str(tmp_audio_file),
                object_key="x.webm",
                credentials=_full_creds(),
                extra_config=_full_extra(),
            )
        msg = str(excinfo.value)
        assert "403" in msg
        assert "ak/sk" in msg

    def test_tos_server_error_404_maps_with_bucket_hint(
        self, provider, fake_tos: _FakeTosModule, tmp_audio_file: Path
    ) -> None:
        orig_factory = fake_tos.TosClientV2

        def _factory(*args: Any, **kw: Any) -> _FakeTosClient:
            client = orig_factory(*args, **kw)
            client.put_error = _FakeTosServerError(404, "NoSuchBucket")
            return client

        fake_tos.TosClientV2 = _factory  # type: ignore[assignment]

        with pytest.raises(RuntimeError) as excinfo:
            provider.upload_file(
                local_path=str(tmp_audio_file),
                object_key="x.webm",
                credentials=_full_creds(),
                extra_config=_full_extra(),
            )
        assert "桶不存在" in str(excinfo.value)

    def test_generic_exception_wrapped_to_runtime_error(
        self, provider, fake_tos: _FakeTosModule, tmp_audio_file: Path
    ) -> None:
        orig_factory = fake_tos.TosClientV2

        def _factory(*args: Any, **kw: Any) -> _FakeTosClient:
            client = orig_factory(*args, **kw)
            client.put_error = ValueError("boom")
            return client

        fake_tos.TosClientV2 = _factory  # type: ignore[assignment]

        with pytest.raises(RuntimeError, match="boom"):
            provider.upload_file(
                local_path=str(tmp_audio_file),
                object_key="x.webm",
                credentials=_full_creds(),
                extra_config=_full_extra(),
            )
