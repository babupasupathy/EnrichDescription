"""Supported categories and the attributes each one needs (PRD: Scope)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Category:
    key: str
    label: str
    required_attributes: tuple[str, ...]
    optional_attributes: tuple[str, ...]
    ebay_category_id: str
    amazon_bestsellers_url: str


CATEGORIES: dict[str, Category] = {
    "womens_dresses": Category(
        key="womens_dresses",
        label="Women's dresses",
        required_attributes=("size", "fit", "fabric"),
        optional_attributes=("color", "length", "sleeve", "occasion"),
        ebay_category_id="63861",
        amazon_bestsellers_url="https://www.amazon.com/gp/bestsellers/fashion/1045024",
    ),
    "cell_phone_cases": Category(
        key="cell_phone_cases",
        label="Cell phone cases",
        required_attributes=("compatible_device", "material"),
        optional_attributes=("protection_level", "features", "color"),
        ebay_category_id="20349",
        amazon_bestsellers_url="https://www.amazon.com/gp/bestsellers/wireless/2407760011",
    ),
}

MARKETPLACES = ("amazon", "ebay")
