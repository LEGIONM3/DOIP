"""Phase 1A Test Suite: Deterministic Corpus Parsing and Section Chunking.

Invariants:
- All 15 doctrine files parsed with YAML frontmatter.
- Deterministic chunking: chunk IDs MUST be stable and reproducible ({DOC_ID}-SEC-{NUM}-{SLUG}).
- Zero UUIDs / unseeded randomness in chunking.
- Every chunk has structured metadata: document_id, document_type, section, source, citation, text.
"""

from pathlib import Path
import re
import sys

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.rag import CORPUS_ROOT, parse_corpus_file, chunk_document, corpus_index


def test_corpus_file_count():
    """Verify exactly 15 markdown files exist across pol, ref, and sop directories."""
    files = list(CORPUS_ROOT.glob("*/*.md"))
    assert len(files) == 15, f"Expected 15 doctrine files, found {len(files)}"

    categories = {f.parent.name.lower() for f in files}
    assert categories == {"pol", "ref", "sop"}


def test_frontmatter_extraction():
    """Verify frontmatter parsing on sample docs from each category."""
    pol_file = CORPUS_ROOT / "pol" / "POL-01.md"
    assert pol_file.exists()
    doc = parse_corpus_file(pol_file)
    assert doc.doc_id == "POL-01"
    assert doc.category == "pol"
    assert "Rules of Engagement" in doc.title
    assert "roe" in doc.tags
    assert doc.version in ["1.0", "v1.0"] or len(doc.version) > 0

    sop_file = CORPUS_ROOT / "sop" / "SOP-04.md"
    assert sop_file.exists()
    doc_sop = parse_corpus_file(sop_file)
    assert doc_sop.doc_id == "SOP-04"
    assert doc_sop.category == "sop"
    assert "Convoy Escort" in doc_sop.title


def test_deterministic_chunking_reproducibility():
    """Chunking the same document twice must produce identical chunk IDs, citations, and content."""
    sop_file = CORPUS_ROOT / "sop" / "SOP-02.md"
    doc1 = parse_corpus_file(sop_file)
    doc2 = parse_corpus_file(sop_file)

    chunks1 = chunk_document(doc1, str(sop_file))
    chunks2 = chunk_document(doc2, str(sop_file))

    assert len(chunks1) == len(chunks2)
    assert len(chunks1) > 0

    for c1, c2 in zip(chunks1, chunks2):
        assert c1["chunk_id"] == c2["chunk_id"]
        assert c1["citation"] == c2["citation"]
        assert c1["text"] == c2["text"]
        assert c1["section"] == c2["section"]


def test_chunk_id_format():
    """All chunk IDs must follow the strict deterministic format."""
    chunk_pattern = re.compile(r"^[A-Z]{3}-\d{2}-SEC-\d+-[a-z0-9-]+$")

    for chunk in corpus_index.chunks:
        cid = chunk.chunk_id
        assert chunk_pattern.match(cid), f"Malformed chunk ID: {cid}"
        assert chunk.document_id in cid
        assert " " not in cid
        assert chunk.text.strip(), f"Empty text in chunk {cid}"
        assert re.match(r"^[A-Z]{3}-\d{2}\s§.+", chunk.citation), f"Malformed citation {chunk.citation}"


def test_total_deterministic_chunks():
    """Corpus must generate exactly 70 deterministic chunks."""
    assert len(corpus_index.chunks) == 70
    assert len(corpus_index.docs) == 15
