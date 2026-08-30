from dataclasses import dataclass, field
from typing import Optional
@dataclass
class AvitoListing:
    url: str
    title: str
    price: int = 0
    year: Optional[int] = None
    mileage: Optional[int] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    region: Optional[str] = None
    seller_type: Optional[str] = None
    description: Optional[str] = None
    external_id: Optional[str] = None
    photos: list[str] = field(default_factory=list)
    transmission: Optional[str] = None
    fuel: Optional[str] = None
    drive: Optional[str] = None
    body_type: Optional[str] = None
    engine_volume: Optional[float] = None
    horsepower: Optional[int] = None
    owners: Optional[int] = None
    source: str = "avito"
    def to_dict(self) -> dict:
        return self.__dict__.copy()
