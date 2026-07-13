# 🛡️ Heimdall: Real-Time Fraud Engine

**Heimdall** is an ultra-low latency, high-throughput machine learning pipeline designed to detect fraudulent financial transactions in real-time.

Built for enterprise-scale performance, Heimdall bridges the gap between complex data science and robust backend engineering. It utilizes an in-memory **Redis Feature Store** to reconstruct user histories instantly and integrates **Explainable AI (XAI)** to provide mathematical transparency for every blocked transaction, ensuring compliance with financial regulations.

---

## ✨ Key Features

- ⚡ **Sub-15ms Inference Engine:** Model artifacts are loaded directly into RAM at server startup via FastAPI, bypassing disk I/O bottlenecks to achieve blazing-fast prediction times.
- 🧠 **Explainable AI (XAI) with SHAP:** "Black-box" predictions are unboxed in real-time. For every transaction, a globally initialized SHAP `TreeExplainer` extracts the top 3 risk factors (log-odds feature contributions) that triggered the fraud alert.
- 💾 **Redis Feature Store:** Simulates a production environment where payment gateways only send minimal data (`Card_ID`, `Amount`). Heimdall instantly queries a Redis cache to append historical rolling features (V1–V28) before passing the vector to the ML model.
- ⚖️ **Imbalance-Optimized XGBoost:** Trained on highly skewed financial datasets (99.9% legitimate traffic). The model abandons raw accuracy in favor of optimizing the Area Under the Precision-Recall Curve (AUCPR) using calculated positive scaling weights.
- 🐳 **Production-Ready & Stress-Tested:** Fully containerized using Docker and stress-tested using Locust to handle high-concurrency traffic spikes without latency degradation.

---

## 🏗️ Architecture Flow

1. **Incoming Request:** Payment terminal sends `{card_id, amount}` to Heimdall API.
2. **State Retrieval:** FastAPI queries Redis to fetch the historical profile (V1–V28) for the specific `card_id`.
3. **Feature Engineering:** The historical data and current amount are merged into a complete 30-feature vector.
4. **ML Inference:** The XGBoost model processes the vector and outputs a fraud probability (0.0 to 1.0).
5. **XAI Extraction:** If the transaction exceeds risk thresholds, SHAP calculates exactly which features skewed the score.
6. **Response:** API immediately returns the decision (`APPROVED`, `FLAGGED_FOR_REVIEW`, or `BLOCKED`) alongside the SHAP explanations.

---

## 📁 Directory Structure

```
HEIMDALL/
│
├── app/                        # FastAPI Application & ML Service Logic
│   ├── main.py                 # API Routes & Server Config
│   ├── ml_service.py           # XGBoost and SHAP inference engine
│   └── schemas.py              # Pydantic data validation models
│
├── artifacts/                  # Serialized ML Models
│   └── heimdall_fraud_model.json
│
├── notebooks/                  # Data Science & Model Training
│   └── model.ipynb
│
├── scripts/                    # Utilities
│   └── populate_redis.py       # Script to load CSV features into Redis
│
├── data/                       # Raw Datasets (Ignored in Git)
│   └── creditcard.csv
│
├── docker-compose.yml          # Container orchestration (FastAPI + Redis)
├── Dockerfile                  # API Image build instructions
└── requirements.txt            # Python dependencies
```

---

## 🚀 API Usage

**Endpoint:** `POST /predict`

**Request Payload:**

```json
{
  "card_id": "usr_987654321",
  "amount": 1450.75
}
```

**Response Payload:**

```json
{
  "transaction_status": "BLOCKED",
  "fraud_probability": 0.9412,
  "inference_time_ms": 11.45,
  "top_risk_factors": {
    "V4": 3.1415,
    "Amount": 1.294,
    "V11": 0.812
  }
}
```

---

## 🛠️ Tech Stack

| Layer | Technologies |
|---|---|
| **Backend** | Python 3.12, FastAPI, Uvicorn, Pydantic |
| **Machine Learning** | XGBoost, Scikit-Learn, Pandas, NumPy |
| **Explainability** | SHAP (SHapley Additive exPlanations) |
| **Database/Caching** | Redis |
| **DevOps** | Docker, Docker Compose, Locust (Load Testing) |

---

## ⚙️ Local Setup (Docker)

1. Clone the repository.
2. Ensure Docker Desktop is running.
3. Start the pipeline:

   ```bash
   docker-compose up --build -d
   ```

4. Populate the Redis Feature Store with mock user data:

   ```bash
   python scripts/populate_redis.py
   ```

5. Access the interactive API documentation at [http://localhost:8000/docs](http://localhost:8000/docs).
