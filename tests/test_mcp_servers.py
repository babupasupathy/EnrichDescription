import httpx
import pytest
import respx
from starlette.testclient import TestClient

from mcp_servers import cache, ebay
from mcp_servers.amazon import merge_product, parse_bestseller
from mcp_servers.app import app


def test_parse_ebay_item():
    item = {"itemId": "v1|1|0", "title": "Floral Dress", "shortDescription": "Midi",
            "price": {"value": "29.99", "currency": "USD"},
            "seller": {"feedbackPercentage": "99.1", "feedbackScore": 1200},
            "itemWebUrl": "https://ebay.com/itm/1"}
    p = ebay.parse_item(item)
    assert p["price"] == 29.99 and p["seller_feedback_score"] == 1200 and p["rating"] is None


def test_parse_amazon_bestseller_and_details():
    b = parse_bestseller({"asin": "B01", "rank": 1, "title": "Case", "price": {"value": 9.99},
                          "rating": 4.6, "ratings_total": 5000, "link": "https://amazon.com/dp/B01"})
    merge_product(b, {"feature_bullets": ["Slim", "Drop tested"], "recent_sales": "1K+ bought",
                      "top_reviews": [{"body": "Great fit"}]})
    assert b["description"] == "Slim\nDrop tested"
    assert b["bought_past_month"] == "1K+ bought" and b["reviews"] == ["Great fit"]


@pytest.mark.anyio
@respx.mock
async def test_ebay_search_uses_token_and_caches(monkeypatch):
    monkeypatch.setenv("EBAY_CLIENT_ID", "id")
    monkeypatch.setenv("EBAY_CLIENT_SECRET", "secret")
    monkeypatch.setenv("EBAY_ENV", "sandbox")
    cache.clear()
    ebay._token.update(value="", expires=0.0)
    respx.post("https://api.sandbox.ebay.com/identity/v1/oauth2/token").mock(
        return_value=httpx.Response(200, json={"access_token": "t", "expires_in": 7200}))
    search = respx.get("https://api.sandbox.ebay.com/buy/browse/v1/item_summary/search").mock(
        return_value=httpx.Response(200, json={"itemSummaries": [{"itemId": "1", "title": "A"}]}))

    first = await ebay.search_listings("maxi dress", "63861", limit=5)
    second = await ebay.search_listings("maxi dress", "63861", limit=5)

    assert first == second and first[0]["title"] == "A"
    assert search.call_count == 1
    assert search.calls[0].request.headers["authorization"] == "Bearer t"


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_mcp_requires_bearer_token(monkeypatch):
    monkeypatch.setenv("MCP_AUTH_TOKEN", "s3cret")
    with TestClient(app) as client:
        assert client.get("/healthz").text == "ok"
        assert client.post("/ebay/mcp", json={}).status_code == 401
        ok = client.post("/ebay/mcp", headers={"Authorization": "Bearer s3cret",
                                               "Accept": "application/json, text/event-stream"},
                         json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        assert ok.status_code != 401
