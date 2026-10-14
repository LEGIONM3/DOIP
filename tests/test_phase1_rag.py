"""Phase 1A Test Suite: Dense Semantic RAG & Hybrid Retrieval.

Invariants:
- Local 384-dimensional dense semantic embedding.
- Dense cosine similarity ranking.
- Sparse lexical search (acronyms, codes, titles).
- Reciprocal Rank Fusion (RRF) hybrid reranker.
- Clean retrieve() backend service interface with filters.
"""

from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.rag import corpus_index, retrieve
from app.embeddings import get_embedding_provider


def test_embedding_provider_consistency():
    """Embedding provider produces deterministic, L2-normalized 384-dimensional vectors."""
    provider = get_embedding_provider()
    v1 = provider.embed_text("tactical fuel minimum reserve")
    v2 = provider.embed_text("tactical fuel minimum reserve")
    v3 = provider.embed_text("unrelated atmospheric weather pressure")

    assert len(v1) == 384
    assert v1 == v2, "Embeddings must be 100% deterministic"

    # Cosine similarity between identical vectors is 1.0
    sim_identical = provider.cosine_similarity(v1, v2)
    assert abs(sim_identical - 1.0) < 1e-4

    # Related vs unrelated semantic separation
    v_fuel2 = provider.embed_text("logistics depot resupply diesel gasoline")
    sim_related = provider.cosine_similarity(v1, v_fuel2)
    sim_unrelated = provider.cosine_similarity(v1, v3)

    assert sim_related > sim_unrelated, f"Related ({sim_related}) should exceed unrelated ({sim_unrelated})"


def test_dense_semantic_search():
    """Dense cosine search surfaces doctrinally relevant chunks."""
    idx = corpus_index.vector_index
    results = idx.search_dense("tactical fuel minimum reserve logistics", top_k=5)

    assert len(results) > 0
    top_chunk, score = results[0]
    # Should match POL-02 (fuel/synthetic) or SOP-02 (resupply) or SOP-04 (convoy)
    assert top_chunk.document_id in ["POL-02", "SOP-02", "SOP-04", "REF-03"]
    assert score > 0.4


def test_sparse_lexical_acronym_search():
    """Sparse matching handles exact military acronyms (CASEVAC, ROE, QRF, EW)."""
    idx = corpus_index.vector_index
    res_casevac = idx.search_sparse("CASEVAC", top_k=3)
    assert any(c.document_id == "SOP-03" for c, _ in res_casevac)

    res_roe = idx.search_sparse("ROE", top_k=3)
    assert any(c.document_id == "POL-01" for c, _ in res_roe)


def test_hybrid_rrf_retrieval():
    """Hybrid search merges dense and sparse rankings via Reciprocal Rank Fusion."""
    idx = corpus_index.vector_index
    hybrid_results = idx.search_hybrid("comms loss radio silence protocol", top_k=5)

    assert len(hybrid_results) > 0
    doc_ids = [r["document_id"] for r in hybrid_results]
    assert "SOP-06" in doc_ids or "REF-01" in doc_ids


def test_retrieve_api_interface():
    """Test clean retrieve() backend function with structured return and filtering."""
    # Top 3 without filter
    res = retrieve("casualty evacuation medical triage", top_k=3)
    assert len(res) <= 3
    assert all("chunk_id" in r and "citation" in r and "score" in r for r in res)
    assert any("SOP-03" in r["citation"] for r in res)

    # With category filter
    res_filtered = retrieve("casualty evacuation medical triage", top_k=5, filters={"category": "sop"})
    assert all(r["document_type"] == "sop" for r in res_filtered)
