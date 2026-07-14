import json
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, Response, Cookie, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from typing import Annotated, Optional, List
from sqlalchemy import func
from sqlalchemy.orm import Session

import auth
from ml_service import load_model, predict_fraud, redis_client
from schemas import (
    TransactionPayload,
    TransactionBase,
    UserBase,
    UserSignupRequest,
    UserLoginRequest,
    MerchantBase,
    MerchantSignupRequest,
    MerchantLoginRequest,
)
from database import get_db, engine, SessionLocal
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

# Allow the local static frontend (e.g. VSCode Live Server) to talk to the API with cookies.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5500", "http://localhost:5500"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db_dependency = Annotated[Session, Depends(get_db)]

# ------ AUTH ENDPOINTS --------

@app.post("/auth/logout", dependencies=[Depends(auth.verify_csrf)])
async def logout(
    response: Response,
    refresh_token: Annotated[Optional[str], Cookie()] = None,
):
    if refresh_token:
        auth.revoke_refresh_token(refresh_token)
    auth.clear_auth_cookies(response)
    return {"detail": "Logged out"}

# ------ USER AUTH ENDPOINTS --------

@app.post("/users/signup", response_model=UserBase, status_code=201)
async def user_signup(payload: UserSignupRequest, db: db_dependency):
    if db.query(models.User).filter(models.User.username == payload.username).first():
        raise HTTPException(status_code=400, detail="Username already taken")

    city = db.query(models.City).filter(func.lower(models.City.name) == payload.city_name.strip().lower()).first()
    if not city:
        raise HTTPException(status_code=400, detail=f"Unknown city: {payload.city_name}")

    user = models.User(
        username=payload.username,
        hashed_password=auth.hash_password(payload.password),
        dob_year=payload.dob_year,
        gender=payload.gender,
        job=payload.job,
        city_id=city.city_id,
        lat=payload.lat,
        long=payload.long,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@app.post("/users/login", response_model=UserBase)
async def user_login(payload: UserLoginRequest, response: Response, db: db_dependency):
    user = db.query(models.User).filter(models.User.username == payload.username).first()
    if not user or not auth.verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    auth.issue_auth_cookies(response, str(user.user_id), role="user")
    return user

@app.get("/users/me", response_model=UserBase)
async def user_me(current_user: auth.current_user_dependency):
    return current_user

# ------ MERCHANT AUTH ENDPOINTS --------

@app.post("/merchants/signup", response_model=MerchantBase, status_code=201)
async def merchant_signup(payload: MerchantSignupRequest, db: db_dependency):
    if db.query(models.Merchant).filter(models.Merchant.username == payload.username).first():
        raise HTTPException(status_code=400, detail="Username already taken")

    merchant = models.Merchant(
        username=payload.username,
        hashed_password=auth.hash_password(payload.password),
        category=payload.category,
        lat=payload.lat,
        long=payload.long,
    )
    db.add(merchant)
    db.commit()
    db.refresh(merchant)
    return merchant

@app.post("/merchants/login", response_model=MerchantBase)
async def merchant_login(payload: MerchantLoginRequest, response: Response, db: db_dependency):
    merchant = db.query(models.Merchant).filter(models.Merchant.username == payload.username).first()
    if not merchant or not auth.verify_password(payload.password, merchant.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    auth.issue_auth_cookies(response, str(merchant.merchant_id), role="merchant")
    return merchant

@app.get("/merchants/me", response_model=MerchantBase)
async def merchant_me(current_merchant: auth.current_merchant_dependency):
    return current_merchant

# --- PREDICTION ENDPOINT ---

@app.post("/predict")
async def predict(transaction: TransactionPayload):
    return await predict_fraud(transaction)

# --- TRANSACTION ENDPOINT ---

def async_save_ledger(tx_id: str, payload: TransactionPayload, prediction_result: dict) -> None:
    db = SessionLocal()
    try:
        transaction = models.Transaction(
            transaction_id=tx_id,
            user_id=payload.user_id,
            merchant_id=payload.merchant_id,
            amt=payload.amt,
            unix_time=payload.unix_time,
            fraud_probability=prediction_result.get("fraud_probability"),
            status=prediction_result.get("transaction_status"),
        )
        db.add(transaction)
        db.commit()
    finally:
        db.close()

    user_raw = redis_client.get(f"user:{payload.user_id}")
    if user_raw:
        user_data = json.loads(user_raw)
        prior_count = user_data.get("card_tx_count", 0)
        prior_avg = user_data.get("card_avg_amt_prior", 0.0)
        new_count = prior_count + 1
        user_data["card_tx_count"] = new_count
        user_data["card_avg_amt_prior"] = ((prior_avg * prior_count) + payload.amt) / new_count
        redis_client.set(f"user:{payload.user_id}", json.dumps(user_data))

@app.post("/transaction")
async def process_transaction(
    payload: TransactionPayload,
    background_tasks: BackgroundTasks,
    db: db_dependency,
    current_entity: auth.protected_route,
):
    prediction_result = await predict_fraud(payload)
    tx_id = f"tx_{uuid.uuid4().hex[:12]}"

    background_tasks.add_task(
        async_save_ledger,
        tx_id=tx_id,
        payload=payload,
        prediction_result=prediction_result,
    )

    return {
        "transaction_id": tx_id,
        **prediction_result,
    }

@app.get("/transactions/mine", response_model=List[TransactionBase])
async def my_transactions(db: db_dependency, current_entity: auth.current_entity_dependency):
    query = db.query(models.Transaction)
    if isinstance(current_entity, models.User):
        query = query.filter(models.Transaction.user_id == current_entity.user_id)
    else:
        query = query.filter(models.Transaction.merchant_id == current_entity.merchant_id)
    return query.order_by(models.Transaction.unix_time.desc()).limit(50).all()