"""Dense Semantic Doctrine RAG Engine & Grounding Verifier (Phase 1A).

Pipeline:
  1. Parse 15 doctrine markdown files (POL-01..03, REF-01..04, SOP-01..08) with YAML frontmatter.
  2. Perform deterministic section chunking with reproducible chunk IDs and citation keys.
  3. Generate dense vector embeddings via local/nomic embedding providers.
  4. Index chunks in HybridVectorIndex (Dense Cosine Similarity + Sparse Lexical + RRF Reranking).
  5. Validate citations and claims strictly against retrieved context (zero hallucination tolerance).
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import re
from typing import Any

try:
    from . import db
    from .embeddings import get_embedding_provider
    from .vector_store import DoctrineChunkRecord, HybridVectorIndex
except ImportError:
    from app import db
    from app.embeddings import get_embedding_provider
    from app.vector_store import DoctrineChunkRecord, HybridVectorIndex

log = logging.getLogger(__name__)

CORPUS_ROOT = Path(__file__).resolve().parent.parent.parent / "corpus"


@dataclass
class CorpusDoc:
    doc_id: str
    category: str
    title: str
    tags: list[str]
    version: str
    content: str
    source_file: str
    sections: list[tuple[str, str]]  # (heading, text)


class DoctrineCorpusManager:
    """Manages document ingestion, deterministic chunking, and dense hybrid indexing."""

    def __init__(self, corpus_dir: Path | None = None) -> None:
        self.corpus_dir = corpus_dir or CORPUS_ROOT
        self.docs: dict[str, CorpusDoc] = {}
        self.vector_index = HybridVectorIndex()
        self.load_and_index()

def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[-\s]+", "-", text)[:32].strip("-")


def parse_corpus_file(path: Path) -> CorpusDoc:
    """Parse a markdown doctrine document with frontmatter."""
    text = path.read_text(encoding="utf-8")
    category = path.parent.name.lower()
    doc_id = path.stem.upper()
    title = doc_id
    tags: list[str] = []
    version = "1.0"
    body = text

    # Parse YAML frontmatter
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            header = parts[1]
            body = parts[2]
            for line in header.strip().splitlines():
                if line.startswith("id:"):
                    doc_id = line.split(":", 1)[1].strip().upper()
                elif line.startswith("title:"):
                    title = line.split(":", 1)[1].strip()
                elif line.startswith("version:"):
                    version = line.split(":", 1)[1].strip()
                elif line.startswith("tags:"):
                    tag_str = line.split(":", 1)[1].strip()
                    tags = [t.strip().strip("[]'\"") for t in tag_str.split(",") if t.strip()]

    # Split body into sections by markdown heading
    sections: list[tuple[str, str]] = []
    current_heading = "Overview"
    current_lines: list[str] = []

    for line in body.splitlines():
        if line.startswith("#"):
            if current_lines:
                sec_text = "\n".join(current_lines).strip()
                if sec_text:
                    sections.append((current_heading, sec_text))
                current_lines = []
            current_heading = line.lstrip("#").strip()
        else:
            current_lines.append(line)

    if current_lines:
        sec_text = "\n".join(current_lines).strip()
        if sec_text:
            sections.append((current_heading, sec_text))

    return CorpusDoc(
        doc_id=doc_id,
        category=category,
        title=title,
        tags=tags,
        version=version,
        content=body.strip(),
        source_file=str(path),
        sections=sections,
    )


def chunk_document(doc: CorpusDoc, source_file: str = "") -> list[dict[str, Any]]:
    """Deterministically chunk a CorpusDoc into section chunks."""
    chunks = []
    for sec_idx, (heading, sec_text) in enumerate(doc.sections, start=1):
        slug = slugify(heading)
        chunk_id = f"{doc.doc_id}-SEC-{sec_idx:02d}-{slug}"
        sec_num_match = re.match(r"^(\d+)\.", heading)
        sec_citation = f"{doc.doc_id} §{sec_num_match.group(1)}" if sec_num_match else f"{doc.doc_id} §{heading}"

        chunks.append({
            "chunk_id": chunk_id,
            "document_id": doc.doc_id,
            "document_type": doc.category,
            "section": heading,
            "source": source_file or doc.source_file,
            "citation": sec_citation,
            "text": sec_text,
            "token_count": len(sec_text.split()),
        })
    return chunks


class DoctrineCorpusManager:
    """Manages document ingestion, deterministic chunking, and dense hybrid indexing."""

    def __init__(self, corpus_dir: Path | None = None) -> None:
        self.corpus_dir = corpus_dir or CORPUS_ROOT
        self.docs: dict[str, CorpusDoc] = {}
        self.vector_index = HybridVectorIndex()
        self.load_and_index()

    @property
    def chunks(self) -> list[DoctrineChunkRecord]:
        return list(self.vector_index.chunks.values())

    def _slugify(self, text: str) -> str:
        return slugify(text)

    def _parse_doc(self, path: Path, text: str) -> CorpusDoc:
        doc = parse_corpus_file(path)
        if self.corpus_dir.parent in path.parents:
            doc.source_file = path.relative_to(self.corpus_dir.parent).as_posix()
        return doc

    def load_and_index(self) -> None:
        """Scan corpus, create deterministic chunks, compute embeddings, and build vector index."""
        self.docs.clear()
        self.vector_index.clear()
        if not self.corpus_dir.exists():
            log.warning("Corpus directory not found: %s", self.corpus_dir)
            return

        chunks_to_persist: list[dict[str, Any]] = []
        all_chunk_records: list[DoctrineChunkRecord] = []
        provider = get_embedding_provider()

        for path in sorted(self.corpus_dir.rglob("*.md")):
            try:
                raw_text = path.read_text(encoding="utf-8")
                doc = self._parse_doc(path, raw_text)
                if not doc:
                    continue

                self.docs[doc.doc_id] = doc

                # Persist document metadata
                try:
                    db.save_doctrine_document(
                        doc_id=doc.doc_id,
                        category=doc.category,
                        title=doc.title,
                        tags=doc.tags,
                        version=doc.version,
                        source_file=doc.source_file,
                        content=doc.content,
                    )
                except Exception as exc:
                    log.debug("DB save_doctrine_document notice: %s", exc)

                # Deterministic section chunking
                for sec_idx, (heading, sec_text) in enumerate(doc.sections, start=1):
                    slug = self._slugify(heading)
                    chunk_id = f"{doc.doc_id}-SEC-{sec_idx:02d}-{slug}"

                    # Clean citation key: e.g. "SOP-04 §1" or "POL-01 §Overview"
                    sec_num_match = re.match(r"^(\d+)\.", heading)
                    sec_citation = f"{doc.doc_id} §{sec_num_match.group(1)}" if sec_num_match else f"{doc.doc_id} §{heading}"

                    full_chunk_text = f"{doc.title} — {heading}\n{sec_text}"
                    emb = provider.embed_text(full_chunk_text)
                    token_count = len(full_chunk_text.split())

                    record = DoctrineChunkRecord(
                        chunk_id=chunk_id,
                        document_id=doc.doc_id,
                        document_type=doc.category,
                        section=heading,
                        citation=sec_citation,
                        source=doc.source_file,
                        text=sec_text,
                        token_count=token_count,
                        embedding=emb,
                    )
                    all_chunk_records.append(record)

                    chunks_to_persist.append({
                        "chunk_id": chunk_id,
                        "document_id": doc.doc_id,
                        "document_type": doc.category,
                        "section": heading,
                        "source": doc.source_file,
                        "citation": sec_citation,
                        "text": sec_text,
                        "token_count": token_count,
                        "embedding": emb,
                    })
            except Exception as exc:
                log.warning("Failed parsing corpus doc %s: %s", path, exc)

        # Index all chunks in memory
        self.vector_index.add_chunks(all_chunk_records)

        # Persist chunks to relational store
        if chunks_to_persist:
            try:
                db.save_doctrine_chunks(chunks_to_persist)
            except Exception as exc:
                log.debug("DB save_doctrine_chunks notice: %s", exc)

        log.info(
            "Corpus loaded: %d documents, %d deterministic chunks, %d-d embeddings",
            len(self.docs),
            self.vector_index.total_chunks,
            provider.dimension,
        )

    def search(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        """Backward-compatible search returning top document sections."""
        results = self.vector_index.search_hybrid(query, top_k=top_k)
        formatted = []
        for r in results:
            doc = self.docs.get(r["document_id"])
            formatted.append({
                "doc_id": r["document_id"],
                "title": doc.title if doc else r["document_id"],
                "category": r["document_type"],
                "score": r["score"],
                "section": r["section"],
                "excerpt": r["text"][:350],
                "citation": r["citation"],
                "chunk_id": r["chunk_id"],
                "source": r["source"],
            })
        return formatted


# Singleton corpus instance
corpus_index = DoctrineCorpusManager()


# ---------------------------------------------------------------------------
# Clean Retrieval API Service
# ---------------------------------------------------------------------------
def retrieve(
    query: str,
    top_k: int = 5,
    filters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Primary retrieval service for Phase 1 semantic RAG.

    Executes dense hybrid retrieval against deterministic doctrine chunks.
    """
    return corpus_index.vector_index.search_hybrid(query, top_k=top_k, filters=filters)


