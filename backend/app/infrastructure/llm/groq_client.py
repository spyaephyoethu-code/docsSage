import logging

import httpx

# runtime imports
from app.core.config import settings

# type-hint imports
from app.infrastructure.db.models import Message
from app.infrastructure.retrieval.types import RetrievedChunk

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.groq.com/openai/v1/chat/completions"
_GEN_MODEL = "llama-3.3-70b-versatile"
_REWRITE_MODEL = "llama-3.1-8b-instant"
_MAX_TOKENS = 500

# Cost per 1M tokens (USD)
_GEN_INPUT_COST = 0.59 / 1_000_000
_GEN_OUTPUT_COST = 0.79 / 1_000_000
_REWRITE_INPUT_COST = 0.05 / 1_000_000
_REWRITE_OUTPUT_COST = 0.08 / 1_000_000

_client: "GroqClient | None" = None


def get_groq_client() -> "GroqClient":
    global _client
    if _client is None:
        _client = GroqClient()
    return _client


class GroqClient:
    def __init__(self) -> None:
        self._headers = {
            "Authorization": f"Bearer {settings.groq_api_key}",
            "Content-Type": "application/json",
        }

    async def rewrite_query(
        self, query: str, history: list[Message], *, summary: str | None = None
    ) -> tuple[str, float]:
        turns = "\n".join(f"{m.role.capitalize()}: {m.content}" for m in history)
        context = f"Conversation summary:\n{summary}\n\nRecent messages:\n{turns}" if summary else f"Conversation:\n{turns}"
        messages = [
            {
                "role": "system",
                "content": (
                    "Rewrite the user's follow-up question as a standalone, self-contained question "
                    "given the conversation history. Output ONLY the rewritten question, nothing else."
                ),
            },
            {
                "role": "user",
                "content": f"{context}\n\nFollow-up: {query}",
            },
        ]
        resp = await self._call(_REWRITE_MODEL, messages, max_tokens=150)
        rewritten = resp["choices"][0]["message"]["content"].strip()
        logger.info(f"Query rewritten: {query!r} → {rewritten!r}")
        usage = resp.get("usage", {})
        return rewritten, _cost(usage, _REWRITE_INPUT_COST, _REWRITE_OUTPUT_COST)

    async def summarize_history(
        self,
        messages: list[Message],
        existing_summary: str | None,
    ) -> tuple[str, float]:
        turns = "\n".join(f"{m.role.capitalize()}: {m.content}" for m in messages)
        if existing_summary:
            system_content = (
                "You are updating a running summary of a documentation assistant conversation. "
                "Incorporate the new turns into the existing summary. Be concise — capture key topics, "
                "questions asked, and answers given. Output ONLY the updated summary."
            )
            user_content = (
                f"Existing summary:\n{existing_summary}\n\n"
                f"New turns to incorporate:\n{turns}"
            )
        else:
            system_content = (
                "Summarize this documentation assistant conversation concisely. "
                "Capture the main topics, key questions, and important answers. "
                "Output ONLY the summary."
            )
            user_content = f"Conversation:\n{turns}"
        payload = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ]
        resp = await self._call(_REWRITE_MODEL, payload, max_tokens=300)
        summary = resp["choices"][0]["message"]["content"].strip()
        usage = resp.get("usage", {})
        return summary, _cost(usage, _REWRITE_INPUT_COST, _REWRITE_OUTPUT_COST)

    async def generate(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        history: list[Message],
        *,
        summary: str | None = None,
    ) -> tuple[str, float]:
        context_blocks = "\n\n".join(
            f"[{i}] {chunk.chunk_text}" for i, chunk in enumerate(chunks, start=1)
        )
        history_text = ""
        if summary:
            history_text += f"\nConversation summary:\n{summary}\n"
        if history:
            turns = "\n".join(f"{m.role.capitalize()}: {m.content}" for m in history)
            history_text += f"\nRecent messages:\n{turns}\n"

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a documentation assistant. Answer questions using ONLY the provided context passages.\n"
                    "- Add inline citations like [1], [2], etc. every time you use information from a passage.\n"
                    "- You may combine multiple passages; cite all relevant sources.\n"
                    "- If the context does not contain enough information, say: "
                    '"I don\'t have enough information in the provided sources to answer that."\n'
                    "- Be concise and factual."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Context:\n{context_blocks}\n{history_text}\nQuestion: {query}"
                ),
            },
        ]
        resp = await self._call(_GEN_MODEL, messages, max_tokens=_MAX_TOKENS)
        answer = resp["choices"][0]["message"]["content"].strip()
        usage = resp.get("usage", {})
        cost = _cost(usage, _GEN_INPUT_COST, _GEN_OUTPUT_COST)
        logger.info(
            f"Groq generation: {usage.get('total_tokens', '?')} tokens, ${cost:.6f}"
        )
        return answer, cost

    async def _call(self, model: str, messages: list[dict], max_tokens: int) -> dict:
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.1,
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(_BASE_URL, headers=self._headers, json=payload)
            resp.raise_for_status()
            return resp.json()


def _cost(usage: dict, input_rate: float, output_rate: float) -> float:
    return (
        usage.get("prompt_tokens", 0) * input_rate
        + usage.get("completion_tokens", 0) * output_rate
    )
