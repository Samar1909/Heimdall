from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional

# --- Auth ---

class SignupRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        if "@" not in value or "." not in value.split("@")[-1]:
            raise ValueError("Invalid email address")
        return value.lower()

class LoginRequest(BaseModel):
    email: str
    password: str

class AccountOut(BaseModel):
    id: str
    email: str

    model_config = ConfigDict(from_attributes=True)

class StateBase(BaseModel):
    state_id: str
    name: str

    model_config = ConfigDict(from_attributes=True)

class CityBase(BaseModel):
    city_id: str
    name: str
    city_pop: int
    state_id: str

    model_config = ConfigDict(from_attributes=True)

class UserBase(BaseModel):
    user_id: int
    username: str
    dob_year: int
    gender: int
    job: str
    city_id: str
    lat: float
    long: float

    model_config = ConfigDict(from_attributes=True)

class UserSignupRequest(BaseModel):
    username: str
    password: str = Field(min_length=8)
    dob_year: int
    gender: int
    job: str
    city_name: str
    lat: float
    long: float

class UserLoginRequest(BaseModel):
    username: str
    password: str

class MerchantBase(BaseModel):
    merchant_id: int
    username: str
    category: str
    lat: float
    long: float

    model_config = ConfigDict(from_attributes=True)

class MerchantSignupRequest(BaseModel):
    username: str
    password: str = Field(min_length=8)
    category: str
    lat: float
    long: float

class MerchantLoginRequest(BaseModel):
    username: str
    password: str

class TransactionBase(BaseModel):
    transaction_id: str
    user_id: int
    merchant_id: int
    amt: float
    unix_time: int
    fraud_probability: Optional[float] = None
    status: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

# --- API Request Payload ---
# This represents the minimal data sent by the payment gateway to the /predict endpoint
class TransactionPayload(BaseModel):
    user_id: int
    merchant_id: int
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
