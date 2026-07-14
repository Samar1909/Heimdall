from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends
from typing import Annotated
from sqlalchemy.orm import Session

from ml_service import load_model, predict_fraud
from schemas import TransactionPayload, UserBase, MerchantBase
from database import get_db, engine
import models

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting Heimdall API...")
    models.Base.metadata.create_all(bind=engine)
    load_model()
    yield
    print("Shutting down Heimdall API...")

app = FastAPI(
    title="Heimdall Real-Time Fraud Engine",
    description="High-throughput transaction fraud detection pipeline.",
    lifespan=lifespan
)

db_dependency = Annotated[Session, Depends(get_db)]

# ------ Create ENDPOINTS --------

@app.post("/users", response_model=UserBase)
async def create_user(user: UserBase, db: db_dependency):
    if db.query(models.User).filter(models.User.user_id == user.user_id).first():
        raise HTTPException(status_code=400, detail="User already exists")
    
    db_user = models.User(**user.model_dump())
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.post("/merchants", response_model=MerchantBase)
async def create_merchant(merchant: MerchantBase, db: db_dependency):
    if db.query(models.Merchant).filter(models.Merchant.merchant_id == merchant.merchant_id).first():
        raise HTTPException(status_code=400, detail="Merchant already exists")
    
    db_merchant = models.Merchant(**merchant.model_dump())
    db.add(db_merchant)
    db.commit()
    db.refresh(db_merchant)
    return db_merchant

# --- PREDICTION ENDPOINT ---

@app.post("/predict")
async def predict(transaction: TransactionPayload):
    return await predict_fraud(transaction)