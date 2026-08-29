from pydantic import BaseModel
from typing import Optional

class CarListing(BaseModel):
    url: str
    title: str
    platform: str
    brand: Optional[str] = None
    model: Optional[str] = None
    price: int
    year: int
    mileage: int = 0
    engine_volume: float = 0
    horsepower: int = 0
    transmission: str = ""
    drive: Optional[str] = None
    body_type: Optional[str] = None
    owners: Optional[int] = None
    accidents: Optional[int] = None
    pts: Optional[str] = None
    region: str = ""
    market_score: float = 0
    market_price: float = 0
    liquidity_score: float = 0
    probability_good_deal: float = 0
    data_confidence: float = 0
    image_url: Optional[str] = None
    model_config = {
        "extra": "allow"
    }