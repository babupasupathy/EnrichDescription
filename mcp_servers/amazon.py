"""Amazon MCP server: bestseller listings via the Rainforest API.

Credits per uncached call: 1 (bestsellers) + 1 per product when details are requested.
Docs: https://docs.trajectdata.com/rainforestapi/product-data-api/overview
"""

import asyncio
import os

import httpx
from mcp.server.fastmcp import FastMCP

from mcp_servers import cache

RAINFOREST_URL = "https://api.rainforestapi.com/request"

mcp = FastMCP("amazon-listings", host="0.0.0.0", stateless_http=True)


async def _request(client: httpx.AsyncClient, **params: str) -> dict:
    resp = await client.get(
        RAINFOREST_URL, params={"api_key": os.environ["RAINFOREST_API_KEY"], **params}
    )
    resp.raise_for_status()
    return resp.json()


def parse_bestseller(b: dict) -> dict:
    return {
        "id": b.get("asin", ""),
        "rank": b.get("rank"),
        "title": b.get("title", ""),
        "description": "",
        "price": float((b.get("price") or {}).get("value", 0) or 0),
        "rating": b.get("rating"),
        "ratings_total": b.get("ratings_total"),
        "url": b.get("link", ""),
        "bought_past_month": None,
        "reviews": [],
    }


def merge_product(listing: dict, product: dict) -> dict:
    bullets = product.get("feature_bullets") or []
    listing["description"] = "\n".join(bullets) or product.get("description", "")
    listing["bought_past_month"] = product.get("recent_sales")  # e.g. "1K+ bought in past month"
    listing["reviews"] = [
        r.get("body", "")[:500] for r in (product.get("top_reviews") or [])[:5] if r.get("body")
    ]
    return listing


@mcp.tool()
async def bestseller_listings(bestsellers_url: str, limit: int = 20,
                              with_details: bool = True) -> list[dict]:
    """Return up to `limit` Amazon US bestsellers for a category, best rank first.

    With details, each item also has its bullets/description, the 'bought in past month'
    badge when Amazon shows one, and up to 5 top review texts.
    """
    limit = max(1, min(limit, 20))
    key = f"amazon:{bestsellers_url}:{limit}:{with_details}"
    if (hit := cache.get(key)) is not None:
        return hit

    async with httpx.AsyncClient(timeout=60) as client:
        data = await _request(client, type="bestsellers", url=bestsellers_url)
        items = [parse_bestseller(b) for b in data.get("bestsellers", [])[:limit]]
        # TODO(M3): if a category has no bestseller list, fall back to a search sorted by rating.
        if with_details and items:
            products = await asyncio.gather(
                *(_request(client, type="product", amazon_domain="amazon.com", asin=i["id"])
                  for i in items),
                return_exceptions=True,
            )
            for item, p in zip(items, products):
                if isinstance(p, dict):
                    merge_product(item, p.get("product", {}))

    cache.put(key, items)
    return items
