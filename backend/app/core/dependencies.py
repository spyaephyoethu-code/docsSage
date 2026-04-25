from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domain.services.kb_service import KBService
from app.infrastructure.db.repositories.kb_repository import KBRepository


def get_kb_repository(db: AsyncSession = Depends(get_db)) -> KBRepository:
    return KBRepository(db)


def get_kb_service(repo: KBRepository = Depends(get_kb_repository)) -> KBService:
    return KBService(repo)
