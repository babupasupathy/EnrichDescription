"""OpenRouter chat models by tier (cheap / mid / top)."""

from typing import Literal

from langchain_openai import ChatOpenAI

from enrich.config import get_settings

Tier = Literal["cheap", "mid", "top"]


def get_model(tier: Tier, temperature: float = 0.0) -> ChatOpenAI:
    s = get_settings()
    model = {"cheap": s.model_cheap, "mid": s.model_mid, "top": s.model_top}[tier]
    extra_body = {}
    if s.openrouter_provider_order:
        # Pin providers (e.g. US-hosted ones) and refuse fallbacks to others.
        extra_body["provider"] = {
            "order": [p.strip() for p in s.openrouter_provider_order.split(",") if p.strip()],
            "allow_fallbacks": False,
        }
    return ChatOpenAI(
        model=model,
        api_key=s.openrouter_api_key,
        base_url=s.openrouter_base_url,
        temperature=temperature,
        extra_body=extra_body or None,
        default_headers={"X-Title": "EnrichDescription"},
    )
