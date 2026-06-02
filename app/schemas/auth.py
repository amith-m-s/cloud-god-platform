from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = None
    tenant_id: str = "default"


class UserLogin(BaseModel):
    email: EmailStr
    password: str
    tenant_id: str = "default"


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str | None = None
    role: str
    is_active: bool

    model_config = {"from_attributes": True}
