from __future__ import annotations

import re
from typing import Mapping
from urllib.parse import urlsplit

ALLOWED_LOCAL_ORIGINS = (
    'http://127.0.0.1:4173',
    'http://localhost:4173',
    'http://127.0.0.1:5173',
    'http://localhost:5173',
    'app://renderer',
)

ALLOWED_LOCAL_ORIGIN_REGEX = r'^https?://(127\.0\.0\.1|localhost)(:\d+)?$|^app://renderer$'
_ALLOWED_LOCAL_ORIGIN_PATTERN = re.compile(ALLOWED_LOCAL_ORIGIN_REGEX)

LOCAL_ORIGIN_EXEMPT_PATHS = {
    '/api/v1/system/health',
    '/api/v1/channels/feishu/events',
}


def _normalize_origin(value: str | None) -> str:
    if not value:
        return ''
    parsed = urlsplit(value)
    if not parsed.scheme or not parsed.netloc:
        return ''
    return f'{parsed.scheme}://{parsed.netloc}'


def is_allowed_local_origin(value: str | None) -> bool:
    origin = _normalize_origin(value)
    if not origin:
        return False
    if origin in ALLOWED_LOCAL_ORIGINS:
        return True
    return bool(_ALLOWED_LOCAL_ORIGIN_PATTERN.match(origin))


def validate_local_browser_request(path: str, headers: Mapping[str, str], method: str = 'GET') -> str | None:
    if not path.startswith('/api/v1/') or path in LOCAL_ORIGIN_EXEMPT_PATHS:
        return None
    origin = _normalize_origin(headers.get('origin'))
    if is_allowed_local_origin(origin):
        return None
    referer = _normalize_origin(headers.get('referer'))
    if is_allowed_local_origin(referer):
        return None
    if method.upper() == 'OPTIONS':
        return None
    sec_fetch_site = headers.get('sec-fetch-site', '').strip().lower()
    if sec_fetch_site == 'cross-site':
        return 'Cross-site browser requests are not allowed'
    if origin and not is_allowed_local_origin(origin):
        return 'Origin is not allowed'
    if referer and not is_allowed_local_origin(referer):
        return 'Referer is not allowed'
    return None
