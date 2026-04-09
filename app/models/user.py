from pydantic import BaseModel, Field


class User(BaseModel):
    student_id: str
    name: str
    password_hash: str
    scnu_account: str | None = None


class UserCreate(BaseModel):
    student_id: str = Field(..., min_length=1, max_length=32)
    name: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)
    scnu_account: str | None = Field(default=None, max_length=64)


class UserLogin(BaseModel):
    student_id: str = Field(..., min_length=1, max_length=32)
    password: str = Field(..., min_length=1, max_length=128)


class UserInfo(BaseModel):
    student_id: str
    name: str
    scnu_account: str | None = None
