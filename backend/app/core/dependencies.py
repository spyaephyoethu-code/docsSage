from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

# runtime imports
from app.core.database import get_db
from app.domain.services.source_service import SourceService
from app.domain.services.kb_service import KBService
from app.infrastructure.db.repositories.chunk_repository import ChunkRepository
from app.infrastructure.db.repositories.kb_repository import KBRepository
from app.infrastructure.db.repositories.source_repository import SourceRepository
from app.infrastructure.vector_store.pinecone_client import PineconeClient, get_pinecone_client


def get_kb_repository(db: AsyncSession = Depends(get_db)) -> KBRepository:
    return KBRepository(db)


def get_kb_service(
    repo: KBRepository = Depends(get_kb_repository),
    chunk_repo: ChunkRepository = Depends(get_chunk_repository),
    pinecone: PineconeClient = Depends(get_pinecone_client),
) -> KBService:
    return KBService(repo, chunk_repo, pinecone)


def get_source_repository(db: AsyncSession = Depends(get_db)) -> SourceRepository:
    return SourceRepository(db)


def get_chunk_repository(db: AsyncSession = Depends(get_db)) -> ChunkRepository:
    return ChunkRepository(db)


def get_source_service(
    source_repo: SourceRepository = Depends(get_source_repository),
    chunk_repo: ChunkRepository = Depends(get_chunk_repository),
    pinecone: PineconeClient = Depends(get_pinecone_client),
) -> SourceService:
    return SourceService(source_repo, chunk_repo, pinecone)
