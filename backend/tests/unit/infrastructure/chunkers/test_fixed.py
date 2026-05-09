import pytest

from app.infrastructure.ingestion.base import Document
from app.infrastructure.ingestion.chunkers.fixed import FixedChunker


@pytest.fixture
def chunker() -> FixedChunker:
    return FixedChunker(chunk_size=10, overlap=2)


def make_doc(text: str, **meta) -> Document:
    return Document(text=text, metadata=meta)


def test_single_short_doc_produces_one_chunk(chunker):
    doc = make_doc("hello world")
    chunks = chunker.chunk([doc])

    assert len(chunks) == 1
    assert "hello" in chunks[0].text


def test_long_doc_produces_multiple_chunks(chunker):
    # 50 words — well over chunk_size=10 tokens
    text = " ".join(["word"] * 50)
    doc = make_doc(text)
    chunks = chunker.chunk([doc])

    assert len(chunks) > 1


def test_chunk_token_count_does_not_exceed_chunk_size(chunker):
    text = " ".join(["word"] * 100)
    doc = make_doc(text)
    chunks = chunker.chunk([doc])

    for chunk in chunks:
        assert chunk.token_count <= chunker._chunk_size


def test_overlap_means_chunks_share_content():
    chunker = FixedChunker(chunk_size=10, overlap=5)
    text = " ".join([f"word{i}" for i in range(30)])
    doc = make_doc(text)
    chunks = chunker.chunk([doc])

    # With overlap, adjacent chunks should share some tokens
    assert len(chunks) > 1
    # Verify total text covered is the full document (all words appear somewhere)
    combined = " ".join(c.text for c in chunks)
    assert "word0" in combined
    assert "word29" in combined


def test_metadata_is_copied_to_each_chunk(chunker):
    doc = make_doc("some text here", source="test.pdf", page_num=3)
    chunks = chunker.chunk([doc])

    for chunk in chunks:
        assert chunk.metadata["source"] == "test.pdf"
        assert chunk.metadata["page_num"] == 3


def test_metadata_copy_is_independent():
    chunker = FixedChunker(chunk_size=5, overlap=1)
    text = " ".join(["word"] * 20)
    doc = make_doc(text, key="value")
    chunks = chunker.chunk([doc])

    # Mutating one chunk's metadata should not affect others
    chunks[0].metadata["key"] = "modified"
    assert chunks[1].metadata["key"] == "value"


def test_multiple_documents_are_chunked_independently(chunker):
    doc1 = make_doc("first document text", source="a.pdf")
    doc2 = make_doc("second document text", source="b.pdf")
    chunks = chunker.chunk([doc1, doc2])

    sources = {c.metadata["source"] for c in chunks}
    assert sources == {"a.pdf", "b.pdf"}


def test_empty_document_list_returns_empty(chunker):
    chunks = chunker.chunk([])
    assert chunks == []
