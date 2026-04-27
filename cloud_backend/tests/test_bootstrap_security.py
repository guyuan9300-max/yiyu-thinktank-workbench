from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.bootstrap_security import BOOTSTRAP_USERS_FILENAME, JWT_SECRET_FILENAME  # noqa: E402
from app.main import create_app  # noqa: E402


def test_secure_bootstrap_defaults_do_not_accept_source_credentials(tmp_path: Path, monkeypatch):
    data_dir = tmp_path / 'secure-cloud-data'
    monkeypatch.setenv('YIYU_CLOUD_DATA_DIR', str(data_dir))
    monkeypatch.delenv('YIYU_CLOUD_INSECURE_SEED_PASSWORDS', raising=False)
    monkeypatch.delenv('YIYU_CLOUD_SECRET_KEY', raising=False)
    monkeypatch.delenv('YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD', raising=False)
    monkeypatch.delenv('YIYU_CLOUD_GUYUAN_PASSWORD', raising=False)
    monkeypatch.delenv('YIYU_CLOUD_QINGHUA_PASSWORD', raising=False)
    monkeypatch.delenv('YIYU_CLOUD_JIANING_PASSWORD', raising=False)
    monkeypatch.delenv('YIYU_CLOUD_YISHUO_PASSWORD', raising=False)

    app = create_app()
    client = TestClient(app)

    default_login = client.post('/api/v1/auth/login', json={'email': 'admin@yiyu-system.com', 'password': 'Admin123!'})
    assert default_login.status_code == 401, default_login.text

    password_store = json.loads((data_dir / BOOTSTRAP_USERS_FILENAME).read_text(encoding='utf-8'))
    bootstrap_password = password_store['user_admin']['password']
    assert bootstrap_password != 'Admin123!'

    secret_value = (data_dir / JWT_SECRET_FILENAME).read_text(encoding='utf-8').strip()
    assert secret_value
    assert secret_value != 'yiyu-cloud-dev-secret'

    bootstrap_login = client.post('/api/v1/auth/login', json={'email': 'admin@yiyu-system.com', 'password': bootstrap_password})
    assert bootstrap_login.status_code == 200, bootstrap_login.text


def test_seed_password_from_env_refreshes_existing_admin_login(tmp_path: Path, monkeypatch):
    data_dir = tmp_path / 'cloud-data'
    monkeypatch.setenv('YIYU_CLOUD_DATA_DIR', str(data_dir))
    monkeypatch.setenv('YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD', 'Admin123!')

    first_app = create_app()
    first_client = TestClient(first_app)
    first_login = first_client.post('/api/v1/auth/login', json={'email': 'admin@yiyu-system.com', 'password': 'Admin123!'})
    assert first_login.status_code == 200, first_login.text

    monkeypatch.setenv('YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD', 'Admin456!')
    second_app = create_app()
    second_client = TestClient(second_app)

    old_login = second_client.post('/api/v1/auth/login', json={'email': 'admin@yiyu-system.com', 'password': 'Admin123!'})
    assert old_login.status_code == 401, old_login.text

    new_login = second_client.post('/api/v1/auth/login', json={'email': 'admin@yiyu-system.com', 'password': 'Admin456!'})
    assert new_login.status_code == 200, new_login.text
