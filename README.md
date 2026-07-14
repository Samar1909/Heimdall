# 🛡️ Heimdall: Real-Time Fraud Engineering Pipeline

**Heimdall** is an ultra-low latency, high-throughput machine learning pipeline designed to detect fraudulent financial transactions in real-time.

Unlike standard ML deployments that expect clients to provide fully pre-processed, anonymized data, Heimdall acts as a true **real-time feature engine**. It receives minimal transactional data (user, merchant, amount, time), instantly reconstructs behavioral history using a Redis Feature Store, computes complex geographical and temporal metrics on the fly, and evaluates the complete feature vector against an imbalance-optimized XGBoost model — all behind a cookie/JWT-authenticated API with separate signup/login flows for cardholders (Users) and Merchants, plus a small dashboard frontend.

---

## ✨ Key Features

- ⚙️ **Real-Time Feature Engineering:** Computes complex metrics (e.g., Haversine distances between user and merchant, time-based aggregations, spend ratios) in-memory during the request lifecycle. This ensures the ML model has rich, interpretable data without burdening the client payment gateway.

- 💾 **Dual-Database Architecture:**
  - **MySQL (The Ledger):** A durable, relational source of truth managed via SQLAlchemy ORM, storing users, merchants, cities/states, and transaction logs.
  - **Redis (Feature Store):** Maintains rolling, aggregated user and merchant state (e.g., historical transaction counts, average spend amounts) for sub-millisecond retrieval, plus refresh-token session storage.

- 🔐 **Role-Based Cookie Auth:** Users and Merchants each have their own signup/login endpoints, backed by Argon2 password hashing and JWT access/refresh tokens delivered as `httpOnly` cookies. A double-submit CSRF cookie protects all state-changing requests.

- ⚡ **Asynchronous State Updates:** Utilizes `BackgroundTasks` to write the transaction to the MySQL ledger and update Redis aggregates *after* the client receives the fraud decision, keeping the response path fast.

- 🧠 **Explainable AI (XAI) with SHAP:** "Black-box" predictions are unboxed in real-time. A globally initialized SHAP `TreeExplainer` extracts the top risk factors that triggered a fraud alert, ensuring compliance with financial transparency regulations.

- ⚖️ **Imbalance-Optimized XGBoost:** Trained on highly skewed financial datasets. The model abandons raw accuracy in favor of optimizing the Area Under the Precision-Recall Curve (AUCPR) using calculated positive scaling weights.

- 🖥️ **Vanilla JS Dashboard:** A dependency-free frontend with role-aware signup/login and separate User (simulate a swipe + personal transaction history) and Merchant (incoming transactions + stats) dashboards.

---

## 🏗️ Architecture Flow

