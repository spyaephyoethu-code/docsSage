from fastapi import APIRouter, status

# runtime imports
from app.api.controllers import source_controller
from app.domain.schemas.source import SourceResponse

router = APIRouter(
    prefix="/api/v1/knowledge-bases/{kb_id}/sources",
    tags=["sources"],
)

router.post("", response_model=SourceResponse, status_code=status.HTTP_202_ACCEPTED)(
    source_controller.create_source
)
router.get("", response_model=list[SourceResponse])(source_controller.list_sources)
router.get("/{source_id}", response_model=SourceResponse)(source_controller.get_source)
router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)(
    source_controller.delete_source
)
