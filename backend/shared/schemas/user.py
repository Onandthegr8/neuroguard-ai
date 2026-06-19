import uuid
from typing import Literal, Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    age: Optional[int] = Field(None, ge=18, le=120)
    gender: Optional[str] = None
    family_history: bool = False
    risk_group: Literal["general", "high_risk"] = "general"


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    age: Optional[int]
    gender: Optional[str]
    risk_group: str
    family_history: bool
    created_at: datetime


class ConsentRequest(BaseModel):
    consent_type: Literal[
        "keystroke_collection", "sleep_data", "location",
        "research_use", "federated_learning", "biometric_data"
    ]
    version: str = Field(default="v1.0", max_length=10)
    granted: bool
    device_id: Optional[uuid.UUID] = None


class ConsentResponse(BaseModel):
    consent_id: uuid.UUID
    consent_type: str
    granted: bool
    granted_at: Optional[datetime]
