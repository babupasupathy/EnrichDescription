"""Marketplace rules RAG (PRD: M2).

rules/<marketplace>.md holds our own-words summaries of each marketplace's listing policies,
one "## " section per chunk, each with a "Source:" link. They are embedded into an in-memory
Chroma collection once per process (about 30 short chunks, so rebuilding at startup is
cheap) and retrieved per marketplace for the classify and generate steps.

Embeddings: Chroma's built-in all-MiniLM-L6-v2 (ONNX, runs locally, no API key). The model
downloads once (~80 MB) on first use.
"""

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import chromadb
from chromadb.config import Settings
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

RULES_DIR = Path(__file__).resolve().parent.parent / "rules"
COLLECTION = "marketplace-rules"


@dataclass(frozen=True)
class Rule:
    id: str
    marketplace: str
    heading: str
    source: str
    text: str

    def as_prompt(self) -> str:
        return f"[{self.heading}] {self.text}"


def parse_rules_file(path: Path) -> list[Rule]:
    raw = path.read_text()
    front = re.match(r"---\n(.*?)\n---\n", raw, re.S)
    meta = dict(re.findall(r"^(\w+):\s*(.+)$", front.group(1), re.M)) if front else {}
    marketplace = meta.get("marketplace", path.stem).strip()
    body = raw[front.end():] if front else raw
    rules = []
    for n, section in enumerate(re.split(r"^## ", body, flags=re.M)[1:], 1):
        heading, _, rest = section.partition("\n")
        source = re.search(r"^Source:\s*(\S+)", rest, re.M)
        text = " ".join(line.strip() for line in rest.splitlines()
                        if line.strip() and not line.startswith("Source:"))
        rules.append(Rule(id=f"{marketplace}-{n:02d}", marketplace=marketplace,
                          heading=heading.strip(), source=source.group(1) if source else "",
                          text=text))
    return rules


def load_rules(rules_dir: Path = RULES_DIR) -> list[Rule]:
    return [r for p in sorted(rules_dir.glob("*.md")) for r in parse_rules_file(p)]


class RulesIndex:
    def __init__(self, rules: list[Rule], embedding_function=None):
        self.rules = {r.id: r for r in rules}
        client = chromadb.EphemeralClient(Settings(anonymized_telemetry=False))
        # Ephemeral clients share state within a process: start from a clean collection.
        if COLLECTION in [c.name for c in client.list_collections()]:
            client.delete_collection(COLLECTION)
        self.collection = client.create_collection(
            COLLECTION, embedding_function=embedding_function or DefaultEmbeddingFunction(),
            metadata={"hnsw:space": "cosine"})
        self.collection.add(
            ids=list(self.rules),
            documents=[f"{r.heading}. {r.text}" for r in rules],
            metadatas=[{"marketplace": r.marketplace, "source": r.source} for r in rules])

    def retrieve(self, marketplace: str, query: str, k: int = 4) -> list[Rule]:
        res = self.collection.query(query_texts=[query], n_results=k,
                                    where={"marketplace": marketplace})
        return [self.rules[i] for i in res["ids"][0]]


@lru_cache(maxsize=1)
def get_index() -> RulesIndex:
    return RulesIndex(load_rules())


def retrieve(marketplace: str, query: str, k: int = 4) -> list[Rule]:
    return get_index().retrieve(marketplace, query, k)
