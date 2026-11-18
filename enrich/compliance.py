"""F7 deterministic checks: length limits, repeated words, characters, copying.

These run as plain code (no model), so they are free, instant and repeatable.
Model-based checks (banned claims, trademark misuse) arrive in M2 with the rules RAG.
"""

import re
from collections import Counter
from dataclasses import dataclass

# Conservative limits; M2 replaces these with values retrieved from the rule docs.
TITLE_MAX = {"amazon": 200, "ebay": 80}
BULLETS_MAX = {"amazon": 5, "ebay": 0}  # eBay has no bullet field; bullets go in the description
BANNED_TITLE_CHARS = re.compile(r"[!$?_{}^¬¦~#<>*]")
NGRAM_N = 8


@dataclass
class Issue:
    field: str
    rule: str
    detail: str


def normalize(text: str) -> list[str]:
    return re.sub(r"[^\w\s]", " ", text.lower()).split()


def ngrams(words: list[str], n: int = NGRAM_N) -> set[tuple[str, ...]]:
    return {tuple(words[i : i + n]) for i in range(len(words) - n + 1)}


def copied_phrases(generated: str, sources: list[str], n: int = NGRAM_N) -> list[str]:
    """Runs of n+ words that appear word-for-word in any competitor listing."""
    source_grams: set[tuple[str, ...]] = set()
    for s in sources:
        source_grams |= ngrams(normalize(s), n)
    return [" ".join(g) for g in ngrams(normalize(generated), n) & source_grams]


def check_listing(marketplace: str, title: str, bullets: list[str], description: str,
                  competitor_texts: list[str]) -> list[Issue]:
    issues: list[Issue] = []

    limit = TITLE_MAX[marketplace]
    if len(title) > limit:
        issues.append(Issue("title", f"{marketplace}: title max {limit} chars",
                            f"title is {len(title)} chars"))

    if BANNED_TITLE_CHARS.search(title):
        issues.append(Issue("title", "No special characters in titles",
                            f"found {sorted(set(BANNED_TITLE_CHARS.findall(title)))}"))

    counts = Counter(w for w in normalize(title) if len(w) > 2)
    repeated = [w for w, c in counts.items() if c > 2]
    if repeated:
        issues.append(Issue("title", "No word more than twice in a title",
                            f"repeated: {repeated}"))

    max_bullets = BULLETS_MAX[marketplace]
    if max_bullets and len(bullets) > max_bullets:
        issues.append(Issue("bullets", f"{marketplace}: at most {max_bullets} bullets",
                            f"{len(bullets)} bullets"))

    full_text = " ".join([title, *bullets, description])
    copies = copied_phrases(full_text, competitor_texts)
    if copies:
        issues.append(Issue("all", f"No copying ({NGRAM_N}+ identical words)",
                            f"{len(copies)} copied phrase(s), e.g. '{copies[0]}'"))
    return issues
