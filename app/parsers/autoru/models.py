"""
Модели данных для парсера Auto.ru
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class AutoRuCardData(BaseModel):
    """Модель данных карточки автомобиля с страницы поиска"""
    
    url: str = Field(..., description="URL объявления")
    title: Optional[str] = Field(None, description="Заголовок объявления")
    
    class Config:
        arbitrary_types_allowed = True


class AutoRuDetailData(BaseModel):
    """Модель данных детальной страницы автомобиля"""
    
    url: str = Field(..., description="URL объявления")
    title: Optional[str] = Field(None, description="Заголовок объявления")
    price: Optional[int] = Field(None, description="Цена в рублях")
    year: Optional[int] = Field(None, description="Год выпуска")
    mileage: Optional[int] = Field(None, description="Пробег в км")
    region: Optional[str] = Field(None, description="Регион продажи")
    brand: Optional[str] = Field(None, description="Марка автомобиля")
    model: Optional[str] = Field(None, description="Модель автомобиля")
    body_type: Optional[str] = Field(None, description="Тип кузова")
    drive: Optional[str] = Field(None, description="Привод")
    owners: Optional[int] = Field(None, description="Количество владельцев")
    accidents: Optional[int] = Field(None, description="Количество ДТП")
    pts: Optional[str] = Field(None, description="Тип ПТС")
    engine_volume: Optional[float] = Field(None, description="Объем двигателя в литрах")
    horsepower: Optional[int] = Field(None, description="Мощность двигателя в л.с.")
    transmission: Optional[str] = Field(None, description="Тип КПП")
    fuel: Optional[str] = Field(None, description="Тип топлива")
    image_url: Optional[str] = Field(None, description="URL изображения")
    
    class Config:
        arbitrary_types_allowed = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертация в словарь"""
        return self.model_dump(exclude_none=True)
