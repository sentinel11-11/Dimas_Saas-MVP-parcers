from dataclasses import dataclass
from typing import Optional


@dataclass
class Car:

    title: str

    price: Optional[int] = None
    year: Optional[int] = None
    mileage: Optional[int] = None

    brand: Optional[str] = None
    model: Optional[str] = None
    
    engine_volume: Optional[float] = None
    horsepower: Optional[int] = None

    transmission: Optional[str] = None
    drive: Optional[str] = None
    body_type: Optional[str] = None

    owners: Optional[int] = None
    vin: Optional[str] = None

    accidents: Optional[int] = None
    pts: Optional[str] = None

    region: Optional[str] = None

    url: Optional[str] = None
    source: Optional[str] = None

    market_score: Optional[float] = None
    final_score: Optional[float] = None
    liquidity_score: float = 0.0

    data_confidence: float = 0.0