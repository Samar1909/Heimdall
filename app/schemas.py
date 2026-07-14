from pydantic import BaseModel


class TransactionPayload(BaseModel):
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
