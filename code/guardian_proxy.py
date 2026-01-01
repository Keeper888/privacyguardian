"""
PrivacyGuardian Proxy Server - "The Pond"
==========================================
A transparent proxy that encrypts PII before it reaches ANY LLM API
and decrypts tokens in responses so you see the original data locally.

Supports: Anthropic, OpenAI, Google, Azure, Mistral, Cohere, Groq, and more.
"""

import asyncio
import json
import os
import sqlite3
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from cryptography.fernet import Fernet
import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse
import uvicorn

from pii_detector import PIIDetector, PIIMatch, PIIType
from llm_endpoints import (
    LLMProvider, LLM_PROVIDERS,
    get_provider_for_domain, get_all_domains
)
from request_parser import RequestParser, StreamingParser


# ============================================================================
# Event Bus - For GUI updates and notifications
# ============================================================================

class EventBus:
    """Simple event bus for real-time updates to GUI/notifications"""

    def __init__(self):
        self.listeners: Dict[str, List[Callable]] = {}

    def subscribe(self, event: str, callback: Callable):
        if event not in self.listeners:
            self.listeners[event] = []
        self.listeners[event].append(callback)

    def emit(self, event: str, data: Any = None):
        if event in self.listeners:
            for callback in self.listeners[event]:
                try:
                    callback(data)
                except Exception as e:
                    print(f"Event handler error: {e}")


# Global event bus
events = EventBus()


# ============================================================================
# Token Vault - Local encrypted storage for PII mappings
# ============================================================================

