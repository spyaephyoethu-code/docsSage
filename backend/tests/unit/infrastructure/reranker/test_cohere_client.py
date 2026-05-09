from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.reranker.cohere_client import CohereReranker
from app.infrastructure.retrieval.types import RetrievedChunk


def make_chunk(pid: str, text: str, score: float = 0.5) -> RetrievedChunk:
    return RetrievedChunk(pinecone_id=pid, chunk_text=text, rank_score=score)


def make_cohere_response(results: list[dict]) -> dict:
    return {"results": results}


@pytest.fixture
def reranker() -> CohereReranker:
    with patch("app.infrastructure.reranker.cohere_client.settings") as mock_settings:
        mock_settings.cohere_api_key = "test-key"
        return CohereReranker()


@pytest.mark.asyncio
async def test_rerank_returns_top_n_chunks(reranker):
    chunks = [
        make_chunk("a", "database connection timeout"),
        make_chunk("b", "python async programming"),
        make_chunk("c", "timeout configuration settings"),
    ]
    cohere_response = make_cohere_response([
        {"index": 0, "relevance_score": 0.95},
        {"index": 2, "relevance_score": 0.80},
    ])

    with patch("app.infrastructure.reranker.cohere_client.check_cohere_budget"), \
         patch("app.infrastructure.reranker.cohere_client.record_cohere_usage"), \
         patch("httpx.AsyncClient") as mock_http:

        mock_resp = MagicMock()
        mock_resp.json.return_value = cohere_response
        mock_resp.raise_for_status = MagicMock()

        mock_http.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
            post=AsyncMock(return_value=mock_resp)
        ))
        mock_http.return_value.__aexit__ = AsyncMock(return_value=False)

        results = await reranker.rerank("database timeout", chunks, top_n=2)

    assert len(results) == 2


@pytest.mark.asyncio
async def test_rerank_attaches_relevance_score(reranker):
    chunks = [make_chunk("a", "database connection timeout")]
    cohere_response = make_cohere_response([{"index": 0, "relevance_score": 0.95}])

    with patch("app.infrastructure.reranker.cohere_client.check_cohere_budget"), \
         patch("app.infrastructure.reranker.cohere_client.record_cohere_usage"), \
         patch("httpx.AsyncClient") as mock_http:

        mock_resp = MagicMock()
        mock_resp.json.return_value = cohere_response
        mock_resp.raise_for_status = MagicMock()

        mock_http.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
            post=AsyncMock(return_value=mock_resp)
        ))
        mock_http.return_value.__aexit__ = AsyncMock(return_value=False)

        results = await reranker.rerank("database", chunks, top_n=1)

    assert results[0].rank_score == pytest.approx(0.95)


@pytest.mark.asyncio
async def test_rerank_empty_chunks_returns_empty(reranker):
    results = await reranker.rerank("any query", [], top_n=5)
    assert results == []


@pytest.mark.asyncio
async def test_rerank_checks_budget_before_calling_api(reranker):
    chunks = [make_chunk("a", "some text")]

    with patch("app.infrastructure.reranker.cohere_client.check_cohere_budget") as mock_budget, \
         patch("app.infrastructure.reranker.cohere_client.record_cohere_usage"), \
         patch("httpx.AsyncClient") as mock_http:

        mock_resp = MagicMock()
        mock_resp.json.return_value = make_cohere_response([{"index": 0, "relevance_score": 0.9}])
        mock_resp.raise_for_status = MagicMock()

        mock_http.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
            post=AsyncMock(return_value=mock_resp)
        ))
        mock_http.return_value.__aexit__ = AsyncMock(return_value=False)

        await reranker.rerank("query", chunks, top_n=1)

    mock_budget.assert_called_once()


@pytest.mark.asyncio
async def test_rerank_records_usage_after_api_call(reranker):
    chunks = [make_chunk("a", "some text")]

    with patch("app.infrastructure.reranker.cohere_client.check_cohere_budget"), \
         patch("app.infrastructure.reranker.cohere_client.record_cohere_usage") as mock_record, \
         patch("httpx.AsyncClient") as mock_http:

        mock_resp = MagicMock()
        mock_resp.json.return_value = make_cohere_response([{"index": 0, "relevance_score": 0.9}])
        mock_resp.raise_for_status = MagicMock()

        mock_http.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
            post=AsyncMock(return_value=mock_resp)
        ))
        mock_http.return_value.__aexit__ = AsyncMock(return_value=False)

        await reranker.rerank("query", chunks, top_n=1)

    mock_record.assert_called_once()
