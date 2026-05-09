import pytest

from app.domain.utils.citation import parse_citations
from app.infrastructure.retrieval.types import RetrievedChunk


def make_chunk(text: str, **kwargs) -> RetrievedChunk:
    return RetrievedChunk(
        pinecone_id="pid",
        chunk_text=text,
        rank_score=0.9,
        source_title=kwargs.get("source_title"),
        source_url=kwargs.get("source_url"),
        source_type=kwargs.get("source_type"),
    )


def test_cited_chunks_are_returned():
    chunks = [make_chunk("chunk one"), make_chunk("chunk two"), make_chunk("chunk three")]
    answer = "The answer is in [1] and [3]."

    citations = parse_citations(answer, chunks)

    indices = [c.index for c in citations]
    assert 1 in indices
    assert 3 in indices


def test_uncited_chunks_are_excluded():
    chunks = [make_chunk("chunk one"), make_chunk("chunk two")]
    answer = "Only [1] was used."

    citations = parse_citations(answer, chunks)

    assert len(citations) == 1
    assert citations[0].index == 1


def test_no_citations_returns_empty():
    chunks = [make_chunk("chunk one"), make_chunk("chunk two")]
    answer = "This answer has no citations."

    citations = parse_citations(answer, chunks)

    assert citations == []


def test_empty_chunks_returns_empty():
    citations = parse_citations("Answer with [1].", [])
    assert citations == []


def test_chunk_text_is_truncated_to_500_chars():
    long_text = "a" * 1000
    chunks = [make_chunk(long_text)]
    answer = "See [1]."

    citations = parse_citations(answer, chunks)

    assert len(citations[0].chunk_text) == 500


def test_source_metadata_is_mapped():
    chunks = [make_chunk(
        "some text",
        source_title="README.md",
        source_url="https://github.com/org/repo",
        source_type="github",
    )]
    answer = "See [1]."

    citations = parse_citations(answer, chunks)

    assert citations[0].source_name == "README.md"
    assert citations[0].source_url == "https://github.com/org/repo"
    assert citations[0].source_type == "github"


def test_duplicate_citation_references_counted_once():
    chunks = [make_chunk("chunk one"), make_chunk("chunk two")]
    answer = "See [1] and also [1] again."

    citations = parse_citations(answer, chunks)

    assert len(citations) == 1
    assert citations[0].index == 1


def test_citation_index_out_of_range_is_ignored():
    chunks = [make_chunk("only one chunk")]
    answer = "See [1] and [99]."

    citations = parse_citations(answer, chunks)

    indices = [c.index for c in citations]
    assert 1 in indices
    assert 99 not in indices


def test_multiple_citations_preserve_order():
    chunks = [make_chunk("a"), make_chunk("b"), make_chunk("c")]
    answer = "From [3], [1], and [2]."

    citations = parse_citations(answer, chunks)

    assert [c.index for c in citations] == [1, 2, 3]
