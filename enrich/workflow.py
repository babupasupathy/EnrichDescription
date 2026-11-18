"""LangGraph workflow (PRD: Functional requirements F2-F7).

classify -> extract_attributes -> [pause for missing attributes] -> fetch_listings
         -> filter_listings -> generate (+ compliance check and one fix pass) -> END

Run with a thread id; if the result contains "__interrupt__", resume with
`Command(resume={"attr": "value", ...})` on the same thread.
"""

import asyncio
import json
from typing import Any, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from enrich import prompts
from enrich.categories import CATEGORIES
from enrich.compliance import check_listing
from enrich.llm import get_model
from enrich.mcp_client import fetch_listings
from enrich.schemas import Attributes, Classification, Listing, RelevantIds

MIN_RELEVANT = 5


class State(TypedDict, total=False):
    description: str
    marketplaces: list[str]
    # outputs
    status: str  # "ok" | "prohibited" | "unsupported"
    message: str
    blocked: dict[str, str]  # marketplace -> reason it was dropped
    category: str
    subcategory: str
    attributes: dict[str, str]
    competitors: dict[str, list[dict]]
    warnings: list[str]
    results: dict[str, dict]


STRUCTURED_ATTEMPTS = 3


class _Structured:
    """Structured-output model that retries when the model answers in prose (parsed as None)."""

    def __init__(self, tier: str, schema: type, temperature: float):
        self.tier, self.schema = tier, schema
        self.runnable = get_model(tier, temperature).with_structured_output(
            schema, method="function_calling")

    async def ainvoke(self, prompt):
        for _ in range(STRUCTURED_ATTEMPTS):
            if (out := await self.runnable.ainvoke(prompt)) is not None:
                return out
        raise RuntimeError(f"The {self.tier} model returned no {self.schema.__name__} after "
                           f"{STRUCTURED_ATTEMPTS} tries.")


def structured(tier: str, schema: type, temperature: float = 0.0) -> _Structured:
    return _Structured(tier, schema, temperature)


# --- F2: policy and category -------------------------------------------------------------
async def classify(state: State) -> dict:
    c: Classification = await structured("cheap", Classification).ainvoke(
        prompts.CLASSIFY.format(marketplaces=state["marketplaces"],
                                description=state["description"]))
    blocked = {m: f"This category is prohibited on {m.title()}: {c.prohibited_reason}"
               for m in c.prohibited_on if m in state["marketplaces"]}
    remaining = [m for m in state["marketplaces"] if m not in blocked]
    if not remaining:
        return {"status": "prohibited", "blocked": blocked,
                "message": "This product is prohibited on every marketplace you chose."}
    if c.category == "other":
        return {"status": "unsupported", "blocked": blocked,
                "message": f"{c.category_label} not supported yet"}
    return {"status": "ok", "blocked": blocked, "marketplaces": remaining,
            "category": c.category, "subcategory": c.subcategory}


def after_classify(state: State) -> str:
    return "extract_attributes" if state["status"] == "ok" else END


# --- F3: attributes, pausing once for anything missing ------------------------------------
async def extract_attributes(state: State) -> dict:
    cat = CATEGORIES[state["category"]]
    attrs: Attributes = await structured("cheap", Attributes).ainvoke(
        prompts.EXTRACT.format(attributes=", ".join(cat.required_attributes + cat.optional_attributes),
                               description=state["description"]))
    values = {k: v for k, v in attrs.values.items() if v and v.strip()}
    missing = [a for a in cat.required_attributes if a not in values]
    if missing:
        answers: dict[str, str] = interrupt({"missing": missing, "found": values})
        values.update({k: v for k, v in answers.items() if v})
    return {"attributes": values}


