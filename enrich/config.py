"""Settings read from environment variables (.env locally, platform secrets when deployed).

Never hard-code keys. See .env.example for the full list.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # OpenRouter
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    # Model tiers (PRD: Decisions). Exact OpenRouter slugs.
    model_cheap: str = "qwen/qwen3.6-35b-a3b"
    model_mid: str = "minimax/minimax-m3"
    model_top: str = "deepseek/deepseek-v4.1-flash"
    # Only route to providers hosted in these countries (PRD: privacy). Empty = any.
    openrouter_provider_order: str = ""

    # MCP servers (Cloud Run URLs in production, localhost in development)
    mcp_ebay_url: str = "http://localhost:8080/ebay/mcp"
    mcp_amazon_url: str = "http://localhost:8080/amazon/mcp"
    mcp_auth_token: str = ""

    # Limits (PRD: abuse limits)
    max_input_chars: int = 2000
    listings_per_marketplace: int = 20


@lru_cache
def get_settings() -> Settings:
    return Settings()
