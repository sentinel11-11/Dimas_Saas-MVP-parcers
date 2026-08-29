"""
FastAPI веб-приложение для парсинга автомобилей
"""
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import asyncio
import json
from loguru import logger

from app.database.db import init_db, get_all_listings, delete_listing
from app.parsers.drom.drom_parser import DromParser
from app.parsers.drom.drom_detail_parser import DromDetailParser
from app.parsers.autoru.autoru_parser import AutoRuParser
from app.parsers.avito.avito_parser import AvitoParser
from app.core.normalizer import DataNormalizer
from app.core.market import MarketEngine
from app.core.market_analyzer import MarketAnalyzer
from app.models.car_listing import CarListing

app = FastAPI(title="Car Parser MVP", description="Парсинг и анализ автомобильных объявлений")

# Подключение статики и шаблонов
# Список всех марок автомобилей (расширенный)
ALL_BRANDS = [
    "audi", "bmw", "chevrolet", "chrysler", "citroen", "dodge", "fiat", "ford",
    "geely", "genesis", "gmc", "honda", "hyundai", "infiniti", "jaguar", "jeep",
    "kia", "land rover", "lexus", "mazda", "mercedes", "mini", "mitsubishi",
    "nissan", "opel", "peugeot", "porsche", "renault", "skoda", "subaru",
    "suzuki", "toyota", "volkswagen", "volvo", "lada", "gaz", "uaz",
    "chery", "haval", "geely", "exeed", "tank", "omoda", "jaecoo", "kowloon",
    "faaw", "dongfeng", "foton", "great wall", "lifan", "brilliance"
]

# Популярные модели для каждой марки
POPULAR_MODELS = {
    "bmw": ["1 серия", "2 серия", "3 серия", "4 серия", "5 серия", "6 серия", "7 серия", "8 серия", 
            "X1", "X2", "X3", "X4", "X5", "X6", "X7", "Z4", "i3", "i4", "iX"],
    "mercedes": ["A-Class", "B-Class", "C-Class", "CLA", "CLS", "E-Class", "G-Class", "GLA", "GLB", 
                 "GLC", "GLE", "GLS", "S-Class", "SL", "AMG GT"],
    "audi": ["A1", "A3", "A4", "A5", "A6", "A7", "A8", "Q2", "Q3", "Q4", "Q5", "Q7", "Q8", "TT", "e-tron"],
    "toyota": ["Camry", "Corolla", "RAV4", "Land Cruiser", "Highlander", "Prius", "Yaris", "Avalon"],
    "honda": ["Accord", "Civic", "CR-V", "HR-V", "Pilot", "Odyssey", "Fit"],
    "nissan": ["Almera", "Altima", "Juke", "Kashqai", "Leaf", "Maxima", "Murano", "Note", "Pathfinder", "Qashqai", "Terrano", "X-Trail"],
    "volkswagen": ["Golf", "Jetta", "Passat", "Polo", "Tiguan", "Touareg", "Arteon"],
    "ford": ["Fiesta", "Focus", "Fusion", "Kuga", "Mondeo", "Mustang", "Explorer", "F-150"],
    "hyundai": ["Accent", "Elantra", "Genesis", "Grandeur", "i30", "Santa Fe", "Sonata", "Tucson"],
    "kia": ["Ceed", "Cerato", "K5", "Mohave", "Optima", "Picanto", "Rio", "Sorento", "Sportage", "Stinger"],
    "lexus": ["ES", "GS", "IS", "LS", "LX", "NX", "RX", "UX"],
    "mazda": ["2", "3", "5", "6", "CX-3", "CX-5", "CX-7", "CX-9", "MX-5"],
    "subaru": ["Forester", "Impreza", "Legacy", "Outback", "WRX", "XV"],
    "mitsubishi": ["ASX", "Eclipse Cross", "L200", "Lancer", "Outlander", "Pajero"],
    "porsche": ["718", "911", "Cayenne", "Macan", "Panamera", "Taycan"],
    "volvo": ["S40", "S60", "S90", "V40", "V60", "V90", "XC40", "XC60", "XC90"],
    "lada": ["Granta", "Kalina", "Priora", "Vesta", "XRAY", "Niva", "Largus"],
    "gaz": ["Volga", "Gazelle", "Next"],
    "uaz": ["Patriot", "Hunter", "Pickup", "Cargo"]
}

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Глобальное хранилище результатов
parsing_results: Dict[str, List[Dict[str, Any]]] = {}


