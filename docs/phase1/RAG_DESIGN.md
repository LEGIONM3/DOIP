# DOIP Phase 1 — Dense Semantic RAG Design

**Author:** RAG-ENGINEER Agent (ECC Orchestration Team)  
**Target:** Dense Vector Retrieval + Deterministic Chunking + Hybrid Ranking  
**Corpus:** 15 Canonical Training Documents (`corpus/pol/`, `corpus/ref/`, `corpus/sop/`)  
**Status:** Approved for Implementation  

---

## 1. Objectives & Architectural Pipeline

The Phase 1A RAG upgrade replaces simplistic token-overlap keyword scoring with an enterprise-grade hybrid semantic search pipeline:

```text
Doctrine Markdown Files (15 Docs)
           ↓
Frontmatter & Markdown Parser
           ↓
Deterministic Section Chunking
           ↓
Metadata & Citation Extraction
           ↓
Dense Vector Embeddings (Local / Nomic / FastDense)
           ↓
Dual Vector Store (PostgreSQL+pgvector / Local Normalized Index)
           ↓
Hybrid Search Engine (Dense Cosine Similarity + BM25/Keyword)
           ↓
Reciprocal Rank Fusion (RRF) Reranker
           ↓
Structured Cited Context (chunk_id, doc_id, section, citation, score)
           ↓
LLM Context Assembler & Citation Validator
```

---

## 2. Ingestion & Deterministic Chunking

### 2.1 Parsing Specification
Each document under `corpus/` contains YAML frontmatter:
```yaml
---
id: SOP-04
title: Convoy Escort Procedures
tags: [convoy, escort, logistics, route]
version: 1.0
---
```
The parser extracts:
- `document_id`: Uppercase normalized string (e.g., `SOP-04`, `POL-01`, `REF-02`).
- `document_type`: Inferred from path parent (`POL`, `REF`, `SOP`).
- `title`: Human-readable title.
- `tags`: List of taxonomy identifiers.
- `version`: Semver or release string.
- `source`: Relative POSIX path (`corpus/sop/SOP-04.md`).

### 2.2 Deterministic Chunk ID Scheme
Chunks are partitioned along markdown section headers (`## 1. Composition`, `## 2. Route planning`, etc.).
The chunk ID is calculated deterministically:
```
{DOC_ID}-SEC-{SECTION_NUM:02d}-{SLUG}
```
Examples:
- `SOP-04-SEC-01-composition`
- `SOP-04-SEC-02-route-planning`
- `POL-01-SEC-03-rules-of-engagement`

**Invariant**: Zero random UUIDs are used. Re-indexing the identical corpus produces 100% byte-identical chunk IDs and metadata.

### 2.3 Chunk Data Contract
Each chunk model exposes:
```python
@dataclass(frozen=True)
class DoctrineChunk:
    chunk_id: str          # Deterministic ID
    document_id: str       # e.g., "SOP-04"
    document_type: str     # "SOP" | "POL" | "REF"
    section: str           # "2. Route planning"
    citation: str          # "SOP-04 §2"
    source: str            # "corpus/sop/SOP-04.md"
    text: str              # Section text body
    token_count: int       # Estimated word/token length
```

---

## 3. Embedding Architecture

The system uses an abstract `EmbeddingProvider` interface:
```python
class EmbeddingProvider(ABC):
    @abstractmethod
    def embed_text(self, text: str) -> list[float]: ...

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...

    @property
    @abstractmethod
    def dimension(self) -> int: ...
```

### Supported Backends:
1. **Local Nomic / Sentence-Transformer**: If `sentence_transformers` or local ONNX runtime is installed and weights exist.
2. **Ollama Embedding Bridge**: Calls `POST http://localhost:11434/api/embeddings` with model `nomic-embed-text` if Ollama is running.
3. **Deterministic Fast Dense Vectorizer (Zero-Dependency Fallback)**:
   - 384-dimensional dense semantic embedding engine using subword trigram hashing with PCA-derived orthogonal projections and cosine normalization.
   - Guaranteed deterministic vectors across all platforms, CPU architectures, and environments with 0 network calls and 0 GPU requirements.
   - Allows all unit tests and offline Docker environments to run reliably.

---

## 4. Vector Backend & Hybrid Retrieval

### 4.1 Vector Storage
- **Primary (PostgreSQL + pgvector)**: Stores chunk metadata and vector column `embedding vector(384)`. Uses HNSW or IVFFlat index with cosine distance (`vector_cosine_ops`).
- **Local Fallback (In-Memory Vector Index)**: Optimized numpy / cosine vector store with pre-computed matrix multiplication.

### 4.2 Hybrid Search & Reranking
Retrieval combines:
1. **Dense Semantic Retrieval**: Computes cosine similarity between query embedding and chunk vectors:
   $$S_{\text{dense}}(q, c) = \frac{\mathbf{e}_q \cdot \mathbf{e}_c}{\|\mathbf{e}_q\| \|\mathbf{e}_c\|}$$
2. **Sparse Lexical / Keyword Scoring**: Matches exact terms, acronyms (`SOP`, `ROE`, `SALUTE`, `CASEVAC`), and document IDs.
3. **Reciprocal Rank Fusion (RRF)**:
   $$\text{Score}_{\text{RRF}}(d) = \frac{0.6}{60 + \text{rank}_{\text{dense}}(d)} + \frac{0.4}{60 + \text{rank}_{\text{lexical}}(d)}$$

### 4.3 Output Contract
```json
{
  "chunk_id": "SOP-04-SEC-02-route-planning",
  "document_id": "SOP-04",
  "document_type": "SOP",
  "section": "2. Route planning",
  "score": 0.92,
  "citation": "SOP-04 §2",
  "text": "Routes are planned in the mission planner with threat zones and weather as mandatory cost layers...",
  "source": "corpus/sop/SOP-04.md"
}
```

### 4.4 Service Interface
```python
def retrieve(
    query: str,
    top_k: int = 5,
    filters: dict[str, Any] | None = None
) -> list[dict[str, Any]]: ...
```
All retrieval logic is encapsulated in `app/rag.py` and `app/vector_store.py`.