class TokenVault:
    """Secure local storage for PII <-> Token mappings"""

    def __init__(self, vault_path: str = "~/.privacyguardian"):
        self.vault_dir = Path(vault_path).expanduser()
        self.vault_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.vault_dir, 0o700)

        self.key_file = self.vault_dir / "master.key"
        self.db_file = self.vault_dir / "vault.db"

        self._init_key()
        self._init_db()

    def _init_key(self):
        if self.key_file.exists():
            with open(self.key_file, 'rb') as f:
                self.master_key = f.read()
        else:
            self.master_key = Fernet.generate_key()
            with open(self.key_file, 'wb') as f:
                f.write(self.master_key)
            os.chmod(self.key_file, 0o600)
        self.cipher = Fernet(self.master_key)

    def _init_db(self):
        self.conn = sqlite3.connect(str(self.db_file), check_same_thread=False)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS tokens (
                token_id TEXT PRIMARY KEY,
                pii_type TEXT NOT NULL,
                encrypted_value BLOB NOT NULL,
                created_at TEXT NOT NULL,
                last_used TEXT NOT NULL,
                use_count INTEGER DEFAULT 1,
                provider TEXT
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                provider TEXT,
                pii_type TEXT,
                action TEXT,
                masked_value TEXT
            )
        """)
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_created ON tokens(created_at)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_activity ON activity_log(timestamp)")
        self.conn.commit()
        os.chmod(self.db_file, 0o600)

    def encrypt_pii(self, value: str, pii_type: PIIType, provider: str = None) -> str:
        value_hash = hashlib.sha256(value.encode()).hexdigest()[:12]
        token_id = f"◈PG:{pii_type.value[:4]}_{value_hash}◈"

        cursor = self.conn.execute(
            "SELECT token_id FROM tokens WHERE token_id = ?", (token_id,)
        )
        is_new = cursor.fetchone() is None

        if not is_new:
            # Existing token - just update use count, no activity log
            self.conn.execute(
                "UPDATE tokens SET last_used = ?, use_count = use_count + 1 WHERE token_id = ?",
                (datetime.utcnow().isoformat(), token_id)
            )
            self.conn.commit()
        else:
            # New token - insert and log activity
            encrypted = self.cipher.encrypt(value.encode())
            self.conn.execute(
                "INSERT INTO tokens (token_id, pii_type, encrypted_value, created_at, last_used, provider) VALUES (?, ?, ?, ?, ?, ?)",
                (token_id, pii_type.value, encrypted, datetime.utcnow().isoformat(), datetime.utcnow().isoformat(), provider)
            )

            # Log activity only for NEW tokens
            masked = f"{value[:3]}***{value[-3:]}" if len(value) > 6 else "***"
            self.conn.execute(
                "INSERT INTO activity_log (timestamp, provider, pii_type, action, masked_value) VALUES (?, ?, ?, ?, ?)",
                (datetime.utcnow().isoformat(), provider, pii_type.value, "protected", masked)
            )
            self.conn.commit()

            # Emit event for GUI only for NEW tokens
            events.emit("pii_protected", {
                "type": pii_type.value,
                "masked": masked,
                "provider": provider,
                "timestamp": datetime.utcnow().isoformat()
            })

        return token_id, is_new

    def decrypt_token(self, token_id: str) -> Optional[str]:
        cursor = self.conn.execute(
            "SELECT encrypted_value FROM tokens WHERE token_id = ?", (token_id,)
        )
        row = cursor.fetchone()
        if row:
            try:
                return self.cipher.decrypt(row[0]).decode()
            except Exception:
                return None
        return None

    def get_all_tokens(self) -> Dict[str, str]:
        cursor = self.conn.execute("SELECT token_id, encrypted_value FROM tokens")
        result = {}
        for token_id, encrypted in cursor.fetchall():
            try:
                result[token_id] = self.cipher.decrypt(encrypted).decode()
            except Exception:
                continue
        return result

    def get_recent_activity(self, limit: int = 50) -> List[Dict]:
        cursor = self.conn.execute(
            "SELECT timestamp, provider, pii_type, action, masked_value FROM activity_log ORDER BY id DESC LIMIT ?",
            (limit,)
        )
        return [
            {"timestamp": row[0], "provider": row[1], "pii_type": row[2], "action": row[3], "masked_value": row[4]}
            for row in cursor.fetchall()
        ]

    def stats(self) -> dict:
        cursor = self.conn.execute("SELECT COUNT(*), SUM(use_count) FROM tokens")
        count, uses = cursor.fetchone()

        cursor = self.conn.execute("SELECT pii_type, COUNT(*) FROM tokens GROUP BY pii_type")
        by_type = {row[0]: row[1] for row in cursor.fetchall()}

        cursor = self.conn.execute(
            "SELECT provider, COUNT(*) FROM activity_log WHERE provider IS NOT NULL GROUP BY provider"
        )
        by_provider = {row[0]: row[1] for row in cursor.fetchall()}

        return {
            "total_tokens": count or 0,
            "total_uses": uses or 0,
            "by_type": by_type,
            "by_provider": by_provider
        }


# ============================================================================
# Privacy Guardian Proxy - Universal LLM Interceptor
# ============================================================================

class PrivacyGuardianProxy:
    """Universal proxy for all LLM APIs with PII protection."""

    def __init__(self):
        self.detector = PIIDetector()
        self.vault = TokenVault()
        self.client = httpx.AsyncClient(timeout=120.0, follow_redirects=True)

        # Stats
        self.requests_processed = 0
        self.pii_items_protected = 0
        self.start_time = datetime.utcnow()

        # Request parser with our protect/unprotect functions
        self.parser = RequestParser(
            pii_protector=self._protect_text_for_parser,
            pii_unprotector=self.unprotect_text
        )

        # Current provider context for parser
        self._current_provider = None

    def _protect_text_for_parser(self, text: str) -> str:
        """Wrapper for parser that uses current provider context"""
        return self.protect_text(text, self._current_provider)

    def protect_text(self, text: str, provider: str = None) -> str:
        """Detect PII in text and replace with encrypted tokens"""
        matches = self.detector.detect(text)
        if not matches:
            return text

        matches.sort(key=lambda m: m.start, reverse=True)

        protected = text
        for match in matches:
            token, is_new = self.vault.encrypt_pii(match.value, match.pii_type, provider)
            protected = protected[:match.start] + token + protected[match.end:]
            if is_new:
                self.pii_items_protected += 1

        return protected

    def unprotect_text(self, text: str) -> str:
        """Replace tokens with original PII values"""
        tokens = self.vault.get_all_tokens()
        result = text
        for token, value in tokens.items():
            if token in result:
                result = result.replace(token, value)
        return result

    async def proxy_request(self, request: Request) -> Response:
        """Proxy a request to the appropriate LLM API with PII protection"""
        self.requests_processed += 1

        # Determine target from headers or default
        host = request.headers.get("host", "")
        target_url_header = request.headers.get("x-target-url")

        if target_url_header:
            # Explicit target URL provided
            parsed = urlparse(target_url_header)
            host = parsed.netloc
            target_base = f"{parsed.scheme}://{parsed.netloc}"
        else:
            # Determine from host header or default to Anthropic
            if not host or host.startswith("localhost") or host.startswith("127."):
                target_base = "https://api.anthropic.com"
                host = "api.anthropic.com"
            else:
                target_base = f"https://{host}"

        # Find provider configuration
        provider = get_provider_for_domain(host)
        provider_name = provider.name if provider else "Unknown"
        self._current_provider = provider_name

        # Build target URL
        path = request.url.path
        query = str(request.url.query) if request.url.query else ""
        full_url = f"{target_base}{path}"
        if query:
            full_url += f"?{query}"

        # Prepare headers
        headers = dict(request.headers)
        headers.pop("host", None)
        headers.pop("content-length", None)
        headers.pop("x-target-url", None)
        headers["host"] = host

        # Process request body - PROTECT PII
        body = await request.body()
        pii_count = 0

        if body and provider:
            body, pii_count = self.parser.protect_request(body, provider)
        elif body:
            # Generic protection for unknown providers
            try:
                text = body.decode('utf-8')
                protected = self.protect_text(text, provider_name)
                body = protected.encode('utf-8')
            except:
                pass

        # Check if streaming
        is_streaming = False
        if body:
            try:
                req_json = json.loads(body)
                is_streaming = req_json.get("stream", False)
            except:
                pass

        # Emit request event
        events.emit("request", {
            "provider": provider_name,
            "pii_count": pii_count,
            "streaming": is_streaming,
            "url": full_url
        })

        if is_streaming:
            return await self._proxy_streaming(request.method, full_url, headers, body, provider)
        else:
            return await self._proxy_regular(request.method, full_url, headers, body, provider)

    async def _proxy_regular(self, method: str, url: str, headers: dict, body: bytes, provider: Optional[LLMProvider]) -> Response:
        """Handle non-streaming request"""
        try:
            response = await self.client.request(
                method=method,
                url=url,
                headers=headers,
                content=body
            )
        except Exception as e:
            return Response(
                content=json.dumps({"error": str(e)}),
                status_code=502,
                media_type="application/json"
            )

        # UNPROTECT tokens in response
        content = response.content
        if provider:
            content = self.parser.unprotect_response(content, provider)
        else:
            try:
                content = self.unprotect_text(content.decode()).encode()
            except:
                pass

        # Filter hop-by-hop headers
        resp_headers = dict(response.headers)
        for h in ['transfer-encoding', 'connection', 'keep-alive', 'content-encoding', 'content-length']:
            resp_headers.pop(h, None)

        return Response(
            content=content,
            status_code=response.status_code,
            headers=resp_headers
        )

    async def _proxy_streaming(self, method: str, url: str, headers: dict, body: bytes, provider: Optional[LLMProvider]) -> Response:
        """Handle streaming request with real-time token unprotection"""
        streaming_parser = StreamingParser(self.unprotect_text)

        try:
            # Make the request and check status first
            response = await self.client.request(
                method=method,
                url=url,
                headers=headers,
                content=body
            )

            # If error response, return it directly (don't try to stream)
            if response.status_code >= 400:
                return Response(
                    content=response.content,
                    status_code=response.status_code,
                    headers=dict(response.headers)
                )

            # For streaming, we need to make a new streaming request
            async def stream_generator():
                try:
                    async with self.client.stream(method, url, headers=headers, content=body) as stream_response:
                        # Check for errors
                        if stream_response.status_code >= 400:
                            yield stream_response.read()
                            return
                        async for chunk in stream_response.aiter_bytes():
                            yield streaming_parser.process_chunk(chunk)
                except Exception as e:
                    yield f"data: {json.dumps({'error': str(e)})}\n\n".encode()

            return StreamingResponse(
                stream_generator(),
                media_type="text/event-stream"
            )

        except Exception as e:
            return Response(
                content=json.dumps({"error": str(e)}),
                status_code=500,
                media_type="application/json"
            )

    def get_uptime(self) -> str:
        delta = datetime.utcnow() - self.start_time
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours}h {minutes}m {seconds}s"


# ============================================================================
# FastAPI Application
# ============================================================================

guardian = PrivacyGuardianProxy()


@asynccontextmanager
async def lifespan(app: FastAPI):
    providers_list = ", ".join([p.name for p in list(LLM_PROVIDERS.values())[:5]]) + "..."
    print(f"""
