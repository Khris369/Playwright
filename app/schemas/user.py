from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=4, max_length=128)
    role: str = Field(default="user", min_length=1, max_length=30)
    status: str = Field(default="active", min_length=1, max_length=30)


class UserUpdate(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    display_name: str = Field(min_length=1, max_length=120)
    role: str = Field(min_length=1, max_length=30)
    status: str = Field(min_length=1, max_length=30)


class UserPasswordReset(BaseModel):
    password: str = Field(min_length=4, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    id: int
    email: str
    display_name: str
    role: str
    status: str
    last_login_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
