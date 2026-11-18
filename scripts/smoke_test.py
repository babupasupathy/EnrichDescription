"""Live check of the deployed MCP servers.

Usage (token from the clipboard, never printed):
  MCP_AUTH_TOKEN="$(pbpaste)" uv run python -m scripts.smoke_test https://YOUR-SERVICE.run.app

Costs: 1 eBay API call, 1 Rainforest credit (bestsellers without product details).
"""

import asyncio
import os
import sys

from enrich.mcp_client import call_tool


async def main(base: str) -> None:
    base = base.rstrip("/")
    if not os.environ.get("MCP_AUTH_TOKEN"):
        sys.exit("Set MCP_AUTH_TOKEN first (see usage above).")

    ebay = await call_tool(f"{base}/ebay/mcp", "search_listings",
                           {"query": "floral wrap dress", "category_id": "63861", "limit": 3})
    print(f"eBay: {len(ebay)} listings")
    for i in ebay:
        print(f"  ${i['price']:>7.2f}  {i['title'][:70]}")

    amazon = await call_tool(f"{base}/amazon/mcp", "bestseller_listings",
                             {"bestsellers_url": "https://www.amazon.com/gp/bestsellers/fashion/1045024",
                              "limit": 3, "with_details": False})
    print(f"Amazon: {len(amazon)} bestsellers")
    for i in amazon:
        print(f"  #{i['rank']}  {i['rating']}★  {i['title'][:70]}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    asyncio.run(main(sys.argv[1]))
