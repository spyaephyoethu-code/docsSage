import logging

import httpx

from app.core.circuit_breaker import check_cohere_budget, record_cohere_usage

# runtime imports
from app.core.config import settings
from app.infrastructure.retrieval.types import RetrievedChunk

logger = logging.getLogger(__name__)

_RERANK_URL = "https://api.cohere.com/v1/rerank"
_MODEL = "rerank-english-v3.0"

_client: "CohereReranker | None" = None


def get_cohere_reranker() -> "CohereReranker":
    global _client
    if _client is None:
        _client = CohereReranker()
    return _client


class CohereReranker:
    def __init__(self) -> None:
        self._headers = {
            "Authorization": f"Bearer {settings.cohere_api_key}",
            "Content-Type": "application/json",
        }

    async def rerank(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        top_n: int = 5,
    ) -> list[RetrievedChunk]:
        if not chunks:
            return []

        check_cohere_budget()

        documents = [c.chunk_text for c in chunks]
        payload = {
            "model": _MODEL,
            "query": query,
            "documents": documents,
            "top_n": top_n,
            "return_documents": False,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(_RERANK_URL, headers=self._headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        record_cohere_usage()

        reranked = []
        for result in data["results"]:
            idx = result["index"]
            chunk = chunks[idx]
            chunk.rank_score = result["relevance_score"]
            reranked.append(chunk)

        logger.info(f"Cohere rerank: {len(chunks)} → {len(reranked)} chunks")
        return reranked
