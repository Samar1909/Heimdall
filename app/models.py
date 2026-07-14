from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, Float, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base

class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), server_default=func.now())

class State(Base):
    __tablename__ = "states"

    state_id: Mapped[str] = mapped_column(String(50), primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), primary_key=True, nullable=False)

class City(Base):
    __tablename__ = "cities"

    city_id: Mapped[str] = mapped_column(String(50), primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), primary_key=True, nullable=False)
    city_pop: Mapped[Optional[int]] = mapped_column(Integer)
    state_id: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("states.state_id"))

    state: Mapped[Optional["State"]] = relationship()

class User(Base):
    __tablename__ = 'users'

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    dob_year: Mapped[Optional[int]] = mapped_column(Integer)
    gender: Mapped[Optional[int]] = mapped_column(Integer)
    job: Mapped[Optional[str]] = mapped_column(String(100))
    city_id: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("cities.city_id"))
    lat: Mapped[Optional[float]] = mapped_column(Float)
    long: Mapped[Optional[float]] = mapped_column(Float)

    city: Mapped[Optional["City"]] = relationship()

class Merchant(Base):
    __tablename__ = "merchants"

    merchant_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(100))
    lat: Mapped[Optional[float]] = mapped_column(Float)
    long: Mapped[Optional[float]] = mapped_column(Float)

class Transaction(Base):
    __tablename__ = "transactions"

    transaction_id: Mapped[str] = mapped_column(String(100), primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.user_id"))
    merchant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("merchants.merchant_id"))
    amt: Mapped[Optional[float]] = mapped_column(Float)
    unix_time: Mapped[Optional[int]] = mapped_column(Integer)
    fraud_probability: Mapped[Optional[float]] = mapped_column(Float)
    status: Mapped[Optional[str]] = mapped_column(String(50))

