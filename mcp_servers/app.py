"""One ASGI app serving every marketplace MCP server, for Cloud Run.

  /ebay/mcp    eBay Browse API tools
  /amazon/mcp  Rainforest (Amazon) tools
  /healthz     unauthenticated health check

Every MCP request must carry `Authorization: Bearer $MCP_AUTH_TOKEN` (PRD: MCP auth).
Run locally:  uv run uvicorn mcp_servers.app:app --port 8080
"""

import hmac
import os
from contextlib import AsyncExitStack, asynccontextmanager

from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Mount, Route

from mcp_servers import amazon, ebay

SERVERS = {"ebay": ebay.mcp, "amazon": amazon.mcp}


class BearerAuth(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        expected = os.environ.get("MCP_AUTH_TOKEN", "")
        if request.url.path == "/healthz":
            return await call_next(request)
        if not expected:
            return JSONResponse({"error": "server misconfigured: MCP_AUTH_TOKEN not set"}, 500)
        supplied = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
        if not hmac.compare_digest(supplied, expected):
            return JSONResponse({"error": "unauthorized"}, 401)
        return await call_next(request)


@asynccontextmanager
async def lifespan(_app: Starlette):
    async with AsyncExitStack() as stack:
        for server in SERVERS.values():
            await stack.enter_async_context(server.session_manager.run())
        yield


async def healthz(_request: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")


app = Starlette(
    routes=[
        Route("/healthz", healthz),
        *(Mount(f"/{name}", app=server.streamable_http_app()) for name, server in SERVERS.items()),
    ],
    lifespan=lifespan,
)
app.add_middleware(BearerAuth)
