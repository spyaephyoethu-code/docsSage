import logging
import time
import uuid

from rank_bm25 import BM25Okapi

# runtime imports
from app.core.database import AsyncSessionLocal
from app.infrastructure.db.repositories.chunk_repository import ChunkRepository
from app.infrastructure.retrieval.types import RetrievedChunk

logger = logging.getLogger(__name__)

_retriever: "BM25Retriever | None" = None


def get_bm25_retriever() -> "BM25Retriever":
    global _retriever
    if _retriever is None:
        _retriever = BM25Retriever()
    return _retriever


class BM25Retriever:
    def __init__(self) -> None:
        # kb_id → (BM25Okapi, texts, metadatas)
        self._cache: dict[uuid.UUID, tuple[BM25Okapi, list[str], list[dict]]] = {}

    async def query(
        self,
        kb_id: uuid.UUID,
        query: str,
        top_k: int = 20,
    ) -> list[RetrievedChunk]:
        if kb_id not in self._cache:
            await self._build(kb_id)
        return self._search(kb_id, query, top_k)

    def invalidate(self, kb_id: uuid.UUID) -> None:
        self._cache.pop(kb_id, None)
        logger.info(f"BM25 cache invalidated for KB {kb_id}")

    async def _build(self, kb_id: uuid.UUID) -> None:
        t0 = time.monotonic()
        async with AsyncSessionLocal() as db:
            chunks = await ChunkRepository(db).get_all_by_kb(kb_id)

        texts = [c.chunk_text for c in chunks]
        metas = [
            {
                "pinecone_id": c.pinecone_id,
                "source_url": c.source_url,
                "source_title": c.source_title,
            }
            for c in chunks
        ]

        if not texts:
            logger.warning(
                f"BM25 build for KB {kb_id}: no chunks found, index will be empty"
            )
            self._cache[kb_id] = (BM25Okapi([[""]]), texts, metas)
            return

        tokenized = [t.lower().split() for t in texts]
        bm25 = BM25Okapi(tokenized)
        self._cache[kb_id] = (bm25, texts, metas)

        elapsed_ms = (time.monotonic() - t0) * 1000
        logger.info(
            f"BM25 index built for KB {kb_id}: {len(texts)} chunks in {elapsed_ms:.0f}ms"
        )

    def _search(self, kb_id: uuid.UUID, query: str, top_k: int) -> list[RetrievedChunk]:
        bm25, texts, metas = self._cache[kb_id]
        if not texts:
            return []

        tokens = query.lower().split()
        scores = bm25.get_scores(tokens)

        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[
            :top_k
        ]
        results = []
        for i in top_indices:
            if scores[i] <= 0:
                break
            results.append(
                RetrievedChunk(
                    pinecone_id=metas[i]["pinecone_id"] or f"bm25_{i}",
                    chunk_text=texts[i],
                    rank_score=float(scores[i]),
                    source_url=metas[i].get("source_url"),
                    source_title=metas[i].get("source_title"),
                )
            )
        return results
