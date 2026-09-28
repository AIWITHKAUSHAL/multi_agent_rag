"""Extract documents, create local embeddings, and retrieve persistent source passages."""

import hashlib
import io
import threading
from pathlib import Path
from uuid import uuid4

import numpy as np
from pypdf import PdfReader

from app.store import now


def extract_pages(name, content):
    """Decode upload bytes into page text while preserving PDF page numbering.

    TXT/Markdown use one logical page and must be UTF-8. Reject unsupported files,
    encrypted or unreadable PDFs, empty/scanned text, and extraction-size limits
    with a ValueError suitable for the API's upload error response.
    """
    suffix = Path(name).suffix.lower()
    if suffix in {".txt", ".md"}:
        try:
            pages = [content.decode("utf-8-sig")]
        except UnicodeDecodeError as exc:
            raise ValueError("Text files must use UTF-8 encoding.") from exc
    elif suffix == ".pdf":
        try:
            reader = PdfReader(io.BytesIO(content))
            if reader.is_encrypted:
                raise ValueError("Password-protected PDFs are not supported.")
            if len(reader.pages) > 200:
                raise ValueError("PDFs are limited to 200 pages.")
            pages = [page.extract_text() or "" for page in reader.pages]
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("Cannot read this PDF. Upload a valid text-based PDF.") from exc
    else:
        raise ValueError("Supported files: .pdf, .txt and .md.")
    if not any(p.strip() for p in pages):
        raise ValueError("No text found. Scanned PDFs need OCR before uploading.")
    if sum(map(len, pages)) > 1_000_000:
        raise ValueError("Extracted text exceeds the 1 million character limit.")
    if any("\x00" in p for p in pages):
        raise ValueError("Binary content is not accepted as text.")
    return pages


def chunk_pages(pages, size=900, overlap=150):
    """Split each page into overlapping character windows with source offsets.

    Return dictionaries containing one-based page numbers, start/end offsets,
    and unmodified text slices. Prefer a whitespace boundary in the latter half
    of a window; overlap never crosses a page boundary. Invalid window settings
    raise ValueError before processing begins.
    """
    if overlap < 0 or size <= overlap:
        raise ValueError("Chunk size must exceed overlap.")
    chunks = []
    for page, text in enumerate(pages, 1):
        start = 0
        while start < len(text):
            end = min(start + size, len(text))
            if end < len(text):
                boundary = text.rfind(" ", start + size // 2, end)
                if boundary > start:
                    end = boundary
            if text[start:end].strip():
                chunks.append({"page": page, "start": start, "end": end, "text": text[start:end]})
            if end == len(text):
                break
            start = max(start + 1, end - overlap)
    return chunks


class Embedder:
    """Lazily load one local FastEmbed model and serialize its inference calls."""

    def __init__(self, settings):
        """Retain model/cache settings without downloading weights at app startup."""
        self.settings = settings
        self.model = None
        self.lock = threading.Lock()

    def encode(self, texts, query=False):
        """Return an L2-normalized float32 matrix, one embedding per input text.

        Use the model's query encoder when ``query=True`` and its passage encoder
        otherwise. The first call loads/downloads weights into the project cache.
        A lock protects both lazy initialization and inference across worker threads.
        """
        with self.lock:
            if self.model is None:
                from fastembed import TextEmbedding

                self.model = TextEmbedding(
                    model_name=self.settings.embedding_model,
                    cache_dir=str(self.settings.data_dir / "models"),
                    threads=2,
                )
            values = self.model.query_embed(texts) if query else self.model.embed(texts)
            vectors = np.array(list(values), dtype=np.float32)
            return vectors / np.maximum(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-12)


class Retriever:
    """Coordinate document extraction, embedding, deduplication, and vector search."""

    def __init__(self, settings, store, embedder):
        """Bind validated settings to the vector store and embedding implementation."""
        self.settings, self.store, self.embedder = settings, store, embedder

    def ingest(self, name, content):
        """Index upload bytes and return document metadata with a ``created`` flag.

        Sanitize the display filename, extract/chunk text, and fingerprint content
        together with the model and chunk configuration. Identical ingestion is
        deduplicated. New documents store normalized vectors and chunk metadata
        atomically through Store.insert_document; original file bytes are not saved.
        """
        name = Path(name.replace("\\", "/")).name[:180]
        pages = extract_pages(name, content)
        chunks = chunk_pages(pages, self.settings.chunk_size, self.settings.chunk_overlap)
        fingerprint = f"{self.settings.embedding_model}:{self.settings.chunk_size}:{self.settings.chunk_overlap}:".encode()
        digest = hashlib.sha256(fingerprint + content).hexdigest()
        for existing in self.store.documents():
            if existing["digest"] == digest:
                return {**existing, "created": False}
        vectors = self.embedder.encode([c["text"] for c in chunks])
        doc = dict(
            id=uuid4().hex,
            name=name,
            digest=digest,
            pages=len(pages),
            chunks=len(chunks),
            model=self.settings.embedding_model,
            created_at=now(),
        )
        stored, created = self.store.insert_document(doc, chunks, vectors)
        return {**stored, "created": created}

    def search(self, query, top_k, document_ids):
        """Embed a question and return scoped, ranked passages above the threshold.

        An empty document_ids list searches the whole library. Return an empty
        result without loading the embedder when the scope has no documents.
        Reject incompatible model metadata before delegating cosine search to Store.
        """
        docs = [d for d in self.store.documents() if not document_ids or d["id"] in document_ids]
        if any(d["model"] != self.settings.embedding_model for d in docs):
            raise ValueError("Some documents use a different embedding model. Delete and re-upload them.")
        if not docs:
            return []
        vector = self.embedder.encode([query], query=True)[0]
        return self.store.search(
            vector, top_k, self.settings.embedding_model, self.settings.min_similarity, document_ids
        )
