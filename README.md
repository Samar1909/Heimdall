# 🛡️ Heimdall: Real-Time Fraud Engineering Pipeline

**Heimdall** is an ultra-low latency, high-throughput machine learning pipeline designed to detect fraudulent financial transactions in real-time.

Unlike standard ML deployments that expect clients to provide fully pre-processed, anonymized data, Heimdall acts as a true **real-time feature engine**. It receives minimal transactional data (user, merchant, amount, time), instantly reconstructs behavioral history using a Redis Feature Store, computes complex geographical and temporal metrics on the fly, and evaluates the complete feature vector against an imbalance-optimized XGBoost model.

---

## ✨ Key Features

- ⚙️ **Real-Time Feature Engineering:** Computes complex metrics (e.g., Haversine distances between user and merchant, time-based aggregations, spend ratios) in-memory during the request lifecycle. This ensures the ML model has rich, interpretable data without burdening the client payment gateway.

- 💾 **Dual-Database Architecture:**
  - **MySQL (The Ledger):** A durable, relational source of truth managed via SQLAlchemy ORM, storing raw users, merchants, and transactions logs.
  - **Redis (Feature Store):** Maintains rolling, aggregated user and merchant state (e.g., historical transaction counts, average spend amounts) for sub-millisecond retrieval.

- ⚡ **Asynchronous State Updates:** Utilizes background tasks to update Redis aggregates and write raw transaction logs to the MySQL ledger *after* the client receives the prediction, guaranteeing strict sub-20ms response times.

- 🧠 **Explainable AI (XAI) with SHAP:** "Black-box" predictions are unboxed in real-time. A globally initialized SHAP `TreeExplainer` extracts the top risk factors that triggered a fraud alert, ensuring compliance with financial transparency regulations.

- ⚖️ **Imbalance-Optimized XGBoost:** Trained on highly skewed financial datasets. The model abandons raw accuracy in favor of optimizing the Area Under the Precision-Recall Curve (AUCPR) using calculated positive scaling weights.

---

## 🏗️ Architecture Flow

1. **Incoming Request:** The payment gateway sends a minimal payload to the API: `{ "user_id": "usr_123", "merchant_id": "mer_89", "amt": 55.00, "unix_time": 1690000000 }`.
2. **State Retrieval:** FastAPI queries Redis to fetch the historical profile and aggregated stats for both the User and the Merchant.
3. **Dynamic Computation:** The backend dynamically calculates missing features:
   - Time derivatives (hour, day of week, month).
   - Haversine geographic distance between user and merchant coordinates.
   - Behavioral ratios (e.g., `amt / card_avg_amt_prior`).
   - One-hot encoding for merchant categories.
4. **ML Inference:** The assembled multi-feature vector is passed to the XGBoost model to calculate the fraud probability.
5. **XAI Extraction:** If flagged, SHAP calculates exactly which interpretable features (e.g., `distance_km`, `amt_to_avg_ratio`) skewed the score.
6. **Async Ledger Update:** The API returns the decision immediately. In the background, SQLAlchemy writes the transaction to the MySQL database, and Redis increments the rolling user/merchant statistics.

---

## 📁 Directory Structure

```
HEIMDALL/
│
├── app/                                # FastAPI Application & ML Service Logic
│   ├── __init__.py
│   ├── database.py                     # SQLAlchemy configuration and connection pooling
│   ├── main.py                         # API Routes, Background Tasks, & Server Config
│   ├── ml_service.py                   # XGBoost and SHAP inference engine, Feature Eng.
│   ├── models.py                       # ORM Database Tables (Users, Merchants, TXs)
│   └── redis_server.py                 # Redis connection and cache management
│
├── artifacts/                          # Serialized ML Models
│   └── heimdall_fraud_model.json       # Exported XGBoost model artifact
│
├── data/                               # Raw Datasets (Ignored in Git)
│   ├── creditcardTest.csv              # Test dataset
│   └── creditcardTrain.csv             # Training dataset
│
├── notebooks/                          # Data Science & Model Training
│   ├── model.ipynb                     # Jupyter notebook for EDA and training
│   └── MODEL_NOTES.md                  # Research and modeling documentation
│
├── README.md                           # Project documentation
└── requirements.txt                    # Python dependencies
```

---

## 🚀 API Usage

**Endpoint:** `POST /predict`

**Client Request Payload (Minimal):**

```json
{
  "user_id": "usr_987654321",
  "merchant_id": "mer_54321",
  "amt": 1450.75,
  "unix_time": 1691234567
}
```

**Response Payload:**

```json
{
  "transaction_status": "BLOCKED",
  "fraud_probability": 0.9412,
  "inference_time_ms": 14.45,
  "top_risk_factors": {
    "amt_to_avg_ratio": 3.1415,
    "distance_km": 1.294,
    "category_travel": 0.812
  }
}
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.12, FastAPI, Uvicorn, Pydantic |
| **Database / ORM** | MySQL, SQLAlchemy |
| **Feature Store (Cache)** | Redis |
| **Machine Learning** | XGBoost, Scikit-Learn, Pandas, NumPy |
| **Explainability** | SHAP (SHapley Additive exPlanations) |