from datetime import datetime

from pydantic import BaseModel

from model.document import DocumentStatus


class DocumentResponse(BaseModel):
    id: int
    organization_id: int
    filename: str
    uploaded_by: int
    status: DocumentStatus
    error_message: str | None
    uploaded_at: datetime | None

    model_config = {"from_attributes": True}
