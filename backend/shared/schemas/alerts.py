import uuid
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel


class AlertCreate(BaseModel):
    patient_id: uuid.UUID
    message: str
    severity: Literal["info", "warning", "critical"] = "info"
    send_to_patient: bool = False


class AlertResponse(BaseModel):
    id: uuid.UUID
    alert_type: str
    severity: str
    title: str
    body: str
    is_read: bool
    created_at: datetime
    delivered_at: Optional[datetime]
