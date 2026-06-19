import uuid
from datetime import datetime
from pydantic import BaseModel


class ReportResponse(BaseModel):
    report_id: uuid.UUID
    report_type: str
    period_start: str
    period_end: str
    download_url: str
    expires_at: datetime
    file_size_bytes: int
