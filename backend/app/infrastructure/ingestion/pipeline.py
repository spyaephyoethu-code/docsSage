"""
Background ingestion pipeline. Called as a FastAPI BackgroundTask.
Creates its own DB session because the request session is already closed.
"""

import asyncio
import logging
import os
import uuid

# runtime imports
from app.core.database import AsyncSessionLocal
from app.infrastructure.db.repositories.chunk_repository import ChunkRepository
from app.infrastructure.db.repositories.source_repository import SourceRepository
from app.infrastructure.embeddings.voyage import VoyageEmbedder

# type-hint imports
from app.infrastructure.ingestion.base import Chunk
from app.infrastructure.ingestion.chunkers.fixed import FixedChunker
from app.infrastructure.ingestion.chunkers.markdown import MarkdownChunker
from app.infrastructure.ingestion.chunkers.semantic import SemanticChunker
from app.infrastructure.ingestion.loaders.github import GitHubLoader
from app.infrastructure.ingestion.loaders.pdf import PDFLoader
from app.infrastructure.ingestion.loaders.text import TextLoader
from app.infrastructure.ingestion.loaders.web import WebLoader
from app.infrastructure.ingestion.loaders.word import WordLoader
from app.infrastructure.retrieval.bm25 import get_bm25_retriever
from app.infrastructure.vector_store.pinecone_client import PineconeClient

logger = logging.getLogger(__name__)

_MIN_TOKENS = 50
_MAX_CHUNKS = 5_000
_TIMEOUT_SECONDS = 600  # 10 minutes

_LOADERS = {
    "github": GitHubLoader,
    "pdf": PDFLoader,
    "web": WebLoader,
    "text": TextLoader,
    "word": WordLoader,
}

_CHUNKERS = {
    "fixed": FixedChunker,
    "markdown": MarkdownChunker,
    "semantic": SemanticChunker,
}


async def _ingest(
    source_repo: SourceRepository,
    chunk_repo: ChunkRepository,
    source_id: uuid.UUID,
    user_id: uuid.UUID,
    kb_id: uuid.UUID,
) -> None:
    source = await source_repo.get(source_id, kb_id)
    if source is None:
        logger.error(f"[{source_id}] Source not found — aborting ingestion")
        return

    loader_cls = _LOADERS.get(source.type)
    if loader_cls is None:
        raise ValueError(f"Unknown source type: {source.type}")

    documents = await loader_cls().load(source.url_or_path or "")  # type: ignore[abstract]
    logger.info(f"[{source_id}] Loaded {len(documents)} documents")

    chunker_cls = _CHUNKERS.get(source.chunking_strategy or "fixed") or FixedChunker
    chunks: list[Chunk] = chunker_cls().chunk(documents)  # type: ignore[abstract]
    logger.info(f"[{source_id}] {len(chunks)} raw chunks")

    seen: set[str] = set()
    unique: list[Chunk] = []
    for chunk in chunks:
        if chunk.text not in seen:
            seen.add(chunk.text)
            unique.append(chunk)

    unique = [c for c in unique if c.token_count >= _MIN_TOKENS]

    if len(unique) > _MAX_CHUNKS:
        logger.warning(f"[{source_id}] Truncating {len(unique)} → {_MAX_CHUNKS} chunks")
        unique = unique[:_MAX_CHUNKS]

    logger.info(f"[{source_id}] Embedding {len(unique)} chunks")

    texts = [c.text for c in unique]
    embeddings = await VoyageEmbedder().embed(texts)

    chunk_ids = [str(uuid.uuid4()) for _ in unique]

    # GitHub chunks already carry file_path (e.g. "src/api/routes.py") per chunk.
    # PDF/Word/Text loaders don't set file_path, so fall back to the source filename.
    source_filename = os.path.basename(source.url_or_path or "") or None
    metadatas = [
        {**c.metadata, "source_title": c.metadata.get("file_path") or source_filename}
        for c in unique
    ]

    PineconeClient().upsert_chunks(
        kb_id=kb_id,
        source_id=source_id,
        source_type=source.type,
        user_id=user_id,
        chunk_ids=chunk_ids,
        embeddings=embeddings,
        texts=texts,
        metadatas=metadatas,
    )

    await chunk_repo.bulk_create(
        source_id,
        [
            {
                "text": c.text,
                "pinecone_id": cid,
                "token_count": c.token_count,
                "source_url": c.metadata.get("url"),
                "source_title": c.metadata.get("file_path") or source_filename,
            }
            for c, cid in zip(unique, chunk_ids)
        ],
    )

    await source_repo.update_status(source_id, "completed", len(unique))
    get_bm25_retriever().invalidate(kb_id)
    logger.info(f"[{source_id}] Ingestion complete — {len(unique)} chunks in Pinecone")


async def run_ingestion_task(
    source_id: uuid.UUID,
    user_id: uuid.UUID,
    kb_id: uuid.UUID,
) -> None:
    async with AsyncSessionLocal() as db:
        source_repo = SourceRepository(db)
        chunk_repo = ChunkRepository(db)

        await source_repo.update_status(source_id, "running")

        try:
            await asyncio.wait_for(
                _ingest(source_repo, chunk_repo, source_id, user_id, kb_id),
                timeout=_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            logger.error(f"[{source_id}] Ingestion timed out after {_TIMEOUT_SECONDS}s")
            await source_repo.update_status(
                source_id,
                "failed",
                error_message="Ingestion timed out after 10 minutes — please retry",
            )
        except Exception as exc:
            logger.exception(f"[{source_id}] Ingestion failed")
            await source_repo.update_status(source_id, "failed", error_message=str(exc))
