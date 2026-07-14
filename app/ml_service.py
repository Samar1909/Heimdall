from typing import cast
from fastapi import HTTPException
import pandas as pd
import xgboost as xgb
import time
import os
from datetime import datetime, timezone
from math import radians, sin, cos, sqrt, atan2
from sqlalchemy import func
from database import SessionLocal
from models import User, Merchant, Transaction
from schemas import TransactionPayload, TransactionModelBase
import shap
import redis
import json

model = None
explainer = None

CATEGORIES = [
    "entertainment", "food_dining", "gas_transport", "grocery_net",
    "grocery_pos", "health_fitness", "home", "kids_pets", "misc_net",
    "misc_pos", "personal_care", "shopping_net", "shopping_pos", "travel",
]

MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "artifacts", "heimdall_fraud_model.json")
redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

def load_model():
    global model, explainer
    print("Loading XGBoost model into memory...")
    model = xgb.XGBClassifier()
    model.load_model(MODEL_PATH)
    print("Model loaded successfully!")
    
    print("Initializing SHAP explainer...")
    explainer = shap.TreeExplainer(model)
    print("SHAP explainer ready!")

def _haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def createTransactionObjectForModel(transaction: TransactionPayload) -> pd.DataFrame:
    user_raw = redis_client.get(f"user:{transaction.user_id}")
    merchant_raw = redis_client.get(f"merchant:{transaction.merchant_id}")
    
    user_data = None
    if user_raw:
        user_data = json.loads(user_raw)
    else:
        db = SessionLocal()
        try:
            db_user = db.query(User).filter(User.user_id == transaction.user_id).first()
            if not db_user:
                raise HTTPException(404, detail=f"User {transaction.user_id} not found in system")
            
            print(f"Cache miss for User {transaction.user_id}. Generating baseline profile.")
            user_data = {
                "dob_year": db_user.dob_year,
                "gender": db_user.gender,
                "city_pop": db_user.city_pop,
                "job": db_user.job,
                "state": db_user.state,
                "lat": db_user.lat,
                "long": db_user.long,
                "card_tx_count": 0,
                "card_avg_amt_prior": 0.0,
                "job_freq": 0.0,
                "state_freq": 0.0
            }
            redis_client.set(f"user:{transaction.user_id}", json.dumps(user_data))
        finally:
            db.close()

    merchant_data = None
    if merchant_raw:
        merchant_data = json.loads(merchant_raw)
    else:
        db = SessionLocal()
        try:
            db_merchant = db.query(Merchant).filter(Merchant.merchant_id == transaction.merchant_id).first()
            if not db_merchant:
                raise HTTPException(404, detail=f"Merchant {transaction.merchant_id} not found in system")
            
            print(f"Cache miss for Merchant {transaction.merchant_id}. Generating baseline profile.")
            merchant_data = {
                "category": db_merchant.category,
                "lat": db_merchant.lat,
                "long": db_merchant.long,
                "merchant_freq": 0.0
            }
            redis_client.set(f"merchant:{transaction.merchant_id}", json.dumps(merchant_data))
        finally:
            db.close()

    tx_time = datetime.fromtimestamp(transaction.unix_time, tz=timezone.utc)
    age = float(tx_time.year - user_data["dob_year"])

    distance_km = _haversine_km(
        user_data["lat"], user_data["long"], 
        merchant_data["lat"], merchant_data["long"]
    )

    category_flags = {f"category_{cat}": 0 for cat in CATEGORIES}
    category_key = f"category_{merchant_data['category']}"
    if category_key in category_flags:
        category_flags[category_key] = 1

    card_tx_count = user_data["card_tx_count"]
    card_avg_amt_prior = user_data["card_avg_amt_prior"]
    
    amt_to_avg_ratio = (
        transaction.amt / card_avg_amt_prior if card_avg_amt_prior > 0 else 0.0
    )

    model_input = TransactionModelBase(
        amt=transaction.amt,
        gender=user_data["gender"],
        city_pop=user_data["city_pop"],
        unix_time=transaction.unix_time,
        age=age,
        hour=tx_time.hour,
        day_of_week=tx_time.weekday(),
        month=tx_time.month,
        distance_km=distance_km,
        card_tx_count=card_tx_count,
        card_avg_amt_prior=card_avg_amt_prior,
        amt_to_avg_ratio=amt_to_avg_ratio,
        merchant_freq=merchant_data["merchant_freq"],
        job_freq=user_data["job_freq"],
        state_freq=user_data["state_freq"],
        **category_flags,
    )

    return pd.DataFrame([model_input.model_dump()])

async def predict_fraud(transaction: TransactionPayload):
    if model is None or explainer is None:
        raise HTTPException(500, detail="Model or explainer is not loaded")

    start_time = time.time()

    try:
        input_data = createTransactionObjectForModel(transaction)
        probabilities = model.predict_proba(input_data)
        fraud_probability = float(probabilities[0][1])
        
        shap_values = explainer.shap_values(input_data)
        
        feature_contributions = dict(zip(input_data.columns, shap_values[0]))
        
        top_risk_features = sorted(
            [(feat, val) for feat, val in feature_contributions.items() if val > 0], 
            key=lambda x: x[1], 
            reverse=True
        )[:3] 
        
        explanations = {feat: round(float(val), 4) for feat, val in top_risk_features}
        
        status = "APPROVED"
        if fraud_probability > 0.80:
            status = "BLOCKED"
        elif fraud_probability > 0.50:
            status = "FLAGGED_FOR_REVIEW"
            
        inference_time_ms = round((time.time() - start_time) * 1000, 2)
        
        return {
            "transaction_status": status,
            "fraud_probability": round(fraud_probability, 4),
            "inference_time_ms": inference_time_ms,
            "top_risk_factors": explanations
        }
    except Exception as e:
        raise HTTPException(500, detail=str(e))