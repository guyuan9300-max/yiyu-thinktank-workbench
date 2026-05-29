from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from secrets import token_urlsafe
from typing import Final

JWT_SECRET_FILENAME: Final = '.yiyu-cloud-secret'
BOOTSTRAP_USERS_FILENAME: Final = '.yiyu-cloud-bootstrap-users.json'
DEFAULT_BOOTSTRAP_ADMIN_EMAIL: Final = 'admin@example.org'


@dataclass(frozen=True)
class SeedUser:
    user_id: str
    full_name: str
    email: str
    primary_role: str
    account_status: str
    department_id: str | None
    password: str
    password_locked: bool = False


SEED_USER_SPECS: Final = (
    {
        'user_id': 'user_admin',
        'full_name': '系统管理员',
        'email': DEFAULT_BOOTSTRAP_ADMIN_EMAIL,
        'primary_role': 'admin',
        'account_status': 'approved',
        'department_id': None,
        'password_env': 'YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD',
        'legacy_password': None,
    },
)


def _truthy(value: str | None) -> bool:
    return str(value or '').strip().lower() in {'1', 'true', 'yes', 'on'}


def ensure_cloud_secret(data_dir: Path) -> str:
    configured = os.environ.get('YIYU_CLOUD_SECRET_KEY', '').strip()
    if configured:
        return configured
    data_dir.mkdir(parents=True, exist_ok=True)
    secret_path = data_dir / JWT_SECRET_FILENAME
    if secret_path.exists():
        existing = secret_path.read_text(encoding='utf-8').strip()
        if existing:
            return existing
    secret = token_urlsafe(48)
    secret_path.write_text(secret, encoding='utf-8')
    try:
        os.chmod(secret_path, 0o600)
    except OSError:
        pass
    return secret


def _load_bootstrap_password_store(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    normalized: dict[str, dict[str, str]] = {}
    for key, value in payload.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            continue
        normalized[key] = {str(inner_key): str(inner_value) for inner_key, inner_value in value.items()}
    return normalized


def _write_bootstrap_password_store(path: Path, payload: dict[str, dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def resolve_seed_users(data_dir: Path) -> list[SeedUser]:
    insecure_seed_passwords = _truthy(os.environ.get('YIYU_CLOUD_INSECURE_SEED_PASSWORDS'))
    password_store_path = data_dir / BOOTSTRAP_USERS_FILENAME
    password_store = _load_bootstrap_password_store(password_store_path)
    store_changed = False
    resolved: list[SeedUser] = []

    for spec in SEED_USER_SPECS:
        email = os.environ.get('YIYU_CLOUD_BOOTSTRAP_ADMIN_EMAIL', '').strip() if spec['user_id'] == 'user_admin' else ''
        email = email or str(spec['email'])
        password = os.environ.get(str(spec['password_env']), '').strip()
        password_locked = bool(password)
        if not password:
            if insecure_seed_passwords and spec['legacy_password']:
                password = str(spec['legacy_password'])
                password_locked = True
            else:
                stored = password_store.get(str(spec['user_id']), {})
                stored_password = str(stored.get('password', '')).strip()
                if stored_password:
                    password = stored_password
                    if stored.get('email') != email:
                        stored['email'] = email
                        password_store[str(spec['user_id'])] = stored
                        store_changed = True
                else:
                    password = token_urlsafe(18)
                    password_store[str(spec['user_id'])] = {
                        'email': email,
                        'fullName': str(spec['full_name']),
                        'primaryRole': str(spec['primary_role']),
                        'password': password,
                    }
                    store_changed = True
        resolved.append(
            SeedUser(
                user_id=str(spec['user_id']),
                full_name=str(spec['full_name']),
                email=email,
                primary_role=str(spec['primary_role']),
                account_status=str(spec['account_status']),
                department_id=str(spec['department_id']) if spec['department_id'] else None,
                password=password,
                password_locked=password_locked,
            )
        )

    if store_changed and not insecure_seed_passwords:
        _write_bootstrap_password_store(password_store_path, password_store)
    return resolved
