"""
RetrieverAgent: embeds knowledge base documents and serves top-k context.

The retriever uses LangChain's Chroma wrapper with OpenAI embeddings
(`text-embedding-3-small`). The vector store is persisted to
``agent_b/vectorstore/`` so indexing only happens the first time.

If OpenAI or Chroma are unavailable (e.g. offline mode or missing API key)
the retriever transparently falls back to a term-frequency score over the
raw knowledge base lines so the UI can still function for demos.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from config.agent_config import MAS_CONFIG
from utils.file_loader import load_all_knowledge
from utils.logger import log_error, log_mas_trace
from utils.text_processing import clean_text, tf_score, tokenize

load_dotenv()


class RetrieverAgent:
    """Vector-store backed retriever with a graceful offline fallback."""

    def __init__(self) -> None:
        self._project_root: Path = Path(__file__).resolve().parents[2]
        self._persist_dir: Path = self._project_root / "agent_b" / "vectorstore"
        self._persist_dir.mkdir(parents=True, exist_ok=True)

        self._documents: list[str] = []
        self._metadatas: list[dict] = []
        self._vectorstore = None
        self._use_vectorstore: bool = False
        self._corpus_tokens: list[list[str]] = []

        self._prepare_documents()
        self._try_build_vectorstore()

    def _prepare_documents(self) -> None:
        """Build the document list and fallback tokenized corpus."""
        bundle = load_all_knowledge()
        for source, raw in bundle.items():
            cleaned = clean_text(raw)
            if not cleaned:
                continue
            # Split each KB file into small chunks by blank-line/paragraph.
            chunks = [c.strip() for c in cleaned.split("\n") if c.strip()]
            # Group adjacent chunks into windows of ~3 lines for better recall.
            window = 3
            for i in range(0, len(chunks), window):
                piece = "\n".join(chunks[i : i + window])
                if piece:
                    self._documents.append(piece)
                    self._metadatas.append({"source": source})
        self._corpus_tokens = [tokenize(doc) for doc in self._documents]

    def _try_build_vectorstore(self) -> None:
        """Attempt to build/load the Chroma vector store; fall back silently."""
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key or api_key == "your_api_key_here":
            log_mas_trace("retriever_init", "No OPENAI_API_KEY. Using TF fallback.")
            return
        try:
            from langchain_openai import OpenAIEmbeddings
            from langchain_community.vectorstores import Chroma

            embeddings = OpenAIEmbeddings(
                model=MAS_CONFIG["embedding_model"],
                api_key=api_key,
            )
            persist_str = str(self._persist_dir)
            index_file = self._persist_dir / "chroma.sqlite3"
            if index_file.exists():
                self._vectorstore = Chroma(
                    persist_directory=persist_str,
                    embedding_function=embeddings,
                    collection_name="dinebot_kb",
                )
            else:
                self._vectorstore = Chroma.from_texts(
                    texts=self._documents,
                    embedding=embeddings,
                    metadatas=self._metadatas,
                    persist_directory=persist_str,
                    collection_name="dinebot_kb",
                )
                # persist() is a no-op on newer Chroma versions but kept for safety.
                try:
                    self._vectorstore.persist()
                except Exception:  # noqa: BLE001
                    pass
            self._use_vectorstore = True
            log_mas_trace(
                "retriever_init",
                f"Chroma ready ({len(self._documents)} chunks).",
            )
        except Exception as exc:  # noqa: BLE001
            log_error("RetrieverAgent", f"Vectorstore init failed: {exc}")
            self._vectorstore = None
            self._use_vectorstore = False

    def retrieve(self, query: str, k: int = 3) -> list[str]:
        """Return up to ``k`` relevant knowledge base chunks."""
        log_mas_trace("retriever_query", f'Query received - "{query}"')
        if not query or not self._documents:
            log_mas_trace("retriever_empty", "No documents or empty query.")
            return []
        if self._use_vectorstore and self._vectorstore is not None:
            try:
                log_mas_trace(
                    "retriever_embedding",
                    "Embedding query with text-embedding-3-small...",
                )
                results = self._vectorstore.similarity_search(query, k=k)
                chunks = [doc.page_content for doc in results if doc.page_content]
                log_mas_trace(
                    "retriever_result",
                    f"Retrieved {len(chunks)} chunks (vector store).",
                )
                for i, c in enumerate(chunks, 1):
                    preview = c.replace("\n", " ")
                    log_mas_trace("retriever_chunk", f"Chunk {i}: {preview[:140]}")
                return chunks
            except Exception as exc:  # noqa: BLE001
                log_error("RetrieverAgent", f"Vector search failed: {exc}")
        return self._tf_fallback(query, k)

    def _tf_fallback(self, query: str, k: int) -> list[str]:
        log_mas_trace(
            "retriever_embedding",
            "Scoring with term-frequency fallback (offline).",
        )
        q_tokens = tokenize(query)
        scored: list[tuple[float, int]] = []
        for idx, toks in enumerate(self._corpus_tokens):
            score = tf_score(q_tokens, toks)
            if score > 0:
                scored.append((score, idx))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        chunks = [self._documents[i] for _, i in scored[: max(1, k)]]
        log_mas_trace(
            "retriever_result",
            f"Retrieved {len(chunks)} chunks (TF fallback).",
        )
        for i, c in enumerate(chunks, 1):
            preview = c.replace("\n", " ")
            log_mas_trace("retriever_chunk", f"Chunk {i}: {preview[:140]}")
        return chunks
