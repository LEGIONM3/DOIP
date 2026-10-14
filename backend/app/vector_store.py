"""Vector Index and Hybrid Retrieval Engine for DOIP Doctrine RAG.

Combines:
  1. Dense Cosine Similarity over L2-normalized embeddings
  2. Sparse Lexical Scoring (Exact term, acronym, and section header matching)
  3. Reciprocal Rank Fusion (RRF) Reranking
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import math
import re
from typing import Any

try:
    from .embeddings import EmbeddingProvider, get_embedding_provider
except ImportError:
    from app.embeddings import EmbeddingProvider, get_embedding_provider

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class DoctrineChunkRecord:
    chunk_id: str
    document_id: str
    document_type: str
    section: str
    citation: str
    source: str
    text: str
    token_count: int
    embedding: list[float]


class HybridVectorIndex:
    """In-memory dense vector store with hybrid search and Reciprocal Rank Fusion."""

    def __init__(self, provider: EmbeddingProvider | None = None) -> None:
        self.provider = provider or get_embedding_provider()
        self.chunks: dict[str, DoctrineChunkRecord] = {}

    def clear(self) -> None:
        self.chunks.clear()

    def add_chunk(self, chunk: DoctrineChunkRecord) -> None:
        self.chunks[chunk.chunk_id] = chunk

    def add_chunks(self, chunks: list[DoctrineChunkRecord]) -> None:
        for c in chunks:
            self.add_chunk(c)

    @property
    def total_chunks(self) -> int:
        return len(self.chunks)

    def search_dense(
        self,
        query: str,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[tuple[DoctrineChunkRecord, float]]:
        """Execute pure dense cosine similarity search."""
        if not self.chunks:
            return []
        q_emb = self.provider.embed_text(query)
        scored: list[tuple[DoctrineChunkRecord, float]] = []

        filters = filters or {}
        doc_type_filter = (filters.get("document_type") or filters.get("category") or "").strip().lower()
        doc_id_filter = (filters.get("document_id") or "").strip().upper()

        for chunk in self.chunks.values():
            if doc_type_filter and chunk.document_type.lower() != doc_type_filter:
                continue
            if doc_id_filter and chunk.document_id.upper() != doc_id_filter:
                continue

            # Dot product of normalized vectors = cosine similarity
            sim = sum(a * b for a, b in zip(q_emb, chunk.embedding))
            scored.append((chunk, float(sim)))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def search_lexical(
        self,
        query: str,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[tuple[DoctrineChunkRecord, float]]:
        """Execute sparse lexical term-matching search."""
        tokens = set(re.findall(r"\w+", query.lower()))
        if not tokens:
            return []

        filters = filters or {}
        doc_type_filter = (filters.get("document_type") or filters.get("category") or "").strip().lower()
        doc_id_filter = (filters.get("document_id") or "").strip().upper()

        scored: list[tuple[DoctrineChunkRecord, float]] = []
        for chunk in self.chunks.values():
            if doc_type_filter and chunk.document_type.lower() != doc_type_filter:
                continue
            if doc_id_filter and chunk.document_id.upper() != doc_id_filter:
                continue

            text_lower = chunk.text.lower()
            sec_lower = chunk.section.lower()
            doc_id_lower = chunk.document_id.lower()

            score = 0.0
            if doc_id_lower in tokens or doc_id_lower in query.lower():
                score += 10.0

            for tok in tokens:
                if tok in sec_lower:
                    score += 4.0
                cnt = text_lower.count(tok)
                if cnt > 0:
                    score += min(cnt * 0.5, 3.0)

            if score > 0.0:
                scored.append((chunk, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    # Alias for sparse retrieval
    search_sparse = search_lexical

    def search_hybrid(
        self,
        query: str,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
        dense_weight: float = 0.65,
    ) -> list[dict[str, Any]]:
        """Execute hybrid dense + lexical search using Reciprocal Rank Fusion (RRF)."""
        candidate_k = max(top_k * 3, 15)
        dense_results = self.search_dense(query, top_k=candidate_k, filters=filters)
        lexical_results = self.search_lexical(query, top_k=candidate_k, filters=filters)

        rrf_scores: dict[str, float] = {}
        chunk_map: dict[str, DoctrineChunkRecord] = {}
        cosine_scores: dict[str, float] = {}

        # 1. Score dense candidates
        for rank, (chunk, sim) in enumerate(dense_results):
            cid = chunk.chunk_id
            chunk_map[cid] = chunk
            cosine_scores[cid] = sim
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (dense_weight / (60.0 + rank))

        # 2. Score lexical candidates
        lex_weight = 1.0 - dense_weight
        for rank, (chunk, _) in enumerate(lexical_results):
            cid = chunk.chunk_id
            chunk_map[cid] = chunk
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (lex_weight / (60.0 + rank))

        # 3. Sort by combined RRF score
        sorted_cids = sorted(rrf_scores.keys(), key=lambda c: rrf_scores[c], reverse=True)

        results = []
        for cid in sorted_cids[:top_k]:
            chunk = chunk_map[cid]
            cos_sim = cosine_scores.get(cid, 0.0)
            # Normalize final display score to roughly [0, 1] range
            display_score = round(max(0.1, min(0.99, cos_sim if cos_sim > 0 else 0.50)), 2)

            results.append({
                "chunk_id": chunk.chunk_id,
                "document_id": chunk.document_id,
                "document_type": chunk.document_type,
                "section": chunk.section,
                "citation": chunk.citation,
                "score": display_score,
                "text": chunk.text,
                "source": chunk.source,
                "token_count": chunk.token_count,
            })

        return results
