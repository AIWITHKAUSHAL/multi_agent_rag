import io

import numpy as np
import pytest
from pypdf import PdfWriter

from app.retrieval import Retriever, chunk_pages, extract_pages
from app.store import Store


def test_chunk_offsets_overlap_and_page_metadata():
    pages = ["Course fee is 12000. " * 50, "Refund policy. " * 20]
    chunks = chunk_pages(pages, 200, 40)
    for chunk in chunks:
        assert chunk["text"] == pages[chunk["page"] - 1][chunk["start"] : chunk["end"]]
        assert len(chunk["text"]) <= 200
    for page in (1, 2):
        parts = [c for c in chunks if c["page"] == page]
        assert parts[0]["start"] == 0 and parts[-1]["end"] == len(pages[page - 1])
        assert all(b["start"] == a["end"] - 40 for a, b in zip(parts, parts[1:]))


@pytest.mark.parametrize("size,overlap", [(0, 0), (20, 20), (10, 11), (20, -1)])
def test_invalid_chunk_settings(size, overlap):
    with pytest.raises(ValueError):
        chunk_pages(["text"], size, overlap)


@pytest.mark.parametrize(
    "name,content",
    [
        ("a.txt", b""),
        ("a.md", b"   "),
        ("a.exe", b"binary"),
        ("a.txt", b"\xff"),
        ("a.pdf", b"not a PDF"),
        ("a.txt", b"a\x00b"),
    ],
)
def test_invalid_upload_content(name, content):
    with pytest.raises(ValueError):
        extract_pages(name, content)


def test_scanned_pdf_has_actionable_error():
    pdf = PdfWriter()
    pdf.add_blank_page(width=100, height=100)
    content = io.BytesIO()
    pdf.write(content)
    with pytest.raises(ValueError, match="OCR"):
        extract_pages("scan.pdf", content.getvalue())


def test_encrypted_pdf_rejected():
    pdf = PdfWriter()
    pdf.add_blank_page(width=100, height=100)
    pdf.encrypt("secret")
    content = io.BytesIO()
    pdf.write(content)
    with pytest.raises(ValueError, match="Password"):
        extract_pages("private.pdf", content.getvalue())


def test_persistence_dedup_ranking_filter_and_delete(settings, doubles):
    path = settings.data_dir / "test.db"
    store = Store(path)
    retriever = Retriever(settings, store, doubles.embedder)
    fee = retriever.ingest("../../fee.md", b"Course fee fee fee is 12000.")
    refund = retriever.ingest("refund.txt", b"Refund refund refund policy.")
    assert fee["name"] == "fee.md"
    assert not retriever.ingest("copy.md", b"Course fee fee fee is 12000.")["created"]
    assert len(Store(path).documents()) == 2
    results = retriever.search("fee 12000", 1, [])
    assert len(results) == 1 and results[0]["document_id"] == fee["id"]
    assert results[0]["citation"] == "S1"
    filtered = retriever.search("refund", 8, [refund["id"]])
    assert {r["document_id"] for r in filtered} == {refund["id"]}
    assert store.search(np.array([0, 0, 1]), 4, settings.embedding_model, 0.99) == []
    assert store.delete_document(fee["id"])
    assert not store.document_chunks(fee["id"])
    assert not store.delete_document(fee["id"])


def test_embedding_model_change_requires_reindex(settings, doubles):
    retriever = Retriever(settings, Store(settings.data_dir / "test.db"), doubles.embedder)
    retriever.ingest("fee.md", b"fee is 12000")
    settings.embedding_model = "different-model"
    with pytest.raises(ValueError, match="different embedding model"):
        retriever.search("fee", 4, [])


def test_no_documents_avoids_embedding_download(settings):
    retriever = Retriever(settings, Store(settings.data_dir / "test.db"), None)
    assert retriever.search("fee", 4, []) == []