1. **Auth:** A User or Merchant signs up (`/users/signup` or `/merchants/signup`) and logs in (`/users/login` or `/merchants/login`). The API issues `access_token`/`refresh_token` (httpOnly) and `csrf_token` cookies, embedding a `role` claim (`user` or `merchant`) in the JWT.
2. **Incoming Transaction:** An authenticated User or Merchant calls `POST /transaction` with `{ "user_id": 1042, "merchant_id": 89, "amt": 55.00, "unix_time": 1690000000 }`, presenting the JWT cookie and the `X-CSRF-Token` header.
3. **State Retrieval:** The backend queries Redis for the historical profile and aggregated stats of both the User and the Merchant (falling back to MySQL, and a City/State join for the user's home city population, on a cache miss).
4. **Dynamic Computation:** The backend computes the remaining features on the fly:
   - Time derivatives (hour, day of week, month).
   - Haversine geographic distance between user and merchant coordinates.
   - Behavioral ratios (e.g., `amt / card_avg_amt_prior`).
   - One-hot encoding for merchant categories.
5. **ML Inference:** The assembled feature vector is passed to the XGBoost model to calculate the fraud probability, and SHAP extracts the top contributing risk factors.
6. **Immediate Response + Async Ledger Update:** The API returns the decision (with a generated `transaction_id`) right away. In the background, SQLAlchemy writes the transaction to MySQL and Redis increments the rolling user statistics.
7. **Dashboards:** `GET /transactions/mine` lets the logged-in User or Merchant pull their own transaction history for the frontend dashboard.

---

## 📁 Directory Structure

```
HEIMDALL/
│
├── app/                                 # FastAPI Application & ML Service Logic
│   ├── __init__.py
│   ├── auth.py                          # Password hashing, JWT issuance/verification, CSRF, auth dependencies
│   ├── database.py                      # SQLAlchemy engine/session configuration
│   ├── main.py                          # API routes, background tasks, CORS, server config
│   ├── ml_service.py                    # XGBoost + SHAP inference engine, feature engineering
│   ├── models.py                        # ORM tables (Account, User, Merchant, City, State, Transaction)
│   ├── schemas.py                       # Pydantic request/response schemas
│   ├── redis_server.py                  # Redis client connection
│   ├── populate_cities.py               # Seeds the states/cities reference tables
│   └── .env                             # Local secrets (JWT_SECRET_KEY) — not committed
│
├── frontend/                            # Static vanilla JS dashboard (no build step)
│   ├── index.html                       # Auth screen + User/Merchant dashboard views
│   ├── app.js                           # Session handling, API calls, dashboard rendering
│   └── style.css                        # Styling
│
├── artifacts/                           # Serialized ML Models
│   └── heimdall_fraud_model.json        # Exported XGBoost model artifact
│
├── data/                                # Raw Datasets (Ignored in Git)
│   ├── creditcardTest.csv               # Test dataset
│   └── creditcardTrain.csv              # Training dataset
│
├── notebooks/                           # Data Science & Model Training
│   ├── model.ipynb                      # Jupyter notebook for EDA and training
│   └── MODEL_NOTES.md                   # Research and modeling documentation
│
├── README.md                            # Project documentation
└── requirements.txt                     # Python dependencies
```

---

## 🗃️ Data Model

| Table | Purpose |
|---|---|
| `users` | `user_id` (auto-increment PK), unique `username` + `hashed_password`, `dob_year`, `gender`, `job`, `city_id` (FK), `lat`/`long` |
| `merchants` | `merchant_id` (auto-increment PK), unique `username` + `hashed_password`, `category`, `lat`/`long` |
| `cities` | `city_id`, `name`, `city_pop`, `state_id` (FK) — seeded via `populate_cities.py` |
| `states` | `state_id`, `name` |
| `transactions` | `transaction_id`, `user_id` (FK), `merchant_id` (FK), `amt`, `unix_time`, `fraud_probability`, `status` |

A `users.city_id` must reference a row already present in `cities` — run `populate_cities.py` before creating any users (see Setup below).

---

## 🔑 Authentication & Sessions

- **Passwords** are hashed with Argon2 (`argon2-cffi`).
- **Tokens:** short-lived JWT access tokens (15 min) + longer-lived refresh tokens (7 days), each carrying a `role` claim of `"user"` or `"merchant"`. Refresh-token JTIs are tracked in Redis so they can be revoked on logout.
- **Cookies:** `access_token` and `refresh_token` are `httpOnly`; `csrf_token` is readable by JS so the frontend can echo it back.
- **CSRF:** all state-changing requests (signup is exempt, but transactions and logout are not) require the `X-CSRF-Token` header to match the `csrf_token` cookie (double-submit pattern). Read-only endpoints (`/users/me`, `/merchants/me`, `/transactions/mine`) only require a valid JWT, not CSRF.
- `JWT_SECRET_KEY` is loaded from `app/.env` (via `python-dotenv`). If unset, a random ephemeral key is generated and a warning is printed — fine for local testing, but tokens won't survive a restart.

---

## 🚀 API Reference

| Method | Route | Auth | Description |
|---|---|---|---|
| `POST` | `/users/signup` | — | Create a User account (resolves `city_name` → `city_id`) |
| `POST` | `/users/login` | — | Log in as a User; issues auth cookies |
| `GET`  | `/users/me` | JWT (user) | Current user's profile |
| `POST` | `/merchants/signup` | — | Create a Merchant account |
| `POST` | `/merchants/login` | — | Log in as a Merchant; issues auth cookies |
| `GET`  | `/merchants/me` | JWT (merchant) | Current merchant's profile |
| `POST` | `/auth/logout` | JWT + CSRF | Revokes the refresh token and clears cookies |
| `POST` | `/transaction` | JWT + CSRF (user or merchant) | Runs fraud inference, logs the transaction, updates Redis aggregates |
| `GET`  | `/transactions/mine` | JWT (user or merchant) | Last 50 transactions for the authenticated user/merchant |
| `POST` | `/predict` | — | Runs fraud inference only, without persisting a ledger entry |

### Example: `POST /transaction`

**Request** (cookies + `X-CSRF-Token` header from a prior login):
```json
{
  "user_id": 1042,
  "merchant_id": 89,
  "amt": 1450.75,
  "unix_time": 1691234567
}
```

**Response:**
```json
{
  "transaction_id": "tx_abc123def456",
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

## 🖥️ Frontend Dashboard

`frontend/` is a static, dependency-free site (plain HTML/CSS/JS):

- **Auth screen:** tabbed Login / Sign Up, with a User/Merchant role toggle on each.
- **User dashboard:** profile card, a "simulate a swipe" form that hits `POST /transaction` and shows the live fraud decision, and a personal transaction history table.
- **Merchant dashboard:** profile card, a stats row (transaction count, flagged/blocked count, total volume), and an incoming-transactions table.

Serve it with any static server on port `5500` (e.g. VSCode's Live Server extension, or `python3 -m http.server 5500` from inside `frontend/`) — that origin is what's whitelisted in the API's CORS config.

---

## 🛠️ Setup

**Prerequisites:** Python 3.12, a running MySQL server, a running Redis server.

```bash
# 1. Create and activate a virtualenv, then install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Configure secrets
echo "JWT_SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(64))')" > app/.env

# 3. Point database.py at your MySQL instance (URL_DATABASE), then seed reference data
cd app
python3 populate_cities.py

# 4. Run the API
uvicorn main:app --reload
```

Then serve `frontend/` on port `5500` as described above and open it in a browser.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.12, FastAPI, Uvicorn, Pydantic |
| **Auth** | PyJWT, Argon2 (`argon2-cffi`), httpOnly cookies, double-submit CSRF |
| **Database / ORM** | MySQL (via PyMySQL), SQLAlchemy |
| **Feature Store / Sessions** | Redis |
| **Machine Learning** | XGBoost, Scikit-Learn, Pandas, NumPy |
| **Explainability** | SHAP (SHapley Additive exPlanations) |
| **Frontend** | Vanilla HTML/CSS/JS (no build step) |
