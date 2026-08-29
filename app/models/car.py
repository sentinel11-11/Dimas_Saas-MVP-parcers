from dataclasses import dataclass
from typing import Optional


@dataclass
class Car:

    title: str

    price: Optional[int] = None
    year: Optional[int] = None
    mileage: Optional[int] = None

    engine_volume: Optional[float] = None
    horsepower: Optional[int] = None

    transmission: Optional[str] = None
    drive: Optional[str] = None

    owners: Optional[int] = None
    vin: Optional[str] = None

    accidents: Optional[int] = None
    pts: Optional[str] = None

    region: Optional[str] = None

    url: Optional[str] = None
    source: Optional[str] = None

    market_score: Optional[float] = None
    final_score: Optional[float] = None

    data_confidence: float = 0.0