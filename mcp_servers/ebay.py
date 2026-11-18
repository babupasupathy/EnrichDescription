"""eBay MCP server: current listings from the eBay Browse API.

Auth: application token via OAuth client credentials.
Docs: https://developer.ebay.com/api-docs/buy/browse/resources/item_summary/methods/search
"""

import base64
import os
import time
from datetime import UTC, datetime, timedelta

import httpx
from mcp.server.fastmcp import FastMCP

from mcp_servers import cache

HOSTS = {"production": "https://api.ebay.com", "sandbox": "https://api.sandbox.ebay.com"}
SCOPE = "https://api.ebay.com/oauth/api_scope"

mcp = FastMCP("ebay-listings", host="0.0.0.0", stateless_http=True)

_token: dict[str, float | str] = {"value": "", "expires": 0.0}


def _host() -> str:
    return HOSTS[os.environ.get("EBAY_ENV", "production")]


async def _get_token(client: httpx.AsyncClient) -> str:
    if _token["value"] and time.time() < float(_token["expires"]) - 60:
        return str(_token["value"])
    creds = f"{os.environ['EBAY_CLIENT_ID']}:{os.environ['EBAY_CLIENT_SECRET']}"
    resp = await client.post(
        f"{_host()}/identity/v1/oauth2/token",
        headers={
            "Authorization": "Basic " + base64.b64encode(creds.encode()).decode(),
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"grant_type": "client_credentials", "scope": SCOPE},
    )
    resp.raise_for_status()
    body = resp.json()
    _token["value"] = body["access_token"]
    _token["expires"] = time.time() + int(body.get("expires_in", 7200))
    return str(_token["value"])


def parse_item(item: dict) -> dict:
    seller = item.get("seller", {})
    return {
        "id": item.get("itemId", ""),
        "title": item.get("title", ""),
        "description": item.get("shortDescription", ""),
        "price": float(item.get("price", {}).get("value", 0) or 0),
        "currency": item.get("price", {}).get("currency", "USD"),
        "condition": item.get("condition", ""),
        "seller_feedback_pct": float(seller.get("feedbackPercentage", 0) or 0),
        "seller_feedback_score": int(seller.get("feedbackScore", 0) or 0),
        "url": item.get("itemWebUrl", ""),
        # The Browse API returns no product rating, sales counts or review text.
        "rating": None,
        "reviews": [],
    }


@mcp.tool()
async def search_listings(query: str, category_id: str, limit: int = 20,
                          listed_within_days: int | None = None) -> list[dict]:
    """Return up to `limit` current eBay US listings for a query within a category.

    Ordered by eBay's best match. Fields: id, title, description, price, condition,
    seller feedback, url. eBay does not expose sales counts or product ratings here.
    """
    limit = max(1, min(limit, 20))
    key = f"ebay:{category_id}:{query.lower()}:{limit}:{listed_within_days}"
    if (hit := cache.get(key)) is not None:
        return hit

    params = {"q": query, "category_ids": category_id, "limit": str(limit)}
    if listed_within_days:
        since = (datetime.now(UTC) - timedelta(days=listed_within_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        params["filter"] = f"itemStartDate:[{since}..]"

    async with httpx.AsyncClient(timeout=20) as client:
        token = await _get_token(client)
        resp = await client.get(
            f"{_host()}/buy/browse/v1/item_summary/search",
            params=params,
            headers={"Authorization": f"Bearer {token}", "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"},
        )
        resp.raise_for_status()
        items = [parse_item(i) for i in resp.json().get("itemSummaries", [])]

    cache.put(key, items)
    return items
