import asyncio
from app.config import config

from app.database.db import (
    init_db,
    save_listing
)
from app.parsers.drom.drom_parser import DromParser
from app.parsers.drom.drom_detail_parser import DromDetailParser
from app.parsers.autoru.autoru_parser import AutoRuParser
from app.parsers.avito.avito_parser import AvitoParser
from app.core.normalizer import DataNormalizer
from app.core.market import MarketEngine
from app.core.market_analyzer import MarketAnalyzer
from app.core.logger import setup_logger
from app.models.car_listing import CarListing
logger = setup_logger()

async def parse_drom_ads(detail_parser, url):
    """Асинхронная обработка одного объявления Drom."""
    try:
        details = await detail_parser.parse_async(url)
        if details:
            details["platform"] = "drom"
            return details
    except Exception as e:
        logger.error(f"DROM DETAIL ERROR ({url}): {e}")
    return None

async def parse_autoru_ads(parser, limit=10):
    """Асинхронный парсинг Auto.ru."""
    try:
        cars = await parser.search(
            filters={"brand": config.BRAND, "model": config.MODEL},
            limit=limit
        )
        logger.info(f"AUTORU FOUND: {len(cars)}")
        return cars
    except Exception as e:
        logger.error(f"AUTORU SEARCH ERROR: {e}")
        return []

def run_analysis():
    init_db()
    
    # 1. Парсинг Drom (синхронный, пока что)
    drom_parser = DromParser()
    drom_detail_parser = DromDetailParser()
    
    filters = {
        "brand": config.BRAND,
        "model": config.MODEL
    }
    drom_ads = drom_parser.search(filters)
    logger.info(f"DROM FOUND ADS: {len(drom_ads)}")
    
    enriched = []
    
    # Детальный парсинг Drom
    for ad in drom_ads:
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

    # 2. Парсинг Avito
    if config.AVITO_ENABLED:
        logger.info("Starting Avito parsing...")
        try:
            avito_ads = AvitoParser().search({"brand": config.BRAND, "model": config.MODEL, "limit": 20, "target_region": "rossiya"})
            logger.info(f"AVITO FOUND ADS: {len(avito_ads)}")
            for ad in avito_ads:
                try:
                    normalized=DataNormalizer.normalize(ad); normalized["platform"]="avito"
                    if not normalized.get("url") or not normalized.get("title"): continue
                    car=CarListing(**normalized); enriched.append(car)
                except Exception as e: logger.error(f"AVITO NORMALIZATION ERROR: {e}")
        except Exception as e:
            logger.error(f"AVITO SEARCH ERROR: {e}")

    # 2. Парсинг Auto.ru (асинхронный)
    logger.info("Starting Auto.ru parsing...")
    autoru_parser = AutoRuParser()
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    autoru_cars = loop.run_until_complete(parse_autoru_ads(autoru_parser, limit=10))
    enriched.extend(autoru_cars)
    
    logger.info(f"TOTAL ENRICHED CARS: {len(enriched)}")
    if not enriched:
        logger.warning(
            "NO VALID CARS"
        )
        return
    market = MarketEngine(
        [x.model_dump() for x in enriched]
    )

    for car in enriched:
        car.market_score = (
            market.price_score(
                car.dict()
            )
        )

        car.market_price = (
            MarketAnalyzer.calculate_market_price(
                [x.model_dump() for x in enriched],
                car
            )
        )
        car.market_deviation = (
            MarketAnalyzer.calculate_market_deviation(
                car.price,
                car.market_price
            )
        )
        car.liquidity_score = (
            MarketAnalyzer.calculate_liquidity_score(
                car
            )
        )
        car.probability_good_deal = (
            MarketAnalyzer.calculate_final_probability(
                car
            )
        )
        save_listing(car)
    enriched.sort(
        key=lambda x: x.probability_good_deal,
        reverse=True
    )
    logger.info("TOP DEALS READY")
    for car in enriched[:10]:
        logger.info(

            f"[{car.probability_good_deal}] "
            f"{car.title} | "
            f"{car.price} ₽ | "
            f"market={car.market_price} ₽ | "
            f"dev={car.market_deviation} | "
            f"liq={car.liquidity_score} | "
            f"{car.region}"
        )

def main():
    run_analysis()
if __name__ == "__main__":
    main()