╔══════════════════════════════════════════════════════════════════╗
║                     🛡️  PRIVACY GUARDIAN  🛡️                      ║
║                     Universal LLM Protection                     ║
║                                                                  ║
║  Your data swims freely in the local pond, but leaves           ║
║  encrypted and anonymous when it ventures outside.              ║
║                                                                  ║
║  Proxy: http://localhost:6660                                   ║
║  Status: http://localhost:6660/__guardian__/stats               ║
║                                                                  ║
║  Supported: {providers_list:<43}║
╚══════════════════════════════════════════════════════════════════╝
    """)

    # Emit startup event for notifications
    events.emit("startup", {"port": 6660, "providers": list(LLM_PROVIDERS.keys())})

    yield
    await guardian.client.aclose()


app = FastAPI(title="PrivacyGuardian", lifespan=lifespan)


# Define specific routes FIRST (before catch-all)
@app.get("/__guardian__/stats")
async def get_stats():
    """Get protection statistics"""
    vault_stats = guardian.vault.stats()
    return {
        "status": "active",
        "uptime": guardian.get_uptime(),
        "requests_processed": guardian.requests_processed,
        "pii_items_protected": guardian.pii_items_protected,
        "vault": vault_stats,
        "supported_providers": list(LLM_PROVIDERS.keys())
    }


@app.get("/__guardian__/activity")
async def get_activity():
    """Get recent activity log"""
    return {"activity": guardian.vault.get_recent_activity(50)}


@app.get("/__guardian__/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "uptime": guardian.get_uptime()}


# Catch-all route LAST
@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def proxy_all(request: Request, path: str):
    """Catch-all route that proxies everything"""
    return await guardian.proxy_request(request)


def main():
    """Run the Privacy Guardian proxy"""
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=6660,
        log_level="warning"
    )


if __name__ == "__main__":
    main()
