from fastapi import APIRouter

# runtime imports
from app.api.controllers import chat_controller
from app.domain.schemas.chat import ChatResponse, ConversationResponse, MessageResponse

router = APIRouter(prefix="/api/v1/knowledge-bases", tags=["chat"])

router.post("/{kb_id}/chat", response_model=ChatResponse)(chat_controller.chat)
router.get("/{kb_id}/conversations", response_model=list[ConversationResponse])(
    chat_controller.list_conversations
)
router.get(
    "/{kb_id}/conversations/{conversation_id}/messages",
    response_model=list[MessageResponse],
)(chat_controller.get_messages)
