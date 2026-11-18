"""Rules RAG: parsing the rules files and per-marketplace retrieval (no model download)."""

import hashlib

from chromadb import Documents, EmbeddingFunction, Embeddings

from enrich import rules

WORDS = 256


class HashedWords(EmbeddingFunction):
    """Tiny deterministic bag-of-words embedding so tests don't download a model."""

    def __init__(self):
        pass

    def __call__(self, input: Documents) -> Embeddings:
        out = []
        for doc in input:
            v = [0.0] * WORDS
            for w in doc.lower().split():
                v[int(hashlib.md5(w.strip(".,:\"'()").encode()).hexdigest(), 16) % WORDS] += 1
            out.append(v)
        return out

    @staticmethod
    def name() -> str:
        return "hashed-words"


def test_every_rules_file_parses_with_sources():
    loaded = rules.load_rules()
    assert {r.marketplace for r in loaded} == {"amazon", "ebay"}
    assert len(loaded) >= 20
    assert all(r.source.startswith("https://") and r.text and r.heading for r in loaded)
    assert len({r.id for r in loaded}) == len(loaded)


def test_retrieve_stays_within_marketplace():
    index = rules.RulesIndex(rules.load_rules(), embedding_function=HashedWords())
    found = index.retrieve("amazon", "title characters limit", k=3)
    assert len(found) == 3 and all(r.marketplace == "amazon" for r in found)
    assert any("Title" in r.heading for r in found)


def test_parse_rules_file(tmp_path):
    f = tmp_path / "walmart.md"
    f.write_text("---\nmarketplace: walmart\n---\n\n## First rule\nSource: https://w.example/1\n"
                 "Line one.\nLine two.\n\n## Second rule\nSource: https://w.example/2\nText.\n")
    first, second = rules.parse_rules_file(f)
    assert first == rules.Rule(id="walmart-01", marketplace="walmart", heading="First rule",
                               source="https://w.example/1", text="Line one. Line two.")
    assert second.id == "walmart-02" and second.text == "Text."
