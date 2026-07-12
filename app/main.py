from fastapi import FastAPI, HTTPException
from ml_service import load_model, predict_fraud
from schemas import TransactionPayload

app = FastAPI(
    title="Heimdall Real-Time Fraud Engine",
    description="High-throughput transaction fraud detection pipeline."
)

load_model()

@app.post("/predict")
async def predict(transaction: TransactionPayload):
    return await predict_fraud(transaction)

