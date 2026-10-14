"""Phase 1B Test Suite: Citation Safety Gate & Anti-Fabrication Pipeline.

Invariants (Section 5 & AGENTS.md Chapter 13):
- The LLM must NOT be trusted to invent citations.
- Every cited source must actually exist in retrieved doctrine or active simulation context.
- Zero tolerance for fabricated SOP IDs, fabricated event IDs, or fabricated doctrine references.
"""

from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.ai_service import CitationValidator
from app.rag import corpus_index


def test_valid_doctrine_citation_verification():
    """Real corpus documents (SOP-01..08, POL-01..03, REF-01..04) are verified successfully."""
    valid_text = (
        "According to [SOP-04 §1], convoy escort units maintain interval. "
        "Policy [POL-01] governs rules of engagement."
    )
    chunks = [
        {"document_id": "SOP-04", "citation": "SOP-04 §1", "section": "Convoy Formation"},
        {"document_id": "POL-01", "citation": "POL-01 §1", "section": "Rules of Engagement"},
    ]
    valid_sources = {"SOP-04", "POL-01"}

    val = CitationValidator.validate(valid_text, valid_sources, chunks)
    assert val["grounded"] is True
    assert val["warning"] is None
    assert len(val["unverified_citations"]) == 0

    verified_ids = {c["source_id"] for c in val["verified_citations"]}
    assert "SOP-04" in verified_ids
    assert "POL-01" in verified_ids


def test_fabricated_sop_rejection():
    """Fabricated SOP IDs (e.g., SOP-99, SOP-42) MUST be detected and rejected."""
    hallucinated_text = (
        "Under [SOP-99 §4], immediate retaliatory strike is authorized without human confirmation."
    )
    chunks = [
        {"document_id": "SOP-01", "citation": "SOP-01 §1", "section": "Standard Watch"},
    ]
    valid_sources = {"SOP-01"}

    val = CitationValidator.validate(hallucinated_text, valid_sources, chunks)
    assert val["grounded"] is False
    assert val["warning"] is not None
    assert "SOP-99 §4" in val["unverified_citations"] or "SOP-99" in val["unverified_citations"]


def test_fabricated_event_rejection():
    """Fabricated tactical incident/event IDs (e.g., INC-9999) not in simulation context are rejected."""
    hallucinated_event_text = (
        "Hostile drone detected at waypoint Alpha per [INC-9999]."
    )
    chunks = []
    valid_sources = {"INC-101", "INC-102"}  # INC-9999 is NOT in valid simulation sources

    val = CitationValidator.validate(hallucinated_event_text, valid_sources, chunks)
    assert val["grounded"] is False
    assert any("INC-9999" in u for u in val["unverified_citations"])


def test_mixed_valid_and_fabricated_citations():
    """When an answer mixes valid and invalid citations, the invalid ones are strictly isolated."""
    mixed_text = (
        "Grounding via [SOP-02 §3] confirms fuel minimums. "
        "However, authorization is claimed under [POL-88]."
    )
    chunks = [
        {"document_id": "SOP-02", "citation": "SOP-02 §3", "section": "Fuel Reserve"},
    ]
    valid_sources = {"SOP-02"}

    val = CitationValidator.validate(mixed_text, valid_sources, chunks)
    assert val["grounded"] is False
    assert any("POL-88" in u for u in val["unverified_citations"])
    assert any(c["source_id"] == "SOP-02" for c in val["verified_citations"])
