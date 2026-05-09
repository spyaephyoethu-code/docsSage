from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.llm.groq_client import GroqClient, _cost
from app.infrastructure.retrieval.types import RetrievedChunk


def make_message(role: str, content: str) -> MagicMock:
    msg = MagicMock()
    msg.role = role
    msg.content = content
    return msg


def make_groq_response(content: str, prompt_tokens: int = 100, completion_tokens: int = 50) -> dict:
    return {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
    }


def make_chunk(text: str) -> RetrievedChunk:
    return RetrievedChunk(pinecone_id="pid", chunk_text=text, rank_score=0.9)


@pytest.fixture
def client() -> GroqClient:
    with patch("app.infrastructure.llm.groq_client.settings") as mock_settings:
        mock_settings.groq_api_key = "test-key"
        return GroqClient()


@pytest.mark.asyncio
async def test_rewrite_query_returns_rewritten_string(client):
    history = [make_message("user", "what is FastAPI?"), make_message("assistant", "FastAPI is a framework.")]
    response = make_groq_response("What is the FastAPI framework used for?")

    with patch.object(client, "_call", new=AsyncMock(return_value=response)):
        rewritten, cost = await client.rewrite_query("what about it?", history)

    assert rewritten == "What is the FastAPI framework used for?"
    assert cost > 0


@pytest.mark.asyncio
async def test_rewrite_query_uses_summary_when_provided(client):
    history = [make_message("user", "follow up question")]
    response = make_groq_response("standalone question")

    with patch.object(client, "_call", new=AsyncMock(return_value=response)) as mock_call:
        await client.rewrite_query("follow up", history, summary="We discussed databases.")

    call_args = mock_call.call_args
    messages = call_args[0][1]
    user_content = messages[1]["content"]
    assert "Conversation summary" in user_content


@pytest.mark.asyncio
async def test_rewrite_query_without_summary(client):
    history = [make_message("user", "what is it?")]
    response = make_groq_response("standalone question")

    with patch.object(client, "_call", new=AsyncMock(return_value=response)) as mock_call:
        await client.rewrite_query("what about it?", history)

    call_args = mock_call.call_args
    messages = call_args[0][1]
    user_content = messages[1]["content"]
    assert "Conversation summary" not in user_content


@pytest.mark.asyncio
async def test_generate_returns_answer_and_cost(client):
    chunks = [make_chunk("FastAPI is a modern Python web framework.")]
    history = [make_message("user", "tell me about FastAPI")]
    response = make_groq_response("FastAPI is great [1].", prompt_tokens=200, completion_tokens=20)

    with patch.object(client, "_call", new=AsyncMock(return_value=response)):
        answer, cost = await client.generate("what is FastAPI?", chunks, history)

    assert answer == "FastAPI is great [1]."
    assert cost > 0


@pytest.mark.asyncio
async def test_generate_includes_chunk_text_in_prompt(client):
    chunks = [make_chunk("This is important context.")]
    history = []
    response = make_groq_response("answer")

    with patch.object(client, "_call", new=AsyncMock(return_value=response)) as mock_call:
        await client.generate("question", chunks, history)

    messages = mock_call.call_args[0][1]
    user_content = messages[1]["content"]
    assert "This is important context." in user_content


@pytest.mark.asyncio
async def test_summarize_history_returns_summary_and_cost(client):
    messages = [
        make_message("user", "what is async?"),
        make_message("assistant", "async allows concurrent execution."),
    ]
    response = make_groq_response("User asked about async programming.", prompt_tokens=80, completion_tokens=10)

    with patch.object(client, "_call", new=AsyncMock(return_value=response)):
        summary, cost = await client.summarize_history(messages, existing_summary=None)

    assert summary == "User asked about async programming."
    assert cost > 0


@pytest.mark.asyncio
async def test_summarize_history_incorporates_existing_summary(client):
    messages = [make_message("user", "and what about sync?")]
    response = make_groq_response("updated summary")

    with patch.object(client, "_call", new=AsyncMock(return_value=response)) as mock_call:
        await client.summarize_history(messages, existing_summary="Previous summary about async.")

    messages_sent = mock_call.call_args[0][1]
    user_content = messages_sent[1]["content"]
    assert "Previous summary about async." in user_content


def test_cost_calculation():
    usage = {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000}
    cost = _cost(usage, input_rate=1.0 / 1_000_000, output_rate=2.0 / 1_000_000)
    assert cost == pytest.approx(3.0)


def test_cost_with_missing_usage_keys():
    cost = _cost({}, input_rate=0.59 / 1_000_000, output_rate=0.79 / 1_000_000)
    assert cost == 0.0
