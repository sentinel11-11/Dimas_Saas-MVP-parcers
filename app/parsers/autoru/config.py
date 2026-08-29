"""
Конфигурация парсера Auto.ru
"""

import os
from typing import List, Dict, Any


class AutoRuConfig:
    """Конфигурация для парсера Auto.ru"""
    
    BASE_URL = "https://auto.ru"
    SEARCH_URL = "https://auto.ru/cars/sale/"
    
    # Прокси конфигурация (из переменных окружения)
    PROXY_LIST: List[str] = [p.strip() for p in os.getenv("AUTORU_PROXIES", "").split(",") if p.strip()] if os.getenv("AUTORU_PROXIES") else None
    
    # Расширенный список User-Agent для ротации
    USER_AGENTS: List[str] = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    ]
    
    # Селекторы для поиска объявлений
    LISTING_SELECTORS: List[str] = [
        'div[class*="ListingItem"]',
        'a[href*="/cars/sale/offer/"]',
        'section[class*="Listing"]',
        'article[class*="card"]',
        '.ListingItemTitle',
        '[data-name="card"]',
    ]
    
    # Настройки браузера
    BROWSER_ARGS: List[str] = [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-web-security",
        "--disable-features=IsolateOrigins,site-per-process",
        "--disable-software-rasterizer",
        "--disable-gpu-sandbox",
        "--window-size=1920,1080",
    ]
    
    # Настройки сессии
    DEFAULT_MAX_REQUESTS_PER_SESSION = 50
    DEFAULT_BASE_DELAY = 2.0
    DEFAULT_RANDOMIZE_DELAY = True
    
    # Таймауты
    PAGE_LOAD_TIMEOUT = 30000
    SELECTOR_WAIT_TIMEOUT = 5000
    SCROLL_DELAY = 2000
    DETAIL_PAGE_DELAY = 2000
    
    @classmethod
    def get_user_agent(cls) -> str:
        """Получить случайный User-Agent"""
        import random
        return random.choice(cls.USER_AGENTS)
    
    @classmethod
    def get_browser_args(cls, headless: bool = True) -> Dict[str, Any]:
        """Получить аргументы для запуска браузера"""
        return {
            "headless": headless,
            "args": cls.BROWSER_ARGS,
        }
