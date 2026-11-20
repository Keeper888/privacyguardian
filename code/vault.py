"""
PrivacyGuardian - Token Vault
=============================
Keeps the real values on this machine. The AI only ever sees tokens.

Token id  = HMAC-SHA256(local secret, type || value), first 64 bits.
            Without the local secret a token can't be reversed by guessing
            values (see issue #16), and two installs give different tokens.
Stored    = ChaCha20-Poly1305(local key, value), random nonce, type as AAD.
"""

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

TOKEN_OPEN = "◈"   # ◈
TOKEN_CLOSE = "◈"
TOKEN_RE = re.compile(r"◈PG:([A-Z0-9_]{1,8})_([0-9a-f]{16})◈")
TOKEN_MAX_LEN = 40       # longest possible token, used to bound stream carry-over


def home_dir() -> Path:
    return Path(os.environ.get("PG_HOME", "~/.privacyguardian")).expanduser()


def _restrict(path: Path) -> None:
    """Owner-only permissions (POSIX mode; on Windows the user profile ACL already applies)."""
    if sys.platform != "win32":
        os.chmod(path, 0o700 if path.is_dir() else 0o600)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TokenVault:
    def __init__(self, vault_dir: Optional[Path] = None):
        self.dir = Path(vault_dir) if vault_dir else home_dir()
        self.dir.mkdir(parents=True, exist_ok=True)
        _restrict(self.dir)
        self._lock = threading.Lock()
        self._cache: Dict[str, str] = {}
        self._load_keys()
        self._open_db()

    # -- keys ---------------------------------------------------------------

    def _load_keys(self) -> None:
        key_file = self.dir / "courier.key"
        if not key_file.exists():
            # 32 bytes token secret + 32 bytes encryption key, created once, never sent anywhere
            fd = os.open(key_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(secrets.token_bytes(64))
        raw = key_file.read_bytes()
        if len(raw) != 64:
            raise ValueError(f"{key_file} is corrupt (expected 64 bytes)")
        _restrict(key_file)
        self._mac_key, enc_key = raw[:32], raw[32:]
        self._aead = ChaCha20Poly1305(enc_key)

    # -- storage ------------------------------------------------------------

    def _open_db(self) -> None:
        db_file = self.dir / "courier.db"
        self.conn = sqlite3.connect(str(db_file), check_same_thread=False)
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS tokens (
                token_id TEXT PRIMARY KEY,
                pii_type TEXT NOT NULL,
                blob BLOB NOT NULL,
                created_at TEXT NOT NULL,
                last_used TEXT NOT NULL,
                use_count INTEGER DEFAULT 1,
                provider TEXT
            );
            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                provider TEXT,
                pii_type TEXT,
                masked_value TEXT
            );
        """)
        self.conn.commit()
        _restrict(db_file)

    # -- public -------------------------------------------------------------

    def make_token(self, value: str, pii_type: str) -> str:
        digest = hmac.new(self._mac_key, f"{pii_type}\x00{value}".encode("utf-8", "surrogatepass"),
                          hashlib.sha256).hexdigest()[:16]
        prefix = re.sub(r"[^A-Z0-9_]", "", pii_type.upper())[:4] or "PII"
        return f"{TOKEN_OPEN}PG:{prefix}_{digest}{TOKEN_CLOSE}"

    def protect(self, value: str, pii_type: str, provider: Optional[str] = None) -> tuple:
        """Return (token, is_new). Stores the encrypted value on first sight."""
        token = self.make_token(value, pii_type)
        if token in self._cache:
            return token, False
        with self._lock:
            row = self.conn.execute("SELECT 1 FROM tokens WHERE token_id = ?", (token,)).fetchone()
            if row:
                self.conn.execute(
                    "UPDATE tokens SET last_used = ?, use_count = use_count + 1 WHERE token_id = ?",
                    (_now(), token))
                is_new = False
            else:
                nonce = secrets.token_bytes(12)
                blob = nonce + self._aead.encrypt(nonce, value.encode("utf-8", "surrogatepass"),
                                                  pii_type.encode())
                self.conn.execute(
                    "INSERT INTO tokens (token_id, pii_type, blob, created_at, last_used, provider) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (token, pii_type, blob, _now(), _now(), provider))
                masked = f"{value[:2]}***{value[-2:]}" if len(value) > 8 else "***"
                self.conn.execute(
                    "INSERT INTO activity_log (timestamp, provider, pii_type, masked_value) VALUES (?, ?, ?, ?)",
                    (_now(), provider, pii_type, masked))
                is_new = True
            self.conn.commit()
        self._cache[token] = value
        return token, is_new

    def reveal(self, token: str) -> Optional[str]:
        if token in self._cache:
            return self._cache[token]
        with self._lock:
            row = self.conn.execute("SELECT pii_type, blob FROM tokens WHERE token_id = ?", (token,)).fetchone()
        if not row:
            return None
        pii_type, blob = row
        try:
            value = self._aead.decrypt(blob[:12], blob[12:], pii_type.encode()).decode("utf-8", "surrogatepass")
        except Exception:
            return None
        self._cache[token] = value
        return value

    def recent_activity(self, limit: int = 50) -> List[dict]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT timestamp, provider, pii_type, masked_value FROM activity_log ORDER BY id DESC LIMIT ?",
                (limit,)).fetchall()
        return [dict(zip(("timestamp", "provider", "pii_type", "masked_value"), r)) for r in rows]

    def stats(self) -> dict:
        with self._lock:
            count, uses = self.conn.execute("SELECT COUNT(*), SUM(use_count) FROM tokens").fetchone()
            by_type = dict(self.conn.execute("SELECT pii_type, COUNT(*) FROM tokens GROUP BY pii_type").fetchall())
        return {"total_tokens": count or 0, "total_uses": uses or 0, "by_type": by_type}
