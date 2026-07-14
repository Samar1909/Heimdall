import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, Response, Cookie
from typing import Annotated, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session

import auth
from ml_service import load_model, predict_fraud
from schemas import (
    TransactionPayload,
    UserBase,
    UserSignupRequest,
    UserLoginRequest,
    MerchantBase,
    MerchantSignupRequest,
    MerchantLoginRequest,
    SignupRequest,
    LoginRequest,
    AccountOut,
)
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

# ------ AUTH ENDPOINTS --------

@app.post("/auth/signup", response_model=AccountOut, status_code=201)
async def signup(payload: SignupRequest, db: db_dependency):
    if db.query(models.Account).filter(models.Account.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Account already exists")

    account = models.Account(
        id=str(uuid.uuid4()),
        email=payload.email,
        hashed_password=auth.hash_password(payload.password),
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account

@app.post("/auth/login", response_model=AccountOut)
async def login(payload: LoginRequest, response: Response, db: db_dependency):
    account = db.query(models.Account).filter(models.Account.email == payload.email.lower()).first()
    if not account or not auth.verify_password(payload.password, account.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    auth.issue_auth_cookies(response, account.id)
    return account

@app.post("/auth/refresh")
async def refresh(
    response: Response,
    db: db_dependency,
    refresh_token: Annotated[Optional[str], Cookie()] = None,
):
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Missing refresh token")

    payload = auth.decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")

    stored_account_id = auth.redis_client.get(f"refresh:{payload.get('jti')}")
    if not stored_account_id or stored_account_id != payload.get("sub"):
        raise HTTPException(status_code=401, detail="Refresh token revoked or invalid")

    account = db.query(models.Account).filter(models.Account.id == payload["sub"]).first()
    if not account:
        raise HTTPException(status_code=401, detail="Account not found")

    auth.redis_client.delete(f"refresh:{payload.get('jti')}")
    auth.issue_auth_cookies(response, account.id)
    return {"detail": "Token refreshed"}

@app.post("/auth/logout", dependencies=[Depends(auth.verify_csrf)])
async def logout(
    response: Response,
    refresh_token: Annotated[Optional[str], Cookie()] = None,
):
    if refresh_token:
        auth.revoke_refresh_token(refresh_token)
    auth.clear_auth_cookies(response)
    return {"detail": "Logged out"}

@app.get("/auth/me", response_model=AccountOut)
async def me(account: auth.current_account_dependency):
    return account

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

# --- PREDICTION ENDPOINT ---

@app.post("/predict")
async def predict(transaction: TransactionPayload):
    return await predict_fraud(transaction)