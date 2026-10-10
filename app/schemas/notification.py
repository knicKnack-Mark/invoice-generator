from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class NotificationOut(BaseModel):
    id: UUID
    type: str
    payload: dict
    read_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}