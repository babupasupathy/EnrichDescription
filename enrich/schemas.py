"""Structured outputs the models must return."""

from typing import Literal

from pydantic import BaseModel, Field


class Classification(BaseModel):
    """F2: policy and category check (cheap model)."""

    prohibited_on: list[Literal["amazon", "ebay"]] = Field(
        default_factory=list,
        description="Marketplaces where this product is prohibited. Empty if allowed everywhere.",
    )
    prohibited_reason: str = Field("", description="Short reason, citing the policy area.")
    category: Literal["womens_dresses", "cell_phone_cases", "other"]
    category_label: str = Field(description="Human-readable category, e.g. 'Men's shoes'.")
    subcategory: str = Field("", description="e.g. 'maxi dress' or 'iPhone 16 case'.")


class Attributes(BaseModel):
    """F3: attributes pulled from the raw description (cheap model)."""

    values: dict[str, str] = Field(
        default_factory=dict,
        description="Attribute name -> value, only for attributes stated in the description.",
    )


class RelevantIds(BaseModel):
    """F5: relevance filter (mid model)."""

    keep_ids: list[str]


class Patterns(BaseModel):
    top_keywords: list[str]
    title_structure: str
    buyer_review_themes: list[str]


class Listing(BaseModel):
    """F6: one marketplace's generated listing (top model)."""

    title: str
    bullets: list[str]
    description: str
    keywords: list[str]
    patterns: Patterns
