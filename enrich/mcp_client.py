"""Calls the marketplace MCP servers (F4).

The workflow always calls the same tool per marketplace, so it uses a plain MCP client
rather than letting a model choose tools.
"""

import json

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from enrich.categories import Category
from enrich.config import get_settings


async def call_tool(url: str, tool: str, args: dict) -> list[dict]:
    s = get_settings()
    headers = {"Authorization": f"Bearer {s.mcp_auth_token}"} if s.mcp_auth_token else {}
    async with httpx.AsyncClient(headers=headers, timeout=120) as http:
        async with streamable_http_client(url, http_client=http) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool, args)
    if result.isError:
        text = " ".join(getattr(c, "text", "") for c in result.content)
        raise RuntimeError(f"{tool} failed: {text[:300]}")
    return parse_result(result.structuredContent, [getattr(c, "text", "") for c in result.content])


def parse_result(structured: dict | None, texts: list[str]) -> list[dict]:
    """FastMCP wraps list returns as {"result": [...]}; older servers send JSON text."""
    if structured is not None:
        return structured.get("result", structured) if isinstance(structured, dict) else structured
    items: list[dict] = []
    for t in texts:
        data = json.loads(t)
        items.extend(data if isinstance(data, list) else [data])
    return items


async def fetch_listings(marketplace: str, category: Category, query: str) -> list[dict]:
    s = get_settings()
    n = s.listings_per_marketplace
    if marketplace == "ebay":
        return await call_tool(s.mcp_ebay_url, "search_listings",
                               {"query": query, "category_id": category.ebay_category_id,
                                "limit": n})
    if marketplace == "amazon":
        return await call_tool(s.mcp_amazon_url, "bestseller_listings",
                               {"bestsellers_url": category.amazon_bestsellers_url, "limit": n})
    raise ValueError(f"unknown marketplace {marketplace}")
