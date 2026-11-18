"""OpenRouter chat models by tier (cheap / mid / top)."""

from typing import Literal

from langchain_openai import ChatOpenAI

from enrich.config import get_settings

Tier = Literal["cheap", "mid", "top"]


def get_model(tier: Tier, temperature: float = 0.0) -> ChatOpenAI:
    s = get_settings()
    model = {"cheap": s.model_cheap, "mid": s.model_mid, "top": s.model_top}[tier]
    # Only route to hosts that honour every parameter we send (forced tool calls for
    # structured output); otherwise some hosts silently ignore it and return plain text.
    provider: dict = {"require_parameters": True}
    if s.openrouter_provider_order:
        # Pin providers (e.g. US-hosted ones) and refuse fallbacks to others.
        provider["order"] = [p.strip() for p in s.openrouter_provider_order.split(",") if p.strip()]
        provider["allow_fallbacks"] = False
    return ChatOpenAI(
        model=model,
        api_key=s.openrouter_api_key,
        base_url=s.openrouter_base_url,
        temperature=temperature,
        extra_body={"provider": provider},
        default_headers={"X-Title": "EnrichDescription"},
    )
