"""Workflow paths with fake models and fake MCP calls (no network, no API keys)."""

import uuid

import pytest
from langgraph.types import Command

from enrich import workflow
from enrich.schemas import Attributes, Classification, Listing, Patterns, RelevantIds

LISTING = Listing(title="Floral Wrap Midi Dress for Women", bullets=["Soft rayon"] * 5,
                  description="An original description.", keywords=["wrap dress"],
                  patterns=Patterns(top_keywords=["wrap"], title_structure="Type + attrs",
                                    buyer_review_themes=["fit"]))


class FakeModel:
    def __init__(self, responses: dict):
        self.responses = responses
        self.schema = None

    def bind(self, schema):
        self.schema = schema
        return self

    async def ainvoke(self, _prompt):
        return self.responses[self.schema]


@pytest.fixture
def fake(monkeypatch):
    responses = {
        Classification: Classification(category="womens_dresses", category_label="Women's dresses",
                                       subcategory="wrap midi dress"),
        Attributes: Attributes(values={"fit": "relaxed", "fabric": "rayon"}),  # size missing
        RelevantIds: RelevantIds(keep_ids=["1", "2"]),
        Listing: LISTING,
    }
    monkeypatch.setattr(workflow, "structured",
                        lambda tier, schema, temperature=0.0: FakeModel(responses).bind(schema))

    async def fake_fetch(marketplace, category, query):
        return [{"id": str(i), "title": f"{marketplace} dress {i}", "description": ""}
                for i in range(1, 4)]

    monkeypatch.setattr(workflow, "fetch_listings", fake_fetch)
    return responses


def cfg():
    return {"configurable": {"thread_id": str(uuid.uuid4())}}


@pytest.mark.anyio
async def test_pauses_for_missing_size_then_generates(fake):
    graph, config = workflow.build_graph(), cfg()
    first = await graph.ainvoke({"description": "wrap dress", "marketplaces": ["amazon", "ebay"]},
                                config)
    assert first["__interrupt__"][0].value["missing"] == ["size"]

    final = await graph.ainvoke(Command(resume={"size": "S-XL"}), config)
    assert final["attributes"]["size"] == "S-XL"
    assert set(final["results"]) == {"amazon", "ebay"}
    assert final["results"]["amazon"]["competitor_count"] == 2
    assert any("only 2 closely matching" in w for w in final["warnings"])


@pytest.mark.anyio
async def test_prohibited_on_one_marketplace_drops_only_that_one(fake):
    fake[Classification] = fake[Classification].model_copy(
        update={"prohibited_on": ["ebay"], "prohibited_reason": "replica goods"})
    fake[Attributes] = Attributes(values={"size": "M", "fit": "slim", "fabric": "silk"})
    out = await workflow.build_graph().ainvoke(
        {"description": "x", "marketplaces": ["amazon", "ebay"]}, cfg())
    assert "ebay" in out["blocked"] and list(out["results"]) == ["amazon"]


@pytest.mark.anyio
async def test_prohibited_everywhere_stops(fake):
    fake[Classification] = fake[Classification].model_copy(
        update={"prohibited_on": ["amazon", "ebay"], "prohibited_reason": "weapons"})
    out = await workflow.build_graph().ainvoke(
        {"description": "x", "marketplaces": ["amazon", "ebay"]}, cfg())
    assert out["status"] == "prohibited" and "results" not in out


@pytest.mark.anyio
async def test_unsupported_category_message(fake):
    fake[Classification] = Classification(category="other", category_label="Men's shoes")
    out = await workflow.build_graph().ainvoke(
        {"description": "running shoes", "marketplaces": ["ebay"]}, cfg())
    assert out["status"] == "unsupported" and out["message"] == "Men's shoes not supported yet"


@pytest.fixture
def anyio_backend():
    return "asyncio"
