from pydantic import BaseModel
from sqlalchemy import Boolean, Column, Integer, String, Float, ForeignKey
from database import Base

class User(Base):
    __tablename = 'users'
    
    user_id = Column(String(50), primary_key=True, index=True)
    dob_year = Column(Integer)
    gender = Column(Integer)
    city_pop = Column(Integer)
    job = Column(String(100))
    state = Column(String(50))
    lat = Column(Float)
    long = Column(Float)
    
class Merchant(Base):
    __tablename__ = "merchants"

    merchant_id = Column(String(50), primary_key=True, index=True)
    category = Column(String(100))
    lat = Column(Float)
    long = Column(Float)
    
class Transaction(Base):
    __tablename__ = "transactions"

    transaction_id = Column(String(100), primary_key=True, index=True)
    user_id = Column(String(50), ForeignKey("users.user_id"))
    merchant_id = Column(String(50), ForeignKey("merchants.merchant_id"))
    amt = Column(Float)
    unix_time = Column(Integer)
    fraud_probability = Column(Float)
    status = Column(String(50))

class TransactionPayload(BaseModel):
    amt: float
    gender: int
    city_pop: int
    unix_time: int
    age: float
    hour: int
    day_of_week: int
    month: int
    distance_km: float
    category_entertainment: int
    category_food_dining: int
    category_gas_transport: int
    category_grocery_net: int
    category_grocery_pos: int
    category_health_fitness: int
    category_home: int
    category_kids_pets: int
    category_misc_net: int
    category_misc_pos: int
    category_personal_care: int
    category_shopping_net: int
    category_shopping_pos: int
    category_travel: int
    card_tx_count: int
    card_avg_amt_prior: float
    amt_to_avg_ratio: float
    merchant_freq: float
    job_freq: float
    state_freq: float
