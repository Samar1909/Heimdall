from fastapi import HTTPException
import pandas as pd
import xgboost as xgb
import time
from schemas import TransactionPayload
import shap

model = None
explainer = None

def load_model():
    global model, explainer
    print("Loading XGBoost model into memory...")
    model = xgb.XGBClassifier()
    model.load_model("../artifacts/heimdall_fraud_model.json")
    print("Model loaded successfully!")
    
    print("Initializing SHAP explainer...")
    explainer = shap.TreeExplainer(model)
    print("SHAP explainer ready!")

async def predict_fraud(transaction: TransactionPayload):
    if model is None or explainer is None:
        raise HTTPException(500, detail="Model or explainer is not loaded")

    start_time = time.time()

    try:
        input_data = pd.DataFrame([transaction.model_dump()])
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