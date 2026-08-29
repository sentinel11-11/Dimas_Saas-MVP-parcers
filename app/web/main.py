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
            "brands": ["bmw", "mercedes", "audi", "toyota", "honda", "nissan", "volkswagen", "ford", "hyundai", "kia"]
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
    
    # 2. Парсинг Avito
    if "avito" in sources:
        try:
            avito_parser = AvitoParser()
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
    
    # 3. Парсинг Auto.ru
    if "autoru" in sources:
        try:
            autoru_parser = AutoRuParser(headless=True)
            
            async def run_autoru():
                return await autoru_parser.search(
                    filters={"brand": brand, "model": model},
                    limit=limit
                )
            
            autoru_cars = asyncio.run(run_autoru())
            logger.info(f"AUTO.RU FOUND: {len(autoru_cars)}")
            enriched.extend(autoru_cars)
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