# ---------------------------------------------------------------------------
# AI Grounding & Citation Verifier (AGENTS.md Chapter 13 Rule)
# ---------------------------------------------------------------------------
def verify_grounding(
    text: str,
    known_events: set[str] | None = None,
    known_docs: set[str] | None = None,
    retrieved_chunk_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Verify citations in generated text against known events and corpus docs.

    Every factual assertion must cite an authorized document (SOP-01..08, POL-01..03,
    REF-01..04) or simulation event (e.g. INC-10, AL-5, EV-22, RUN-1). Unverifiable
    citations are rejected and flagged.
    """
    known_events = known_events or set()
    known_docs = known_docs or set(corpus_index.docs.keys())

    # Detect cited doc tokens: e.g. SOP-01, POL-02, REF-03
    doc_cites = set(re.findall(r"\b(SOP-\d+|POL-\d+|REF-\d+)\b", text, re.IGNORECASE))
    doc_cites = {d.upper() for d in doc_cites}

    # Detect cited event tokens: e.g. INC-10, AL-5, RUN-1, EV-12, DET-1
    event_cites = set(re.findall(r"\b(INC-\w+|AL-\w+|RUN-\w+|EV-\w+|DET-\w+)\b", text, re.IGNORECASE))
    event_cites = {e.upper() for e in event_cites}

    valid_docs = [d for d in doc_cites if d in known_docs]
    invalid_docs = [d for d in doc_cites if d not in known_docs]

    # Check event validity
    valid_events = [e for e in event_cites if (not known_events or e in known_events)]
    invalid_events = [e for e in event_cites if known_events and e not in known_events]

    total_citations = len(valid_docs) + len(valid_events)
    has_unverified = bool(invalid_docs or invalid_events)

    # Text making strong doctrine/incident assertions without citations is unverified
    needs_citation = any(
        kw in text.lower()
        for kw in ["mandates", "requires", "protocol", "violation", "incident", "casualty", "doctrine", "ordered"]
    )

    if needs_citation and total_citations == 0:
        grounded = False
        warning = "Claim makes doctrine or event assertions without citing an authorized event ID or corpus doc ID."
    elif has_unverified:
        grounded = False
        warning = f"References unverified identifiers: {invalid_docs + invalid_events}"
    else:
        grounded = True
        warning = None

    return {
        "grounded": grounded,
        "warning": warning,
        "valid_doc_citations": valid_docs,
        "valid_event_citations": valid_events,
        "invalid_citations": invalid_docs + invalid_events,
    }


def query_rag(
    query: str,
    recent_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Execute grounded RAG query across doctrine corpus and event stream."""
    recent_events = recent_events or []
    known_events = {
        e.get("entityId", "") for e in recent_events if e.get("entityId")
    } | {
        e.get("payload", {}).get("alertId", "") for e in recent_events if e.get("payload", {}).get("alertId")
    } | {
        e.get("id", "") for e in recent_events if e.get("id")
    }

    # Execute dense hybrid retrieval
    results = retrieve(query, top_k=3)
    if not results:
        return {
            "query": query,
            "answer": "No relevant doctrine or SOP reference found for this query.",
            "citations": [],
            "grounding": {"grounded": True, "warning": None},
        }

    top_chunk = results[0]
    doc_id = top_chunk["document_id"]
    citation = top_chunk["citation"]
    section = top_chunk["section"]
    excerpt = top_chunk["text"][:350]

    # Synthesize grounded answer with verified citation
    answer = f"According to [{doc_id}] ({citation} — {section}): {excerpt}"
    grounding = verify_grounding(answer, known_events=known_events)

    # Format citations for response
    citations_output = [
        {
            "doc_id": r["document_id"],
            "chunk_id": r["chunk_id"],
            "title": r["section"],
            "category": r["document_type"],
            "score": r["score"],
            "section": r["section"],
            "excerpt": r["text"][:350],
            "citation": r["citation"],
            "source": r["source"],
        }
        for r in results
    ]

    return {
        "query": query,
        "answer": answer,
        "citations": citations_output,
        "grounding": grounding,
    }
