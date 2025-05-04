from pydantic import BaseModel, EmailStr
from datetime import datetime

class User(BaseModel):
    id: int
    email: str

    class Config:
        orm_mode = True


class UserCreate(BaseModel):
    email: EmailStr
    password: str

class Emission(BaseModel):
    id: int
    user_id: int
    scope: int
    amount: float
    timestamp: datetime

    class Config:
        orm_mode = True

class EmissionCreate(BaseModel):
    user_id: int
    scope: int      # 1, 2 또는 3
    amount: float






