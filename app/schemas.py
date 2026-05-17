from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Any


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


class ProblemCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1)
    difficulty: str = Field(..., example="Easy")
    test_cases: List[Any] = Field(...)


class ProblemUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    difficulty: Optional[str] = None
    test_cases: Optional[List[Any]] = None