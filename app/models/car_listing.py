from pydantic import BaseModel, Field
from typing import Optional, Literal

class CarSearchConfig(BaseModel):
    """Конфигурация поиска автомобиля пользователем"""
    brand: str = Field(..., description="Марка автомобиля")
    model: Optional[str] = Field(None, description="Модель автомобиля")
    
    # Диапазоны
    year_min: int = Field(2010, ge=1990, le=2026, description="Минимальный год выпуска")
    year_max: int = Field(2026, ge=1990, le=2026, description="Максимальный год выпуска")
    
    mileage_min: int = Field(0, ge=0, le=1000000, description="Минимальный пробег (км)")
    mileage_max: int = Field(300000, ge=0, le=1000000, description="Максимальный пробег (км)")
    
    owners_min: int = Field(1, ge=1, le=5, description="Мин кол-во владельцев")
    owners_max: int = Field(3, ge=1, le=5, description="Макс кол-во владельцев")
    
    # Параметры
    transmission: Optional[Literal["automatic", "manual", "robot", "variator"]] = Field(None, description="Коробка передач")
    fuel: Optional[Literal["petrol", "diesel", "electric", "hybrid", "gas"]] = Field(None, description="Тип топлива")
    drive: Optional[Literal["front", "rear", "four_wheel"]] = Field(None, description="Привод")
    body_type: Optional[str] = Field(None, description="Тип кузова")
    
    price_min: int = Field(0, ge=0, description="Мин цена")
    price_max: int = Field(100000000, ge=0, description="Макс цена")
    
    region: Optional[str] = Field(None, description="Регион поиска")

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
    
    # Поля для отчета
    search_config_applied: Optional[CarSearchConfig] = None
    deal_probability: str = "Unknown"
    
    # Псевдонимы для обратной совместимости
    @property
    def owners_count(self) -> Optional[int]:
        return self.owners
    
    model_config = {
        "extra": "allow"
    }