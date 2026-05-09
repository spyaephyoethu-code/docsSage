import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.llm.groq_client import GroqClient
from app.infrastructure.retrieval.types import RetrievedChunk


def make_chunk(text: str) -> RetrievedChunk:
    return RetrievedChunk(pinecone_id="pid", chunk_text=text, rank_score=0.9)


def make_sse_line(content: str) -> str:
    return f"data: {json.dumps({'choices': [{'delta': {'content': content}}], 'usage': None})}"


def make_usage_line(prompt_tokens: int, completion_tokens: int) -> str:
    return f"data: {json.dumps({'choices': [], 'usage': {'prompt_tokens': prompt_tokens, 'completion_tokens': completion_tokens, 'total_tokens': prompt_tokens + completion_tokens}})}"


@pytest.fixture
def client() -> GroqClient:
    with patch("app.infrastructure.llm.groq_client.settings") as mock_settings:
        mock_settings.groq_api_key = "test-key"
        return GroqClient()


async def collect_stream(client, chunks, history=None, summary=None):
    tokens = []
    final_cost = None
    async for token, cost in client.generate_stream(
        query="test query",
        chunks=chunks,
        history=history or [],
        summary=summary,
    ):
        if token is None:
            final_cost = cost
        else:
            tokens.append(token)
    return tokens, final_cost


def mock_stream_response(lines: list[str]):
    async def aiter_lines():
        for line in lines:
            yield line

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.aiter_lines = aiter_lines
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)
    return mock_resp


@pytest.mark.asyncio
async def test_generate_stream_yields_tokens(client):
    lines = [
        make_sse_line("FastAPI"),
        make_sse_line(" is"),
        make_sse_line(" great"),
        make_usage_line(100, 10),
        "data: [DONE]",
    ]

    with patch("httpx.AsyncClient") as mock_http:
        mock_client = MagicMock()
        mock_client.stream.return_value = mock_stream_response(lines)
        mock_http.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_http.return_value.__aexit__ = AsyncMock(return_value=False)

        tokens, cost = await collect_stream(client, [make_chunk("FastAPI context")])

    assert tokens == ["FastAPI", " is", " great"]


@pytest.mark.asyncio
async def test_generate_stream_yields_cost_at_end(client):
    lines = [
        make_sse_line("hello"),
        make_usage_line(1_000_000, 1_000_000),
        "data: [DONE]",
    ]

    with patch("httpx.AsyncClient") as mock_http:
        mock_client = MagicMock()
        mock_client.stream.return_value = mock_stream_response(lines)
        mock_http.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_http.return_value.__aexit__ = AsyncMock(return_value=False)

        _, cost = await collect_stream(client, [make_chunk("context")])

    # 1M prompt tokens * 0.59/1M + 1M completion * 0.79/1M = 1.38
    assert cost == pytest.approx(1.38)


@pytest.mark.asyncio
async def test_generate_stream_stops_at_done(client):
    lines = [
        make_sse_line("token1"),
        "data: [DONE]",
        make_sse_line("token2"),  # should never be reached
    ]

    with patch("httpx.AsyncClient") as mock_http:
        mock_client = MagicMock()
        mock_client.stream.return_value = mock_stream_response(lines)
        mock_http.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_http.return_value.__aexit__ = AsyncMock(return_value=False)

        tokens, _ = await collect_stream(client, [make_chunk("context")])

    assert tokens == ["token1"]


@pytest.mark.asyncio
async def test_generate_stream_skips_empty_delta(client):
    lines = [
        make_sse_line("hello"),
        f"data: {json.dumps({'choices': [{'delta': {'content': ''}}], 'usage': None})}",
        make_sse_line(" world"),
        make_usage_line(10, 5),
        "data: [DONE]",
    ]

    with patch("httpx.AsyncClient") as mock_http:
        mock_client = MagicMock()
        mock_client.stream.return_value = mock_stream_response(lines)
        mock_http.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_http.return_value.__aexit__ = AsyncMock(return_value=False)

        tokens, _ = await collect_stream(client, [make_chunk("context")])

    assert tokens == ["hello", " world"]


@pytest.mark.asyncio
async def test_generate_stream_skips_non_data_lines(client):
    lines = [
        "",                        # blank line
        ": keep-alive",            # SSE comment
        make_sse_line("hello"),
        make_usage_line(10, 5),
        "data: [DONE]",
    ]

    with patch("httpx.AsyncClient") as mock_http:
        mock_client = MagicMock()
        mock_client.stream.return_value = mock_stream_response(lines)
        mock_http.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_http.return_value.__aexit__ = AsyncMock(return_value=False)

        tokens, _ = await collect_stream(client, [make_chunk("context")])

    assert tokens == ["hello"]


@pytest.mark.asyncio
async def test_generate_stream_includes_chunk_context_in_payload(client):
    lines = [make_sse_line("answer"), make_usage_line(10, 5), "data: [DONE]"]

    with patch("httpx.AsyncClient") as mock_http:
        mock_client = MagicMock()
        mock_client.stream.return_value = mock_stream_response(lines)
        mock_http.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_http.return_value.__aexit__ = AsyncMock(return_value=False)

        await collect_stream(client, [make_chunk("important context")])

    call_kwargs = mock_client.stream.call_args[1]
    user_content = call_kwargs["json"]["messages"][1]["content"]
    assert "important context" in user_content


@pytest.mark.asyncio
async def test_generate_stream_sends_stream_true_in_payload(client):
    lines = [make_sse_line("answer"), make_usage_line(10, 5), "data: [DONE]"]

    with patch("httpx.AsyncClient") as mock_http:
        mock_client = MagicMock()
        mock_client.stream.return_value = mock_stream_response(lines)
        mock_http.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_http.return_value.__aexit__ = AsyncMock(return_value=False)

        await collect_stream(client, [make_chunk("context")])

    call_kwargs = mock_client.stream.call_args[1]
    assert call_kwargs["json"]["stream"] is True
    assert call_kwargs["json"]["stream_options"]["include_usage"] is True
