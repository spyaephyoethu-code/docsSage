from fastapi import APIRouter, status
from fastapi.responses import Response

# runtime imports
from app.api.controllers import kb_controller
from app.domain.schemas.kb import KBResponse

router = APIRouter(prefix="/api/v1/knowledge-bases", tags=["knowledge-bases"])

router.get("", response_model=list[KBResponse])(kb_controller.list_kbs)
router.post("", response_model=KBResponse, status_code=status.HTTP_201_CREATED)(
    kb_controller.create_kb
)
router.get("/{kb_id}", response_model=KBResponse)(kb_controller.get_kb)
router.patch("/{kb_id}", response_model=KBResponse)(kb_controller.update_kb)
router.delete(
    "/{kb_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response
)(kb_controller.delete_kb)
