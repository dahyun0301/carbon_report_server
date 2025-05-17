from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from .db import Base
import datetime

class User(Base):
    __tablename__ = "users"
    id       = Column(Integer, primary_key=True, index=True)
    email    = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    industry = Column(String, nullable=True) 

    emissions = relationship("Emission", back_populates="owner")

class Emission(Base):
    __tablename__ = "emissions"
    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id"))
    scope      = Column(Integer, nullable=False)  # 1,2,3
    amount     = Column(Float, nullable=False)
    timestamp  = Column(DateTime, default=datetime.datetime.astimezone)

    owner      = relationship("User", back_populates="emissions")
    
class EmissionRecord(Base):
    __tablename__ = "emission_records"

    id = Column(Integer, primary_key=True, index=True)
    company = Column(String, nullable=False)
    month = Column(String, index=True)
    electricity = Column(Float)
    gasoline = Column(Float)
    natural_gas = Column(Float)
    district_heating = Column(Float)
    total_emission = Column(Float)

class ReportInfo(Base):
    __tablename__ = "report_info"
    id = Column(Integer, primary_key=True, index=True)
    company = Column(String)
    start_month = Column(String)
    end_month = Column(String)
    allowance = Column(Float)