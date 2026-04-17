from __future__ import annotations

from pathlib import Path

from ingest import ingest
from providers import FakeEmbedder
from retrieve import Store, tokenize


def test_tokenize_lowercase_and_word_only() -> None:
    assert tokenize("Hello, World! 123 abc_def") == [
        "hello",
        "world",
        "123",
        "abc_def",
    ]


def _fixture_store(tmp_path: Path) -> Path:
    (tmp_path / "hr.md").write_text(
        (
            "PTO policy: 20 days per year.\n\n"
            "Expense reimbursement: receipts required above 25 dollars.\n\n"
            "Remote work eligibility is role dependent."
        ),
        encoding="utf-8",
    )
    (tmp_path / "billing.md").write_text(
        (
            "Widgetly Cloud Team plan costs 79 USD per month.\n\n"
            "Annual billing is discounted 15 percent.\n\n"
            "Rate limit on Team is 600 requests per minute per project."
        ),
        encoding="utf-8",
    )
    store_path = tmp_path / "s.jsonl"
    ingest(
        source=tmp_path,
        store_path=store_path,
        embedder=FakeEmbedder(),
        chunk_size=80,
        chunk_overlap=0,
    )
    return store_path


def test_bm25_keyword_match_surfaces_correct_chunk(tmp_path: Path) -> None:
    # Hybrid RRF with a hash-based (non-semantic) embedder means vector ranks
    # are effectively random noise; the BM25 leg must still surface the
    # keyword-matching chunk into the top-k.
    store = Store(_fixture_store(tmp_path))
    hits = store.search("Team plan 79 monthly cost", FakeEmbedder(), top_k=3)
    assert any(
        "Team" in h.text and "79" in h.text and h.doc.endswith("billing.md")
        for h in hits
    ), [h.text for h in hits]


def test_search_empty_store(tmp_path: Path) -> None:
    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    store = Store(empty)
    assert len(store) == 0
    assert store.search("anything", FakeEmbedder(), top_k=3) == []


def test_search_respects_top_k(tmp_path: Path) -> None:
    store = Store(_fixture_store(tmp_path))
    assert len(store.search("policy", FakeEmbedder(), top_k=1)) == 1
    assert len(store.search("policy", FakeEmbedder(), top_k=10)) <= len(store)
