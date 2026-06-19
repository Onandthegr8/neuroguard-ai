from typing import Literal, Optional
from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    phone: Optional[str] = None
    otp: Optional[str] = None
    provider: Optional[Literal["google", "apple"]] = None
    token: Optional[str] = None


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int = 900
    token_type: str = "Bearer"
    user: dict


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    expires_in: int = 900
