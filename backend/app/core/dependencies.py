from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

# runtime imports
from app.core.database import get_db
from app.domain.services.chat_service import ChatService
from app.domain.services.kb_service import KBService
from app.domain.services.source_service import SourceService
from app.infrastructure.db.repositories.chunk_repository import ChunkRepository
from app.infrastructure.db.repositories.conversation_repository import (
    ConversationRepository,
)
from app.infrastructure.db.repositories.kb_repository import KBRepository
from app.infrastructure.db.repositories.message_repository import MessageRepository
from app.infrastructure.db.repositories.source_repository import SourceRepository
from app.infrastructure.embeddings.voyage import VoyageEmbedder
from app.infrastructure.llm.groq_client import GroqClient, get_groq_client
from app.infrastructure.reranker.cohere_client import (
    CohereReranker,
    get_cohere_reranker,
)
from app.infrastructure.retrieval.bm25 import BM25Retriever, get_bm25_retriever
from app.infrastructure.vector_store.pinecone_client import (
    PineconeClient,
    get_pinecone_client,
)


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


def get_conversation_repository(
    db: AsyncSession = Depends(get_db),
) -> ConversationRepository:
    return ConversationRepository(db)


def get_message_repository(db: AsyncSession = Depends(get_db)) -> MessageRepository:
    return MessageRepository(db)


def get_embedder() -> VoyageEmbedder:
    return VoyageEmbedder()


def get_chat_service(
    conv_repo: ConversationRepository = Depends(get_conversation_repository),
    msg_repo: MessageRepository = Depends(get_message_repository),
    embedder: VoyageEmbedder = Depends(get_embedder),
    pinecone: PineconeClient = Depends(get_pinecone_client),
    bm25: BM25Retriever = Depends(get_bm25_retriever),
    reranker: CohereReranker = Depends(get_cohere_reranker),
    groq: GroqClient = Depends(get_groq_client),
) -> ChatService:
    return ChatService(conv_repo, msg_repo, embedder, pinecone, bm25, reranker, groq)


