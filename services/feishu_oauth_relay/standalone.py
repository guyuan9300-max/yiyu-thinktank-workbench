from __future__ import annotations

import hashlib
import hmac
import html
import json
import os
import sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


DEFAULT_DB_PATH = "/var/lib/yiyu-oauth-relay/relay.sqlite3"
HOST = os.environ.get("YIYU_FEISHU_OAUTH_RELAY_HOST", "127.0.0.1")
PORT = int(os.environ.get("YIYU_FEISHU_OAUTH_RELAY_PORT", "47840"))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _db_path() -> Path:
    return Path(os.environ.get("YIYU_FEISHU_OAUTH_RELAY_DB", DEFAULT_DB_PATH)).expanduser()


def _connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS relay_sessions (
            state_hash TEXT PRIMARY KEY,
            claim_secret_hash TEXT NOT NULL,
            code TEXT,
            error_message TEXT,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            received_at TEXT,
            claimed_at TEXT
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_relay_sessions_expires ON relay_sessions(expires_at)")
    conn.commit()
    return conn


def _cleanup(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM relay_sessions WHERE expires_at <= ? OR claimed_at IS NOT NULL", (_now_iso(),))
    conn.commit()


def _callback_page(title: str, detail: str, *, success: bool) -> bytes:
    tone = "#16a34a" if success else "#dc2626"
    markup = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{html.escape(title)}</title><style>
body{{margin:0;padding:32px;background:#f8fafc;color:#0f172a;font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Helvetica Neue',sans-serif}}
.card{{max-width:560px;margin:8vh auto;background:#fff;border:1px solid #e2e8f0;border-radius:24px;padding:28px;box-shadow:0 16px 48px rgba(15,23,42,.08)}}
.badge{{display:inline-flex;padding:6px 12px;border-radius:999px;color:{tone};background:#f1f5f9;font-size:12px;font-weight:700}}
h1{{font-size:24px;margin:18px 0 12px;line-height:1.3}}p{{font-size:14px;line-height:1.75;color:#475569;margin:0 0 12px}}
</style></head><body><main class="card"><div class="badge">{'授权已收到' if success else '授权失败'}</div>
<h1>{html.escape(title)}</h1><p>{html.escape(detail)}</p><p>现在可以回到益语智库软件，软件会自动刷新飞书授权状态。</p></main></body></html>"""
    return markup.encode("utf-8")


class RelayHandler(BaseHTTPRequestHandler):
    server_version = "YiYuFeishuOAuthRelay/1.0"

    def log_message(self, fmt: str, *args) -> None:  # Do not log OAuth query strings here.
        return

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, status: int, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = min(int(self.headers.get("Content-Length") or "0"), 16384)
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/healthz":
            with _connect() as conn:
                _cleanup(conn)
            self._send_json(200, {"status": "ok"})
            return
        if parsed.path != "/feishu/member/callback":
            self._send_json(404, {"detail": "not found"})
            return
        query = parse_qs(parsed.query, keep_blank_values=True)
        state = (query.get("state") or [""])[0]
        code = (query.get("code") or [""])[0]
        error = (query.get("error_description") or query.get("error") or [""])[0]
        if not state:
            self._send_html(200, _callback_page("飞书授权失败", "缺少授权状态，请回到益语智库软件重新发起授权。", success=False))
            return
        state_hash = _sha256(state)
        with _connect() as conn:
            _cleanup(conn)
            row = conn.execute("SELECT * FROM relay_sessions WHERE state_hash = ?", (state_hash,)).fetchone()
            if not row:
                self._send_html(200, _callback_page("飞书授权失败", "这次授权会话不存在或已过期，请回到益语智库软件重新发起授权。", success=False))
                return
            if error:
                conn.execute("UPDATE relay_sessions SET error_message = ?, received_at = ? WHERE state_hash = ?", (error[:240], _now_iso(), state_hash))
                conn.commit()
                self._send_html(200, _callback_page("飞书授权失败", "飞书没有完成本次授权，请回到益语智库软件重新发起。", success=False))
                return
            if not code.strip():
                conn.execute("UPDATE relay_sessions SET error_message = ?, received_at = ? WHERE state_hash = ?", ("飞书没有返回有效授权码。", _now_iso(), state_hash))
                conn.commit()
                self._send_html(200, _callback_page("飞书授权失败", "飞书没有返回有效授权码，请回到益语智库软件重新发起授权。", success=False))
                return
            conn.execute("UPDATE relay_sessions SET code = ?, error_message = NULL, received_at = ? WHERE state_hash = ?", (code.strip(), _now_iso(), state_hash))
            conn.commit()
        self._send_html(200, _callback_page("飞书授权已收到", "授权结果已安全回传，稍后会由你的组织云端完成绑定。", success=True))

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        try:
            payload = self._read_json()
        except Exception:
            self._send_json(400, {"detail": "invalid json"})
            return
        if parsed.path == "/feishu/member/sessions":
            state_hash = str(payload.get("stateHash") or "").strip().lower()
            claim_secret_hash = str(payload.get("claimSecretHash") or "").strip().lower()
            expires_at = str(payload.get("expiresAt") or "").strip()
            if not state_hash or not claim_secret_hash or not expires_at:
                self._send_json(400, {"detail": "missing required fields"})
                return
            try:
                if _parse_iso(expires_at) <= datetime.now(timezone.utc):
                    self._send_json(400, {"detail": "expired session"})
                    return
            except ValueError:
                self._send_json(400, {"detail": "invalid expiresAt"})
                return
            with _connect() as conn:
                _cleanup(conn)
                conn.execute(
                    """
                    INSERT INTO relay_sessions(state_hash, claim_secret_hash, code, error_message, created_at, expires_at, received_at, claimed_at)
                    VALUES(?, ?, NULL, NULL, ?, ?, NULL, NULL)
                    ON CONFLICT(state_hash) DO UPDATE SET claim_secret_hash=excluded.claim_secret_hash, code=NULL, error_message=NULL,
                        created_at=excluded.created_at, expires_at=excluded.expires_at, received_at=NULL, claimed_at=NULL
                    """,
                    (state_hash, claim_secret_hash, _now_iso(), expires_at),
                )
                conn.commit()
            self._send_json(200, {"status": "registered", "expiresAt": expires_at})
            return
        if parsed.path == "/feishu/member/code/claim":
            state = str(payload.get("state") or "")
            claim_secret = str(payload.get("claimSecret") or "")
            state_hash = _sha256(state)
            claim_secret_hash = _sha256(claim_secret)
            with _connect() as conn:
                _cleanup(conn)
                row = conn.execute("SELECT * FROM relay_sessions WHERE state_hash = ?", (state_hash,)).fetchone()
                if not row:
                    self._send_json(404, {"detail": "not found"})
                    return
                if not hmac.compare_digest(str(row["claim_secret_hash"]), claim_secret_hash):
                    self._send_json(403, {"detail": "forbidden"})
                    return
                if row["error_message"]:
                    message = str(row["error_message"])
                    conn.execute("DELETE FROM relay_sessions WHERE state_hash = ?", (state_hash,))
                    conn.commit()
                    self._send_json(200, {"status": "error", "errorMessage": message})
                    return
                if not row["code"]:
                    self._send_json(200, {"status": "pending", "receivedAt": row["received_at"]})
                    return
                code = str(row["code"])
                received_at = row["received_at"]
                conn.execute("UPDATE relay_sessions SET claimed_at = ? WHERE state_hash = ?", (_now_iso(), state_hash))
                conn.commit()
            self._send_json(200, {"status": "authorized", "code": code, "receivedAt": received_at})
            return
        self._send_json(404, {"detail": "not found"})


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), RelayHandler)
    print(f"YiYu Feishu OAuth Relay listening on {HOST}:{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
