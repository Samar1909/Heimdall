from pydantic import BaseModel

from pydantic import BaseModel, ConfigDict
from typing import Optional

class UserBase(BaseModel):
    user_id: str
    dob_year: int
    gender: int
    city_pop: int
    job: str
    state: str
    lat: float
    long: float

    model_config = ConfigDict(from_attributes=True)

class MerchantBase(BaseModel):
    merchant_id: str
    category: str
    lat: float
    long: float

    model_config = ConfigDict(from_attributes=True)

class TransactionBase(BaseModel):
    transaction_id: str
    user_id: str
    merchant_id: str
    amt: float
    unix_time: int
    fraud_probability: Optional[float] = None
    status: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

# --- API Request Payload ---
# This represents the minimal data sent by the payment gateway to the /predict endpoint
class TransactionPayload(BaseModel):
    user_id: str
    merchant_id: str
    amt: float
    unix_time: int
    

class TransactionModelBase(BaseModel):
    amt: float
    gender: int
    city_pop: int
    unix_time: int
    age: float
    hour: int
    day_of_week: int
    month: int
    distance_km: float
    category_entertainment: int
    category_food_dining: int
    category_gas_transport: int
    category_grocery_net: int
    category_grocery_pos: int
    category_health_fitness: int
    category_home: int
    category_kids_pets: int
    category_misc_net: int
    category_misc_pos: int
    category_personal_care: int
    category_shopping_net: int
    category_shopping_pos: int
    category_travel: int
    card_tx_count: int
    card_avg_amt_prior: float
    amt_to_avg_ratio: float
    merchant_freq: float
    job_freq: float
    state_freq: float
