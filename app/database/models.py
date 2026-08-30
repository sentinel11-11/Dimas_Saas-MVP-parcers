from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Text
)

from sqlalchemy.orm import declarative_base


Base = declarative_base()


class CarListingORM(Base):

    __tablename__ = "car_listings"

    id = Column(Integer, primary_key=True)

    title = Column(String)

    price = Column(Integer)

    year = Column(Integer)

    mileage = Column(Integer)

    owners = Column(Integer)

    engine_volume = Column(Float)

    horsepower = Column(Integer)

    transmission = Column(String)

    drive = Column(String)

    body_type = Column(String)

    fuel_type = Column(String)

    color = Column(String)

    region = Column(String)

    accidents = Column(Integer)

    pts = Column(String)

    market_score = Column(Float)

    final_score = Column(Float)

    url = Column(Text, unique=True)

    source = Column(String)


class SavedSearchORM(Base):
    __tablename__ = "saved_searches"

    id = Column(Integer, primary_key=True)
    email = Column(String, default="")
    brand = Column(String)
    model = Column(String)
    params_json = Column(Text)
    last_min_price = Column(Integer, default=0)
    last_count = Column(Integer, default=0)
    created_at = Column(String)