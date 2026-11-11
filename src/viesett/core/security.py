import asyncio
import hashlib
import json
import logging
import time
from collections import OrderedDict
from typing import Protocol
from uuid import uuid4

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from viesett.core.config import Settings

logger = logging.getLogger("viesett.http")


class RateLimiter(Protocol):
    def allow(self, key: str) -> bool: ...


class MemoryRateLimiter:
    """Bounded fixed windows for the milestone's single-process server."""

    def __init__(self, limit: int, max_keys: int = 10000) -> None:
        self.limit = limit
        self.max_keys = max_keys
        self.windows: OrderedDict[str, tuple[float, int]] = OrderedDict()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        while self.windows and next(iter(self.windows.values()))[0] <= now - 60:
            self.windows.popitem(last=False)
        if key not in self.windows and len(self.windows) >= self.max_keys:
            return False
        start, count = self.windows.get(key, (now, 0))
        if count >= self.limit:
            return False
        self.windows[key] = (start, count + 1)
        return True


class SecurityMiddleware:
    def __init__(self, app: ASGIApp, settings: Settings, limiter: RateLimiter) -> None:
        self.app = app
        self.settings = settings
        self.limiter = limiter

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        correlation_id = str(uuid4())
        scope.setdefault("state", {})["correlation_id"] = correlation_id
        started = False
        status = 500

        async def secure_send(message: Message) -> None:
            nonlocal started, status
            if message["type"] == "http.response.start":
                started = True
                status = message["status"]
                headers = list(message.get("headers", []))
                headers.extend(
                    [
                        (b"cache-control", b"private, no-store"),
                        (b"x-content-type-options", b"nosniff"),
                        (b"referrer-policy", b"no-referrer"),
                        (b"x-correlation-id", correlation_id.encode()),
                    ]
                )
                message["headers"] = headers
            await send(message)

        async def respond(code: int, detail: str) -> None:
            await JSONResponse({"detail": detail}, status_code=code)(scope, receive, secure_send)

        try:
            client = str(scope.get("client", ("unknown",))[0])
            key = "network:" + hashlib.sha256(client.encode()).hexdigest()
            if not self.limiter.allow(key):
                await respond(429, "Rate limit exceeded")
                return
            headers = dict(scope.get("headers", []))
            try:
                declared = int(headers.get(b"content-length", b"0"))
            except ValueError:
                await respond(400, "Invalid content length")
                return
            if declared < 0 or b"content-encoding" in headers:
                await respond(400, "Unsupported request framing")
                return
            if declared > self.settings.max_request_bytes:
                await respond(413, "Request too large")
                return
            async with asyncio.timeout(self.settings.request_timeout_seconds):
                # Bound the actual streamed body as well as Content-Length, before parsing.
                body = bytearray()
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    body.extend(message.get("body", b""))
                    if len(body) > self.settings.max_request_bytes:
                        await respond(413, "Request too large")
                        return
                    if not message.get("more_body", False):
                        break
                consumed = False

                async def bounded_receive() -> Message:
                    nonlocal consumed
                    if consumed:
                        return await receive()
                    consumed = True
                    return {"type": "http.request", "body": bytes(body), "more_body": False}

                await self.app(scope, bounded_receive, secure_send)
        except TimeoutError:
            if not started:
                await respond(408, "Request timed out")
        except Exception:
            # Deliberate allowlist logging: no exception repr, body, text, URL or headers.
            if not started:
                await respond(500, "Internal error")
        finally:
            logger.info(
                json.dumps(
                    {
                        "event": "http_request",
                        "method": scope["method"],
                        "status": status,
                        "correlation_id": correlation_id,
                    }
                )
            )
