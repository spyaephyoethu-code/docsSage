import pytest

from app.infrastructure.retrieval.rrf import rrf_merge
from app.infrastructure.retrieval.types import RetrievedChunk


def make_chunk(pid: str, score: float = 0.5) -> RetrievedChunk:
    return RetrievedChunk(pinecone_id=pid, chunk_text=f"text for {pid}", rank_score=score)


def test_chunk_in_both_lists_scores_higher_than_chunk_in_one():
    dense = [make_chunk("a"), make_chunk("b"), make_chunk("c")]
    sparse = [make_chunk("a"), make_chunk("d"), make_chunk("e")]

    results = rrf_merge(dense, sparse)
    ids = [r.pinecone_id for r in results]

    # "a" appears in both lists — should be ranked first
    assert ids[0] == "a"


def test_deduplication_no_duplicate_ids():
    dense = [make_chunk("a"), make_chunk("b")]
    sparse = [make_chunk("a"), make_chunk("c")]

    results = rrf_merge(dense, sparse)
    ids = [r.pinecone_id for r in results]

    assert len(ids) == len(set(ids))


def test_top_n_limits_results():
    dense = [make_chunk(str(i)) for i in range(20)]
    sparse = [make_chunk(str(i + 20)) for i in range(20)]

    results = rrf_merge(dense, sparse, top_n=10)

    assert len(results) <= 10


def test_empty_dense_returns_sparse_only():
    sparse = [make_chunk("a"), make_chunk("b")]

    results = rrf_merge([], sparse)
    ids = [r.pinecone_id for r in results]

    assert set(ids) == {"a", "b"}


def test_empty_sparse_returns_dense_only():
    dense = [make_chunk("a"), make_chunk("b")]

    results = rrf_merge(dense, [])
    ids = [r.pinecone_id for r in results]

    assert set(ids) == {"a", "b"}


def test_both_empty_returns_empty():
    results = rrf_merge([], [])
    assert results == []


def test_rank_score_is_updated_to_rrf_score():
    dense = [make_chunk("a", score=0.99)]
    sparse = [make_chunk("b", score=0.01)]

    results = rrf_merge(dense, sparse)

    # rank_score should now be the RRF score, not the original cosine/bm25 score
    for r in results:
        assert r.rank_score < 1.0  # RRF scores are always < 1


def test_higher_rank_yields_higher_rrf_score():
    dense = [make_chunk("a"), make_chunk("b"), make_chunk("c")]
    results = rrf_merge(dense, [])

    scores = [r.rank_score for r in results]
    assert scores == sorted(scores, reverse=True)
