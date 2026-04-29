import uuid

from fastapi import BackgroundTasks, Depends, HTTPException, status

# runtime imports
from app.core.dependencies import get_kb_service, get_source_service
from app.core.middleware.auth import CurrentUser
from app.domain.exceptions import KBNotFound, SourceLimitExceeded, SourceNotFound
from app.domain.schemas.source import SourceCreate
from app.infrastructure.ingestion.pipeline import run_ingestion_task

# type-hint imports
from app.domain.services.source_service import SourceService
from app.domain.services.kb_service import KBService
from app.infrastructure.db.models import Source


async def create_source(
    kb_id: uuid.UUID,
    body: SourceCreate,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser,
    kb_service: KBService = Depends(get_kb_service),
    source_service: SourceService = Depends(get_source_service),
) -> Source:
    try:
        await kb_service.get_kb(kb_id, current_user.id)
        source = await source_service.create_source(kb_id, body.type, body.url)
    except KBNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except SourceLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc))
    background_tasks.add_task(run_ingestion_task, source.id, current_user.id, kb_id)
    return source


async def list_sources(
    kb_id: uuid.UUID,
    current_user: CurrentUser,
    kb_service: KBService = Depends(get_kb_service),
    source_service: SourceService = Depends(get_source_service),
) -> list[Source]:
    try:
        await kb_service.get_kb(kb_id, current_user.id)
    except KBNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return await source_service.list_sources(kb_id)


async def get_source(
    kb_id: uuid.UUID,
    source_id: uuid.UUID,
    current_user: CurrentUser,
    kb_service: KBService = Depends(get_kb_service),
    source_service: SourceService = Depends(get_source_service),
) -> Source:
    try:
        await kb_service.get_kb(kb_id, current_user.id)
        return await source_service.get_source(source_id, kb_id)
    except KBNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except SourceNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


async def delete_source(
    kb_id: uuid.UUID,
    source_id: uuid.UUID,
    current_user: CurrentUser,
    kb_service: KBService = Depends(get_kb_service),
    source_service: SourceService = Depends(get_source_service),
) -> None:
    try:
        await kb_service.get_kb(kb_id, current_user.id)
        await source_service.delete_source(source_id, kb_id)
    except KBNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except SourceNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
