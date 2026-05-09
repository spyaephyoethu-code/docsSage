import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.retrieval.bm25 import BM25Retriever


def make_chunk_row(text: str, pinecone_id: str = "pid") -> MagicMock:
    row = MagicMock()
    row.chunk_text = text
    row.pinecone_id = pinecone_id
    row.source_url = None
    row.source_title = None
    return row


@pytest.fixture
def retriever() -> BM25Retriever:
    return BM25Retriever()


@pytest.fixture
def kb_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def mock_chunks():
    return [
        make_chunk_row("database connection timeout error", "pid1"),
        make_chunk_row("how to configure the database", "pid2"),
        make_chunk_row("timeout settings for the server", "pid3"),
        make_chunk_row("python async programming guide", "pid4"),
    ]


@pytest.mark.asyncio
async def test_query_builds_index_on_first_call(retriever, kb_id, mock_chunks):
    with patch("app.infrastructure.retrieval.bm25.AsyncSessionLocal") as mock_session, \
         patch("app.infrastructure.retrieval.bm25.ChunkRepository") as mock_repo_cls:

        mock_repo = AsyncMock()
        mock_repo.get_all_by_kb.return_value = mock_chunks
        mock_repo_cls.return_value = mock_repo

        mock_session.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        mock_session.return_value.__aexit__ = AsyncMock(return_value=False)

        await retriever.query(kb_id=kb_id, query="database timeout", top_k=5)

        assert kb_id in retriever._cache


@pytest.mark.asyncio
async def test_query_does_not_rebuild_index_on_second_call(retriever, kb_id, mock_chunks):
    with patch("app.infrastructure.retrieval.bm25.AsyncSessionLocal") as mock_session, \
         patch("app.infrastructure.retrieval.bm25.ChunkRepository") as mock_repo_cls:

        mock_repo = AsyncMock()
        mock_repo.get_all_by_kb.return_value = mock_chunks
        mock_repo_cls.return_value = mock_repo

        mock_session.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        mock_session.return_value.__aexit__ = AsyncMock(return_value=False)

        await retriever.query(kb_id=kb_id, query="database", top_k=5)
        await retriever.query(kb_id=kb_id, query="timeout", top_k=5)

        # DB should only be called once
        assert mock_repo.get_all_by_kb.call_count == 1


def test_relevant_chunk_scores_higher_than_irrelevant(retriever, kb_id):
    from rank_bm25 import BM25Okapi

    # Use 6 chunks so "database"(1/6) and "timeout"(1/6) have non-zero IDF.
    # BM25Okapi IDF = log((N-n+0.5)/(n+0.5)) — zero when n = N/2, so avoid 50% occurrence.
    raw = [
        ("database connection timeout error", "pid1"),
        ("python async programming guide", "pid2"),
        ("fastapi routing and middleware", "pid3"),
        ("docker container orchestration", "pid4"),
        ("git branching strategies", "pid5"),
        ("ci cd pipeline setup", "pid6"),
    ]
    texts = [r[0] for r in raw]
    metas = [{"pinecone_id": r[1], "source_url": None, "source_title": None} for r in raw]
    tokenized = [t.lower().split() for t in texts]
    retriever._cache[kb_id] = (BM25Okapi(tokenized), texts, metas)

    results = retriever._search(kb_id, "database timeout", top_k=5)

    # Only chunk 0 contains both query words — must be the top result
    assert len(results) > 0
    assert results[0].pinecone_id == "pid1"


@pytest.mark.asyncio
async def test_zero_score_chunks_are_excluded(retriever, kb_id):
    chunks = [
        make_chunk_row("completely unrelated text about cats", "pid1"),
        make_chunk_row("another unrelated topic about weather", "pid2"),
    ]
    with patch("app.infrastructure.retrieval.bm25.AsyncSessionLocal") as mock_session, \
         patch("app.infrastructure.retrieval.bm25.ChunkRepository") as mock_repo_cls:

        mock_repo = AsyncMock()
        mock_repo.get_all_by_kb.return_value = chunks
        mock_repo_cls.return_value = mock_repo

        mock_session.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        mock_session.return_value.__aexit__ = AsyncMock(return_value=False)

        results = await retriever.query(kb_id=kb_id, query="database timeout", top_k=5)

        # No chunks share words with the query — should return empty
        assert results == []


def test_invalidate_removes_kb_from_cache(retriever, kb_id):
    retriever._cache[kb_id] = (MagicMock(), [], [])
    retriever.invalidate(kb_id)

    assert kb_id not in retriever._cache


def test_invalidate_nonexistent_kb_does_not_raise(retriever, kb_id):
    retriever.invalidate(kb_id)  # should not raise


@pytest.mark.asyncio
async def test_empty_kb_returns_empty_results(retriever, kb_id):
    with patch("app.infrastructure.retrieval.bm25.AsyncSessionLocal") as mock_session, \
         patch("app.infrastructure.retrieval.bm25.ChunkRepository") as mock_repo_cls:

        mock_repo = AsyncMock()
        mock_repo.get_all_by_kb.return_value = []
        mock_repo_cls.return_value = mock_repo

        mock_session.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        mock_session.return_value.__aexit__ = AsyncMock(return_value=False)

        results = await retriever.query(kb_id=kb_id, query="anything", top_k=5)

        assert results == []
