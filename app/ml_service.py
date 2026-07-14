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

model = None
explainer = None

CATEGORIES = [
    "entertainment", "food_dining", "gas_transport", "grocery_net",
    "grocery_pos", "health_fitness", "home", "kids_pets", "misc_net",
    "misc_pos", "personal_care", "shopping_net", "shopping_pos", "travel",
]

MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "artifacts", "heimdall_fraud_model.json")

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
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == transaction.user_id).first()
        if user is None:
            raise HTTPException(404, detail=f"User {transaction.user_id} not found")

        merchant = db.query(Merchant).filter(Merchant.merchant_id == transaction.merchant_id).first()
        if merchant is None:
            raise HTTPException(404, detail=f"Merchant {transaction.merchant_id} not found")

        tx_time = datetime.fromtimestamp(transaction.unix_time, tz=timezone.utc)
        age = float(tx_time.year - cast(int, user.dob_year))

        distance_km = _haversine_km(user.lat, user.long, merchant.lat, merchant.long)

        category_flags = {f"category_{cat}": 0 for cat in CATEGORIES}
        category_key = f"category_{merchant.category}"
        if category_key in category_flags:
            category_flags[category_key] = 1

        prior_txns = (
            db.query(Transaction)
            .filter(
                Transaction.user_id == transaction.user_id,
                Transaction.unix_time < transaction.unix_time,
            )
            .all()
        )
        card_tx_count = len(prior_txns)
        card_avg_amt_prior = (
            cast(float, sum(t.amt for t in prior_txns)) / card_tx_count if card_tx_count > 0 else 0.0
        )
        amt_to_avg_ratio = (
            transaction.amt / card_avg_amt_prior if card_avg_amt_prior > 0 else 0.0
        )

        total_txn_count = db.query(func.count(Transaction.transaction_id)).scalar() or 0
        if total_txn_count > 0:
            merchant_freq = (
                db.query(func.count(Transaction.transaction_id))
                .filter(Transaction.merchant_id == transaction.merchant_id)
                .scalar()
                / total_txn_count
            )
            job_freq = (
                db.query(func.count(Transaction.transaction_id))
                .join(User, Transaction.user_id == User.user_id)
                .filter(User.job == user.job)
                .scalar()
                / total_txn_count
            )
            state_freq = (
                db.query(func.count(Transaction.transaction_id))
                .join(User, Transaction.user_id == User.user_id)
                .filter(User.state == user.state)
                .scalar()
                / total_txn_count
            )
        else:
            merchant_freq = job_freq = state_freq = 0.0

        model_input = TransactionModelBase(
            amt=transaction.amt,
            gender=cast(int, user.gender),
            city_pop=cast(int, user.city_pop),
            unix_time=transaction.unix_time,
            age=age,
            hour=tx_time.hour,
            day_of_week=tx_time.weekday(),
            month=tx_time.month,
            distance_km=distance_km,
            card_tx_count=card_tx_count,
            card_avg_amt_prior=card_avg_amt_prior,
            amt_to_avg_ratio=amt_to_avg_ratio,
            merchant_freq=merchant_freq,
            job_freq=job_freq,
            state_freq=state_freq,
            **category_flags,
        )

        return pd.DataFrame([model_input.model_dump()])
    finally:
        db.close()


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