class SearchRequest(BaseModel):
    brand: str
    model: str
    sources: List[str] = ["drom", "avito", "autoru"]
    limit: int = 10


@app.on_event("startup")
async def startup_event():
    """Инициализация БД при запуске"""
    init_db()
    logger.info("Web application started")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Главная страница с формой поиска"""
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "title": "Поиск выгодных автомобилей",
            "brands": ALL_BRANDS,
            "models_json": json.dumps(POPULAR_MODELS),
            "custom_limit_enabled": True
        }
    )


@app.post("/search", response_class=HTMLResponse)
async def search_cars(
    request: Request,
    brand: str = Form(...),
    model: str = Form(...),
    sources: List[str] = Form(default=["drom"]),
    limit: int = Form(default=10)
):
    """Обработка поиска автомобилей"""
    logger.info(f"Search request: brand={brand}, model={model}, sources={sources}, limit={limit}")
    
    enriched = []
    errors = []
    
    # 1. Парсинг Drom
    if "drom" in sources:
        try:
            drom_parser = DromParser()
            drom_detail_parser = DromDetailParser()
            filters = {"brand": brand, "model": model}
            drom_ads = drom_parser.search(filters)
            logger.info(f"DROM FOUND: {len(drom_ads)}")
            
            for ad in drom_ads[:limit]:
                try:
                    details = drom_detail_parser.parse(ad["url"])
                    if details:
                        ad.update(details)
                    normalized = DataNormalizer.normalize(ad)
                    normalized["platform"] = "drom"
                    car = CarListing(**normalized)
                    enriched.append(car)
                except Exception as e:
                    logger.error(f"DROM DETAIL ERROR: {e}")
                    errors.append(f"Drom ошибка: {str(e)}")
        except Exception as e:
            logger.error(f"DROM SEARCH ERROR: {e}")
            errors.append(f"Drom поиск: {str(e)}")
    
    # 2. Парсинг Avito (с поддержкой прокси)
    if "avito" in sources:
        try:
            # Прокси передаются через конфигурацию или переменные окружения
            import os
            proxy_list_str = os.getenv("AVITO_PROXIES", "")
            avito_proxy_list = [p.strip() for p in proxy_list_str.split(",") if p.strip()] if proxy_list_str else None
            
            avito_parser = AvitoParser(proxy_list=avito_proxy_list)
            avito_ads = avito_parser.search({"brand": brand, "model": model, "limit": limit, "target_region": "rossiya"})
            logger.info(f"AVITO FOUND: {len(avito_ads)}")
            
            for ad in avito_ads:
                try:
                    normalized = DataNormalizer.normalize(ad)
                    normalized["platform"] = "avito"
                    if not normalized.get("url") or not normalized.get("title"):
                        continue
                    car = CarListing(**normalized)
                    enriched.append(car)
                except Exception as e:
                    logger.error(f"AVITO NORMALIZATION ERROR: {e}")
                    errors.append(f"Avito обработка: {str(e)}")
        except Exception as e:
            logger.error(f"AVITO SEARCH ERROR: {e}")
            errors.append(f"Avito поиск: {str(e)}")
    
    # 3. Парсинг Auto.ru (с поддержкой прокси)
    if "autoru" in sources:
        try:
            # Прокси передаются через конфигурацию или переменные окружения
            import os
            autoru_proxy_list_str = os.getenv("AUTORU_PROXIES", "")
            autoru_proxy_list = [p.strip() for p in autoru_proxy_list_str.split(",") if p.strip()] if autoru_proxy_list_str else None
            
            autoru_parser = AutoRuParser(headless=True, proxy_list=autoru_proxy_list)
            
            # Создаем задачу в текущем event loop
            autoru_task = asyncio.create_task(
                autoru_parser.search(
                    filters={"brand": brand, "model": model},
                    limit=limit
                )
            )
            autoru_cars = await autoru_task
            logger.info(f"AUTO.RU FOUND: {len(autoru_cars)}")
            
            for car_data in autoru_cars:
                try:
                    if isinstance(car_data, CarListing):
                        enriched.append(car_data)
                    else:
                        normalized = DataNormalizer.normalize(car_data)
                        normalized["platform"] = "autoru"
                        car = CarListing(**normalized)
                        enriched.append(car)
                except Exception as e:
                    logger.error(f"AUTORU NORMALIZATION ERROR: {e}")
                    errors.append(f"Auto.ru обработка: {str(e)}")
        except Exception as e:
            logger.error(f"AUTORU SEARCH ERROR: {e}")
            errors.append(f"Auto.ru поиск: {str(e)}")
    
    logger.info(f"TOTAL ENRICHED: {len(enriched)}")
    
    # Расчет скоринга
    if enriched:
        market = MarketEngine([x.model_dump() for x in enriched])
        
        for car in enriched:
            car.market_score = market.price_score(car.model_dump())
            car.market_price = MarketAnalyzer.calculate_market_price(
                [x.model_dump() for x in enriched], car
            )
            car.market_deviation = MarketAnalyzer.calculate_market_deviation(
                car.price, car.market_price
            )
            car.liquidity_score = MarketAnalyzer.calculate_liquidity_score(car)
            car.probability_good_deal = MarketAnalyzer.calculate_final_probability(car)
    
    # Сортировка по вероятности выгодной сделки
    enriched.sort(key=lambda x: x.probability_good_deal or 0, reverse=True)
    
    # Сохранение в БД и подготовку данных для отображения
    results_data = []
    for car in enriched:
        try:
            from app.database.db import save_listing
            save_listing(car)
        except Exception as e:
            logger.error(f"DB SAVE ERROR: {e}")
        
        results_data.append({
            "title": car.title,
            "price": car.price,
            "year": car.year,
            "mileage": car.mileage,
            "region": car.region,
            "url": car.url,
            "platform": car.platform,
            "image_url": car.image_url or "/static/images/no-car-image.png",
            "market_price": car.market_price,
            "market_deviation": car.market_deviation,
            "probability": car.probability_good_deal,
            "liquidity": car.liquidity_score,
            "badge_class": get_badge_class(car.probability_good_deal) if car.probability_good_deal else "bg-secondary"
        })
    
    # Сохранение результатов в глобальном хранилище
    session_key = f"{brand}_{model}"
    parsing_results[session_key] = results_data
    
    return templates.TemplateResponse(
        "results.html",
        {
            "request": request,
            "results": results_data,
            "brand": brand.capitalize(),
            "model": model.capitalize(),
            "total": len(results_data),
            "errors": errors,
            "sources_used": sources
        }
    )


def get_badge_class(probability: float) -> str:
    """Определение класса цвета бейджа на основе вероятности"""
    if probability >= 0.8:
        return "bg-success"
    elif probability >= 0.6:
        return "bg-primary"
    elif probability >= 0.4:
        return "bg-warning"
    else:
        return "bg-danger"


@app.get("/results/{brand}/{model}", response_class=HTMLResponse)
async def view_results(request: Request, brand: str, model: str):
    """Просмотр результатов поиска"""
    session_key = f"{brand}_{model}"
    results = parsing_results.get(session_key, [])
    
    if not results:
        # Попытка загрузить из БД
        try:
            db_listings = get_all_listings()
            results = []
            for listing in db_listings:
                if listing.brand and listing.brand.lower() == brand.lower():
                    results.append({
                        "title": listing.title,
                        "price": listing.price,
                        "year": listing.year,
                        "mileage": listing.mileage,
                        "region": listing.region,
                        "url": listing.url,
                        "platform": listing.source,
                        "market_price": listing.market_score,
                        "market_deviation": listing.final_score,
                        "probability": listing.final_score,
                        "liquidity": 0.5,
                        "badge_class": get_badge_class(listing.final_score) if listing.final_score else "bg-secondary"
                    })
        except Exception as e:
            logger.error(f"DB LOAD ERROR: {e}")
    
    return templates.TemplateResponse(
        "results.html",
        {
            "request": request,
            "results": results,
            "brand": brand.capitalize(),
            "model": model.capitalize(),
            "total": len(results),
            "errors": [],
            "sources_used": []
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
