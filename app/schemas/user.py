from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=255)
    email: str | None = Field(default=None, min_length=3, max_length=254)
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=4, max_length=128)
    role: str = Field(default="user", min_length=1, max_length=30)
    status: str = Field(default="active", min_length=1, max_length=30)


class UserUpdate(BaseModel):
    username: str = Field(min_length=3, max_length=255)
    email: str | None = Field(default=None, min_length=3, max_length=254)
    display_name: str = Field(min_length=1, max_length=120)
    role: str = Field(min_length=1, max_length=30)
    status: str = Field(min_length=1, max_length=30)


class UserPasswordReset(BaseModel):
    password: str = Field(min_length=4, max_length=128)


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    id: int
    username: str
    email: str | None = None
    display_name: str
    role: str
    status: str
    last_login_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
