import asyncio
import hashlib
import logging

import httpx

# runtime imports
from app.core.config import settings

logger = logging.getLogger(__name__)

_MODEL = "voyage-3-lite"
_BATCH_SIZE = 128
_API_URL = "https://api.voyageai.com/v1/embeddings"


class VoyageEmbedder:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), _BATCH_SIZE):
            batch = texts[i : i + _BATCH_SIZE]
            embeddings = await self._embed_with_retry(batch)
            all_embeddings.extend(embeddings)
        return all_embeddings

    async def _embed_with_retry(self, texts: list[str], max_retries: int = 3) -> list[list[float]]:
        headers = {
            "Authorization": f"Bearer {settings.voyage_api_key}",
            "Content-Type": "application/json",
        }
        payload = {"model": _MODEL, "input": texts}

        for attempt in range(max_retries):
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(_API_URL, headers=headers, json=payload)
                if resp.status_code == 429:
                    wait = 2**attempt
                    logger.warning(f"Voyage rate limit hit, retrying in {wait}s")
                    await asyncio.sleep(wait)
                    continue
                resp.raise_for_status()
                data = resp.json()
                return [item["embedding"] for item in data["data"]]

        raise RuntimeError("Voyage rate limit: max retries exceeded")

    @staticmethod
    def content_hash(text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()
