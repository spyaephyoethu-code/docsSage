from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

# runtime imports
from app.core.quotas import MAX_KBS_PER_USER
from app.domain.exceptions import KBLimitExceeded, KBNotFound
from app.domain.schemas.kb import KBCreate, KBUpdate

# type-hint imports
if TYPE_CHECKING:
    from app.infrastructure.db.models import KnowledgeBase
    from app.infrastructure.db.repositories.chunk_repository import ChunkRepository
    from app.infrastructure.db.repositories.kb_repository import KBRepository
    from app.infrastructure.vector_store.pinecone_client import PineconeClient


class KBService:
    def __init__(
        self,
        repo: KBRepository,
        chunk_repo: ChunkRepository,
        pinecone: PineconeClient,
    ) -> None:
        self.repo = repo
        self._chunk_repo = chunk_repo
        self._pinecone = pinecone

    async def list_kbs(self, user_id: uuid.UUID) -> list[KnowledgeBase]:
        return await self.repo.list_by_user(user_id)

    async def get_kb(self, kb_id: uuid.UUID, user_id: uuid.UUID) -> KnowledgeBase:
        kb = await self.repo.get_owned(kb_id, user_id)
        if kb is None:
            raise KBNotFound(f"Knowledge base {kb_id} not found.")
        return kb

    async def create_kb(self, user_id: uuid.UUID, body: KBCreate) -> KnowledgeBase:
        count = await self.repo.count_by_user(user_id)
        if count >= MAX_KBS_PER_USER:
            raise KBLimitExceeded(
                f"Maximum {MAX_KBS_PER_USER} knowledge bases per user reached."
            )
        return await self.repo.create(user_id, body.name, body.description)

    async def update_kb(
        self, kb_id: uuid.UUID, user_id: uuid.UUID, body: KBUpdate
    ) -> KnowledgeBase:
        kb = await self.get_kb(kb_id, user_id)
        return await self.repo.update(kb, body.name, body.description)

    async def delete_kb(self, kb_id: uuid.UUID, user_id: uuid.UUID) -> None:
        kb = await self.get_kb(kb_id, user_id)
        pinecone_ids = await self._chunk_repo.get_pinecone_ids_by_kb(kb_id)
        if pinecone_ids:
            self._pinecone.delete_by_ids(pinecone_ids)
        await self.repo.delete(kb)
