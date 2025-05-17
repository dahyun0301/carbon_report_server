from pydantic import BaseModel, EmailStr
from datetime import datetime

class User(BaseModel):              #회원가입 응답 모델
    id: int
    email: str

    model_config = {
        "from_attributes": True
    }


class UserCreate(BaseModel):        #회원가입 요청 모델
    email: EmailStr
    password: str
    industry: str

class Emission(BaseModel):          # 탄소배출량 응답 모델
    id: int
    user_id: int
    scope: int
    amount: float
    timestamp: datetime

    model_config = {
        "from_attributes": True
    }

class EmissionCreate(BaseModel):    # 탄소배출량 생성 요청 모델
    user_id: int
    scope: int      # 1, 2 또는 3
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



