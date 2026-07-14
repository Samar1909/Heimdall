from sqlalchemy import Column, Integer, String, Float, ForeignKey
from database import Base

class User(Base):
    __tablename__ = 'users'
    
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

