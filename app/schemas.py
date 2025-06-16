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
    industry: str

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
    scope: int    
    amount: float

class EmissionResponse(BaseModel):
    company: str
    month: str
    electricity: float
    gasoline: float
    natural_gas: float
    district_heating: float
    total_emission: float

class ReportInfoBase(BaseModel):
    company: str
    start_month: str
    end_month: str
    allowance: float




