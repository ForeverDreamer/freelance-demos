from __future__ import annotations

from pathlib import Path

from ragchat import build_user_prompt, main


def test_cli_ingest_then_ask_retrieve_only(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    # Wire a fake-provider config pointing at sample data and a temp store.
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "note.md").write_text(
        "Alpha facts go here.\n\nBeta facts go there.", encoding="utf-8"
    )
    config = tmp_path / "rag.yaml"
    store = tmp_path / "store.jsonl"
    config.write_text(
        f"""
embeddings:
  provider: fake
  model: none
llm:
  provider: fake
  model: none
retrieval:
  top_k: 2
  chunk_size: 200
  chunk_overlap: 0
storage:
  path: {store}
""",
        encoding="utf-8",
    )

    rc = main(["--config", str(config), "ingest", str(data_dir)])
    assert rc == 0
    assert store.exists() and store.stat().st_size > 0

    rc = main(
        ["--config", str(config), "ask", "alpha?", "--retrieve-only"]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "Alpha" in out or "alpha" in out.lower()


def test_cli_ask_uses_fake_llm(tmp_path: Path, capsys) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "note.md").write_text("PTO is 20 days.", encoding="utf-8")
    config = tmp_path / "rag.yaml"
    store = tmp_path / "store.jsonl"
    config.write_text(
        f"""
embeddings:
  provider: fake
  model: none
llm:
  provider: fake
  model: none
retrieval:
  top_k: 2
  chunk_size: 200
  chunk_overlap: 0
storage:
  path: {store}
""",
        encoding="utf-8",
    )
    main(["--config", str(config), "ingest", str(data_dir)])
    capsys.readouterr()  # drop ingest output
    rc = main(["--config", str(config), "ask", "How many PTO days?"])
    assert rc == 0
    out = capsys.readouterr().out
    assert out.startswith("[fake-llm]")


def test_build_user_prompt_formats_citations() -> None:
    class H:
        def __init__(self, doc, chunk_id, text):
            self.doc = doc
            self.chunk_id = chunk_id
            self.text = text
            self.score = 0.0

    prompt = build_user_prompt(
        "Q?", [H("a.md", 0, "chunk-a"), H("b.md", 2, "chunk-b")]
    )
    assert "[a.md#0]" in prompt
    assert "[b.md#2]" in prompt
    assert prompt.rstrip().endswith("Question: Q?")
