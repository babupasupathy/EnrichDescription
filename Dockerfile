# MCP servers for Google Cloud Run (the Streamlit app deploys separately on Streamlit Cloud).
FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

COPY mcp_servers ./mcp_servers

# Cloud Run sets $PORT (default 8080).
CMD ["sh", "-c", "uv run --no-sync uvicorn mcp_servers.app:app --host 0.0.0.0 --port ${PORT:-8080}"]
