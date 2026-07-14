from database import SessionLocal
from models import City, State

CITIES = [
    # (city_id, name, city_pop, state_id, state_name)
    ("delhi", "Delhi", 16787941, "delhi", "Delhi"),
    ("mumbai", "Mumbai", 12442373, "maharashtra", "Maharashtra"),
    ("bengaluru", "Bengaluru", 8443675, "karnataka", "Karnataka"),
    ("hyderabad", "Hyderabad", 6809970, "telangana", "Telangana"),
    ("chennai", "Chennai", 4646732, "tamil_nadu", "Tamil Nadu"),
    ("kolkata", "Kolkata", 4496694, "west_bengal", "West Bengal"),
    ("ahmedabad", "Ahmedabad", 5570585, "gujarat", "Gujarat"),
    ("pune", "Pune", 3124458, "maharashtra", "Maharashtra"),
    ("surat", "Surat", 4467797, "gujarat", "Gujarat"),
    ("jaipur", "Jaipur", 3073350, "rajasthan", "Rajasthan"),
    ("ghaziabad", "Ghaziabad", 1729000, "uttar_pradesh", "Uttar Pradesh"),
]


def populate_cities() -> None:
    db = SessionLocal()
    try:
        states = {(state_id, state_name) for _, _, _, state_id, state_name in CITIES}
        for state_id, state_name in states:
            if not db.query(State).filter(State.state_id == state_id).first():
                db.add(State(state_id=state_id, name=state_name))
        db.commit()

        for city_id, name, city_pop, state_id, _ in CITIES:
            if not db.query(City).filter(City.city_id == city_id).first():
                db.add(City(city_id=city_id, name=name, city_pop=city_pop, state_id=state_id))
        db.commit()

        print(f"Populated {len(states)} states and {len(CITIES)} cities.")
    finally:
        db.close()


if __name__ == "__main__":
    populate_cities()
