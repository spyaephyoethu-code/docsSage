import uuid

from fastapi import Depends, HTTPException, status

# runtime imports — used in function logic and FastAPI machinery
from app.core.dependencies import get_kb_service
from app.core.middleware.auth import CurrentUser
from app.domain.exceptions import KBLimitExceeded, KBNotFound
from app.domain.schemas.kb import KBCreate, KBUpdate

# type-hint imports — not constructed here; DI builds these via dependencies.py
from app.domain.services.kb_service import KBService
from app.infrastructure.db.models import KnowledgeBase


async def list_kbs(
    current_user: CurrentUser,
    service: KBService = Depends(get_kb_service),
) -> list[KnowledgeBase]:
    return await service.list_kbs(current_user.id)


async def create_kb(
    body: KBCreate,
    current_user: CurrentUser,
    service: KBService = Depends(get_kb_service),
) -> KnowledgeBase:
    try:
        return await service.create_kb(current_user.id, body)
    except KBLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)
        )


async def get_kb(
    kb_id: uuid.UUID,
    current_user: CurrentUser,
    service: KBService = Depends(get_kb_service),
) -> KnowledgeBase:
    try:
        return await service.get_kb(kb_id, current_user.id)
    except KBNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


async def update_kb(
    kb_id: uuid.UUID,
    body: KBUpdate,
    current_user: CurrentUser,
    service: KBService = Depends(get_kb_service),
) -> KnowledgeBase:
    try:
        return await service.update_kb(kb_id, current_user.id, body)
    except KBNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


async def delete_kb(
    kb_id: uuid.UUID,
    current_user: CurrentUser,
    service: KBService = Depends(get_kb_service),
) -> None:
    try:
        await service.delete_kb(kb_id, current_user.id)
    except KBNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
