"""
Тестовый скрипт для проверки парсера Auto.ru
Запускать локально на машине с установленным Playwright:
    playwright install chromium
    python test_autoru_parser.py
"""

from app.parsers.autoru.autoru_parser import AutoRuParser
from loguru import logger
import sys


def main():
    logger.info("=" * 50)
    logger.info("AUTO.RU PARSER TEST")
    logger.info("=" * 50)
    
    # Параметры поиска
    filters = {
        "brand": "bmw",
        "model": "x5",
        # "region": "moscow",  # можно добавить регион
        # "price_from": 3000000,
        # "price_to": 10000000,
        # "year_from": 2015,
        # "year_to": 2025,
    }
    
    logger.info(f"Search filters: {filters}")
    
    # Создаем парсер (headless=False для отладки, чтобы видеть браузер)
    parser = AutoRuParser(headless=True)
    
    try:
        # Запускаем поиск
        results = parser.search_sync(filters)
        
        logger.info("=" * 50)
        logger.info(f"FOUND {len(results)} LISTINGS")
        logger.info("=" * 50)
        
        for i, car in enumerate(results[:5], 1):  # Показываем первые 5
            logger.info(f"\n[{i}] {car.get('title', 'N/A')}")
            logger.info(f"    Price: {car.get('price', 0):,} ₽")
            logger.info(f"    Year: {car.get('year', 'N/A')}")
            logger.info(f"    Mileage: {car.get('mileage', 'N/A')} km")
            logger.info(f"    Region: {car.get('region', 'N/A')}")
            logger.info(f"    URL: {car.get('url', 'N/A')}")
            logger.info(f"    Platform: {car.get('platform', 'N/A')}")
            
        if len(results) > 5:
            logger.info(f"\n... and {len(results) - 5} more listings")
            
        logger.info("\n" + "=" * 50)
        logger.info("TEST COMPLETED SUCCESSFULLY")
        logger.info("=" * 50)
        
    except Exception as e:
        logger.error(f"TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
        
    finally:
        # Закрываем браузер
        import asyncio
        asyncio.run(parser.close())


if __name__ == "__main__":
    main()
