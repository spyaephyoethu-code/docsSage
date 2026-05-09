import uuid

from fastapi import Depends, HTTPException, status

# runtime imports
from app.core.dependencies import get_chat_service
from app.core.middleware.auth import CurrentUser
from app.domain.exceptions import (
    BudgetExceeded,
    ConversationNotFound,
    DailyLimitExceeded,
    KBNotFound,
)
from app.domain.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ConversationResponse,
    MessageResponse,
)

# type-hint imports
from app.domain.services.chat_service import ChatService


async def chat(
    kb_id: uuid.UUID,
    request: ChatRequest,
    current_user: CurrentUser,
    service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    try:
        return await service.chat(
            kb_id=kb_id,
            user_id=current_user.id,
            query=request.query,
            conversation_id=request.conversation_id,
        )
    except DailyLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)
        )
    except BudgetExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )
    except ConversationNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except KBNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


async def list_conversations(
    kb_id: uuid.UUID,
    current_user: CurrentUser,
    service: ChatService = Depends(get_chat_service),
) -> list[ConversationResponse]:
    convs = await service.list_conversations(kb_id, current_user.id)
    return [
        ConversationResponse(
            id=c.id,
            kb_id=c.kb_id,
            title=c.title,
            created_at=c.created_at.isoformat(),
        )
        for c in convs
    ]


async def get_messages(
    kb_id: uuid.UUID,
    conversation_id: uuid.UUID,
    current_user: CurrentUser,
    service: ChatService = Depends(get_chat_service),
) -> list[MessageResponse]:
    try:
        msgs = await service.get_messages(conversation_id, kb_id, current_user.id)
    except ConversationNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return [
        MessageResponse(
            id=m.id,
            role=m.role,
            content=m.content,
            citations=m.citations,
            created_at=m.created_at.isoformat(),
        )
        for m in msgs
    ]
