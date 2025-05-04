from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from .db import Base
import datetime

class User(Base):
    __tablename__ = "users"
    id       = Column(Integer, primary_key=True, index=True)
    email    = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)

class Emission(Base):
    __tablename__ = "emissions"
    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id"))
    scope      = Column(Integer, nullable=False)  # 1,2,3
    amount     = Column(Float, nullable=False)
    timestamp  = Column(DateTime, default=datetime.datetime.astimezone)

    owner      = relationship("User", back_populates="emissions")

User.emissions = relationship("Emission", back_populates="owner")