# --- F4: competitor listings via MCP, marketplaces in parallel ----------------------------
async def fetch(state: State) -> dict:
    cat = CATEGORIES[state["category"]]
    query = state["subcategory"] or cat.label
    results = await asyncio.gather(
        *(fetch_listings(m, cat, query) for m in state["marketplaces"]), return_exceptions=True)
    competitors, warnings = {}, list(state.get("warnings", []))
    for m, r in zip(state["marketplaces"], results):
        if isinstance(r, Exception):
            warnings.append(f"{m}: couldn't fetch competitor listings ({r}); writing without them.")
            competitors[m] = []
        else:
            competitors[m] = r
    return {"competitors": competitors, "warnings": warnings}


# --- F5: relevance filter (mid model) -----------------------------------------------------
async def filter_listings(state: State) -> dict:
    model = structured("mid", RelevantIds)
    warnings = list(state.get("warnings", []))

    async def one(m: str, items: list[dict]) -> list[dict]:
        if not items:
            return items
        lines = "\n".join(f"{i['id']} | {i['title']}" for i in items)
        try:
            keep: RelevantIds = await model.ainvoke(prompts.FILTER.format(
                subcategory=state["subcategory"], attributes=state["attributes"], listings=lines))
        except Exception as e:  # The filter is an optimisation; never fail the run over it.
            warnings.append(f"{m}: couldn't filter competitor listings ({e}); using all of them.")
            return items
        ids = set(keep.keep_ids)
        kept = [i for i in items if i["id"] in ids]
        if len(kept) < MIN_RELEVANT:
            warnings.append(f"{m}: only {len(kept)} closely matching listings found.")
        return kept

    markets = list(state["competitors"])
    filtered = await asyncio.gather(*(one(m, state["competitors"][m]) for m in markets))
    return {"competitors": dict(zip(markets, filtered)), "warnings": warnings}


# --- F6 + F7: generate, check, fix once ---------------------------------------------------
def _competitor_text(items: list[dict]) -> str:
    keep = ("title", "description", "price", "rating", "ratings_total", "bought_past_month",
            "seller_feedback_pct", "reviews")
    return json.dumps([{k: i.get(k) for k in keep if i.get(k)} for i in items], indent=1)[:30000]


async def generate_one(state: State, marketplace: str) -> dict[str, Any]:
    items = state["competitors"].get(marketplace, [])
    model = structured("top", Listing, temperature=0.4)
    prompt = prompts.GENERATE.format(
        marketplace=marketplace.title(), description=state["description"],
        attributes=state["attributes"], competitors=_competitor_text(items) if items else "(none)",
        marketplace_rules=prompts.MARKETPLACE_RULES[marketplace])
    listing: Listing = await model.ainvoke(prompt)

    sources = [f"{i.get('title', '')} {i.get('description', '')}" for i in items]
    issues = check_listing(marketplace, listing.title, listing.bullets, listing.description, sources)
    if issues:
        fix = prompts.FIX.format(issues="\n".join(f"- {i.rule}: {i.detail}" for i in issues))
        listing = await model.ainvoke([("user", prompt), ("assistant", listing.model_dump_json()),
                                       ("user", fix)])
        issues = check_listing(marketplace, listing.title, listing.bullets, listing.description,
                               sources)
    return {"listing": listing.model_dump(),
            "issues": [i.__dict__ for i in issues],
            "competitor_count": len(items)}


async def generate(state: State) -> dict:
    outs = await asyncio.gather(*(generate_one(state, m) for m in state["marketplaces"]))
    return {"results": dict(zip(state["marketplaces"], outs))}


def build_graph(checkpointer=None):
    g = StateGraph(State)
    g.add_node("classify", classify)
    g.add_node("extract_attributes", extract_attributes)
    g.add_node("fetch_listings", fetch)
    g.add_node("filter_listings", filter_listings)
    g.add_node("generate", generate)
    g.add_edge(START, "classify")
    g.add_conditional_edges("classify", after_classify, ["extract_attributes", END])
    g.add_edge("extract_attributes", "fetch_listings")
    g.add_edge("fetch_listings", "filter_listings")
    g.add_edge("filter_listings", "generate")
    g.add_edge("generate", END)
    return g.compile(checkpointer=checkpointer or InMemorySaver())
