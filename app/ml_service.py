from fastapi import HTTPException
import pandas as pd
import xgboost as xgb
import time
from schemas import TransactionPayload

model = None

def load_model():
    global model
    print("Loading XGBoost model into memory...")
    model = xgb.XGBClassifier()
    model.load_model("artifacts/heimdall_fraud_model.json")
    print("Model loaded successfully!")

async def predict_fraud(transaction :TransactionPayload):
    if model is None:
        raise HTTPException(500, detail="Model is not loaded")

    start_time = time.time()

    try:
        input_data = pd.DataFrame([transaction.model_dump()])
        probabilities = model.predict_proba(input_data)
        fraud_probability = float(probabilities[0][1])
        
        status = "APPROVED"
        if fraud_probability > 0.80:
            status = "BLOCKED"
        elif fraud_probability > 0.50:
            status = "FLAGGED_FOR_REVIEW"
            
        inference_time_ms = round((time.time() - start_time) * 1000, 2)
        
        return {
            "transaction_status": status,
            "fraud_probability": round(fraud_probability, 4),
            "inference_time_ms": inference_time_ms
        }
    except Exception as e:
        raise HTTPException(500, detail = str(e))