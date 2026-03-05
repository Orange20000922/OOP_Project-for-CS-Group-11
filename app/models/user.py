from pydantic import BaseModel


class User(BaseModel):
    student_id: str
    name: str
    password_hash: str


class UserCreate(BaseModel):
    student_id: str
    name: str
    password: str


class UserLogin(BaseModel):
    student_id: str
    password: str


class UserInfo(BaseModel):
    student_id: str
    name: str
