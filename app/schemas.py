from pydantic import BaseModel, Field, EmailStr
from typing import Optional


class SubmissionRequest(BaseModel):
    code: str = Field(..., min_length=1, example="print('Hello World')")
    language: str = Field(..., example="python")


class UserCreate(BaseModel):
    name: str = Field(..., min_length=1, example="Alice")
    email: str = Field(..., example="alice@example.com")
    password: str = Field(..., min_length=6, example="secret123")


class LoginRequest(BaseModel):
    email: str = Field(..., example="alice@example.com")
    password: str = Field(..., example="secret123")