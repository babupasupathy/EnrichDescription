"""Prompts for each pipeline stage. Versioned here so evals can track changes."""

CLASSIFY = """You classify a product for US marketplace listing.

1. Policy: list each marketplace in {marketplaces} where this product is PROHIBITED
   (weapons, adult/sexual content, violence, drugs or paraphernalia, counterfeit or replica
   goods, recalled or hazardous items). Give a short reason naming the policy area.
   Ordinary dresses and phone cases are allowed. Use the marketplace policy excerpts below.
2. Category: womens_dresses, cell_phone_cases, or other. For other, give a short
   human-readable category_label such as "Men's shoes".
3. Subcategory: a short phrase, e.g. "floral maxi dress" or "iPhone 16 Pro clear case".

Marketplace policy excerpts (retrieved):
{policy}

Product description:
{description}"""

EXTRACT = """Extract product attributes from the description. Only include attributes the
description actually states; never guess.

Attributes to look for: {attributes}

Product description:
{description}"""

FILTER = """You are filtering competitor listings for relevance to a seller's product.
Keep listings that are the same kind of product (same subcategory and key attributes).
Drop listings that are a different product type or incompatible (e.g. a Galaxy case when
the product is an iPhone case).

Seller's product: {subcategory}
Attributes: {attributes}

Listings (id | title):
{listings}

Return the ids to keep."""

GENERATE = """You write a {marketplace} listing for a US small seller.

Seller's raw description:
{description}

Product attributes (authoritative, use them): {attributes}

Top competitor listings in this category, strongest first:
{competitors}

Instructions:
- First study the competitors and extract PATTERNS only: the keywords that recur, how the
  best titles are structured, and what buyers praise or complain about in reviews.
- Never copy or paraphrase competitor sentences. Write original text about THIS product.
- Do not claim anything the seller did not state (no invented materials, certifications or
  health claims such as "antimicrobial" or "FDA approved").
- Use brand names only as compatibility ("for iPhone 16"), never as if we were that brand.
- {marketplace_rules}
- Follow these {marketplace} policy excerpts (retrieved from our rules summaries):
{policy}

Return: title, bullets, description, keywords (search terms), and the patterns you used."""

MARKETPLACE_RULES = {
    "amazon": (
        "Amazon: title at most 75 characters including spaces, no word more than twice, "
        "no special characters like ! $ ? _ { } ^ ~ # < > *. Exactly 5 bullets, each under "
        "250 characters, starting with a short capitalized benefit. Description 150-300 words."
    ),
    "ebay": (
        "eBay: title at most 80 characters, lead with brand/product type and key attributes, "
        "no ALL CAPS or symbols. eBay has no bullet field: return an empty bullets list and "
        "put key features as short lines inside the description. Description 100-250 words."
    ),
}

FIX = """Your listing broke these rules:
{issues}

Rewrite the listing so it passes, changing only what is needed."""
