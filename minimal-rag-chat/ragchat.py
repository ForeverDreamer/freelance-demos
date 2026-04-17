"""CLI entry point for minimal-rag-chat.

Subcommands:
    ingest <path>       Chunk, embed, and persist documents.
    ask <question>      Retrieve top-k chunks and answer via LLM.
"""
from __future__ import annotations

import argparse
import logging
import sys
from typing import Iterable

from config import load_config
from ingest import ingest
from providers import get_chat, get_embedder
from retrieve import Hit, Store

logger = logging.getLogger("ragchat")

SYSTEM_PROMPT = (
    "You are a helpful assistant. Answer the user's question using only the "
    "context below. If the context does not contain the answer, say so. "
    "Cite sources inline as [doc#chunk]."
)


def build_user_prompt(question: str, hits: Iterable[Hit]) -> str:
    parts = ["Context:"]
    for h in hits:
        parts.append(f"--- [{h.doc}#{h.chunk_id}] ---\n{h.text}")
    parts.append(f"\nQuestion: {question}")
    return "\n\n".join(parts)


def cmd_ingest(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    embedder = get_embedder(cfg.embeddings.provider, cfg.embeddings.model)
    n = ingest(
        source=args.source,
        store_path=cfg.storage.path,
        embedder=embedder,
        chunk_size=cfg.retrieval.chunk_size,
        chunk_overlap=cfg.retrieval.chunk_overlap,
    )
    logger.info("Ingested %d chunks to %s", n, cfg.storage.path)
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    embedder = get_embedder(cfg.embeddings.provider, cfg.embeddings.model)
    store = Store(cfg.storage.path)
    if len(store) == 0:
        logger.error("Empty store at %s. Run `ingest` first.", cfg.storage.path)
        return 1
    hits = store.search(args.question, embedder, top_k=cfg.retrieval.top_k)
    if args.retrieve_only:
        for h in hits:
            print(f"[{h.score:.4f}] {h.doc}#{h.chunk_id}")
            print(h.text)
            print()
        return 0
    chat = get_chat(
        cfg.llm.provider,
        cfg.llm.model,
        cfg.llm.temperature,
        cfg.llm.max_tokens,
    )
    answer = chat.complete(SYSTEM_PROMPT, build_user_prompt(args.question, hits))
    print(answer)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Minimal RAG chat. Ingest documents and ask questions over them "
            "with hybrid BM25 + vector retrieval."
        )
    )
    parser.add_argument("--config", default="rag.yaml", help="Path to YAML config")
    parser.add_argument("--log-level", default="INFO", help="Logging level")

    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ingest = sub.add_parser("ingest", help="Chunk, embed, and persist documents")
    p_ingest.add_argument("source", help="Path to a file or directory")
    p_ingest.set_defaults(func=cmd_ingest)

    p_ask = sub.add_parser("ask", help="Ask a question against the store")
    p_ask.add_argument("question", help="Natural-language question")
    p_ask.add_argument(
        "--retrieve-only",
        action="store_true",
        help="Skip the LLM and print the retrieved chunks",
    )
    p_ask.set_defaults(func=cmd_ask)

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
