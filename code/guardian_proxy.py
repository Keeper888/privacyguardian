"""
PrivacyGuardian Proxy
=====================
Sits between an AI client (Claude Code, an OpenAI SDK app, ...) and the
provider's API. Real values never leave this machine: the courier swaps them
for tokens on the way out and back on the way in.

    client --(real values)--> proxy --(tokens)--> provider
    client <-(real values)--- proxy <-(tokens)--- provider

Port: PG_PORT (default 4666). Upstream when the client gives no target:
PG_UPSTREAM (default https://api.anthropic.com).
"""

import os
import time
from contextlib import asynccontextmanager
from typing import Optional
from urllib.parse import urlparse

import httpx
import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse

from courier import Courier, SSEUnprotector
from llm_endpoints import get_provider_for_domain

PORT = int(os.environ.get("PG_PORT", "4666"))
DEFAULT_UPSTREAM = os.environ.get("PG_UPSTREAM", "https://api.anthropic.com").rstrip("/")

HOP_BY_HOP = {"connection", "keep-alive", "transfer-encoding", "te", "trailer", "upgrade",
              "proxy-authorization", "proxy-authenticate", "content-length", "content-encoding", "host"}


class PrivacyGuardianProxy:
    def __init__(self, courier: Optional[Courier] = None, transport: Optional[httpx.AsyncBaseTransport] = None):
        self.courier = courier or Courier()
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(600.0, connect=15.0),
                                        follow_redirects=False, transport=transport)
        self.requests_processed = 0
        self.upstream_calls = 0
        self.start_time = time.time()

    # kept for callers of the old API
    def protect_text(self, text: str, provider: Optional[str] = None) -> str:
        return self.courier.protect_text(text, provider)

    def unprotect_text(self, text: str) -> str:
        return self.courier.unprotect_text(text)

    def _target(self, request: Request) -> str:
        explicit = request.headers.get("x-target-url")
        base = DEFAULT_UPSTREAM
        if explicit:
            u = urlparse(explicit)
            base = f"{u.scheme}://{u.netloc}"
        url = base + request.url.path
        if request.url.query:
            url += "?" + request.url.query
        return url

    async def proxy_request(self, request: Request) -> Response:
        self.requests_processed += 1
        url = self._target(request)
        host = urlparse(url).netloc
        provider = get_provider_for_domain(host)
        provider_name = provider.name if provider else host

        headers = {k: v for k, v in request.headers.items()
                   if k.lower() not in HOP_BY_HOP and k.lower() != "x-target-url"}
        headers["accept-encoding"] = "gzip"   # something httpx can always decode

        body = self.courier.protect_body(await request.body(), provider_name)

        upstream = self.client.build_request(request.method, url, headers=headers, content=body)
        try:
            self.upstream_calls += 1
            resp = await self.client.send(upstream, stream=True)   # one call, streamed or not (issue #17)
        except httpx.HTTPError as e:
            return Response(content=f'{{"error":"upstream unreachable: {type(e).__name__}"}}',
                            status_code=502, media_type="application/json")

        out_headers = {k: v for k, v in resp.headers.items() if k.lower() not in HOP_BY_HOP}
        ctype = resp.headers.get("content-type", "")

        if "text/event-stream" in ctype and resp.status_code < 400:
            sse = SSEUnprotector(self.courier)

            async def relay():
                try:
                    async for chunk in resp.aiter_bytes():
                        out = sse.feed(chunk)
                        if out:
                            yield out
                    tail = sse.close()
                    if tail:
                        yield tail
                finally:
                    await resp.aclose()

            return StreamingResponse(relay(), status_code=resp.status_code,
                                     headers=out_headers, media_type=ctype)

        content = await resp.aread()
        await resp.aclose()
        return Response(content=self.courier.unprotect_body(content),
                        status_code=resp.status_code, headers=out_headers)

    def uptime(self) -> str:
        s = int(time.time() - self.start_time)
        return f"{s // 3600} h {s % 3600 // 60} min"


def create_app(proxy: Optional[PrivacyGuardianProxy] = None) -> FastAPI:
    proxy = proxy or PrivacyGuardianProxy()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        print(f"PrivacyGuardian courier on http://127.0.0.1:{PORT} -> {DEFAULT_UPSTREAM}", flush=True)
        yield
        await proxy.client.aclose()

    app = FastAPI(title="PrivacyGuardian", lifespan=lifespan)
    app.state.proxy = proxy

    @app.get("/__guardian__/health")
    async def health():
        return {"status": "healthy", "uptime": proxy.uptime()}

    @app.get("/__guardian__/stats")
    async def stats():
        return {
            "uptime": proxy.uptime(),
            "requests_processed": proxy.requests_processed,
            "upstream_calls": proxy.upstream_calls,
            "pii_items_protected": proxy.courier.items_protected,
            "vault": proxy.courier.vault.stats(),
        }

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
    async def catch_all(request: Request, path: str):
        return await proxy.proxy_request(request)

    return app


def main():
    uvicorn.run(create_app(), host="127.0.0.1", port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
