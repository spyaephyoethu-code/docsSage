import logging
import uuid
from typing import Any

from pinecone import Pinecone

# runtime imports
from app.core.config import settings
from app.infrastructure.retrieval.types import RetrievedChunk

logger = logging.getLogger(__name__)

_UPSERT_BATCH = 100
_client: "PineconeClient | None" = None


def get_pinecone_client() -> "PineconeClient":
    global _client
    if _client is None:
        _client = PineconeClient()
    return _client


class PineconeClient:
    def __init__(self) -> None:
        pc = Pinecone(api_key=settings.pinecone_api_key)
        self._index = pc.Index(settings.pinecone_index_name)

    def upsert_chunks(
        self,
        *,
        kb_id: uuid.UUID,
        source_id: uuid.UUID,
        source_type: str,
        user_id: uuid.UUID,
        chunk_ids: list[str],
        embeddings: list[list[float]],
        texts: list[str],
        metadatas: list[dict],
    ) -> None:
        vectors = []
        for chunk_id, embedding, text, meta in zip(
            chunk_ids, embeddings, texts, metadatas
        ):
            pinecone_meta: dict = {
                "kb_id": str(kb_id),
                "source_id": str(source_id),
                "source_type": source_type,
                "user_id": str(user_id),
                "chunk_text": text[:2000],
            }
            if meta.get("page_num") is not None:
                pinecone_meta["page_num"] = meta["page_num"]
            if meta.get("url"):
                pinecone_meta["url"] = meta["url"]
            if meta.get("source_title"):
                pinecone_meta["source_title"] = meta["source_title"]

            vectors.append(
                {"id": chunk_id, "values": embedding, "metadata": pinecone_meta}
            )

        for i in range(0, len(vectors), _UPSERT_BATCH):
            self._index.upsert(vectors=vectors[i : i + _UPSERT_BATCH])  # type: ignore[arg-type]

        logger.info(f"Upserted {len(vectors)} vectors for source {source_id}")

    def query(
        self,
        *,
        kb_id: uuid.UUID,
        user_id: uuid.UUID,
        vector: list[float],
        top_k: int = 20,
    ) -> list[RetrievedChunk]:
        _filter: Any = {"kb_id": str(kb_id), "user_id": str(user_id)}
        results = self._index.query(  # type: ignore[call-overload]
            vector=vector,
            top_k=top_k,
            filter=_filter,
            include_metadata=True,
        )
        chunks = []
        for match in results.matches:  # type: ignore[union-attr]
            meta = match.metadata or {}
            chunks.append(
                RetrievedChunk(
                    pinecone_id=match.id,
                    chunk_text=meta.get("chunk_text", ""),
                    rank_score=match.score,
                    source_url=meta.get("url") or meta.get("source_url"),
                    source_type=meta.get("source_type"),
                    source_id=meta.get("source_id"),
                    source_title=meta.get("source_title"),
                )
            )
        logger.info(f"Pinecone query for KB {kb_id}: {len(chunks)} results")
        return chunks

    def delete_by_ids(self, pinecone_ids: list[str]) -> None:
        _DELETE_BATCH = 1000
        for i in range(0, len(pinecone_ids), _DELETE_BATCH):
            self._index.delete(ids=pinecone_ids[i : i + _DELETE_BATCH])
