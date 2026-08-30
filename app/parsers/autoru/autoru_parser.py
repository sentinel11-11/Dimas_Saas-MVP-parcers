"""
Парсер для auto.ru на основе vavilovnv/auto-ru-parser
Использует Playwright для обхода защиты и рендеринга JS.
Поддерживает proxy rotation, рандомизацию user-agent и умные задержки.

Модульная архитектура:
- config.py: Конфигурация и константы
- http/client.py: Менеджеры прокси и User-Agent
- core/parser_engine.py: Утилиты для задержек, сессий и очистки данных
- models.py: Pydantic модели данных
- autoru_parser.py: Основной класс парсера
"""

import asyncio
import random
import re
from typing import List, Optional, Dict, Any
from loguru import logger
from playwright.async_api import async_playwright, Browser, Page, BrowserContext

from app.parsers.base_parser import BaseParser
from app.models.car_listing import CarListing
from .config import AutoRuConfig
from .http.client import ProxyManager, UserAgentRotator
from .core.parser_engine import DelayManager, SessionManager, DataCleaner
from .models import AutoRuCardData, AutoRuDetailData


class AutoRuParser(BaseParser):
    """
    Production-ready парсер auto.ru с улучшенной защитой от блокировок
    Использует модульную архитектуру для разделения ответственности
    """

    BASE_URL = AutoRuConfig.BASE_URL
    SEARCH_URL = AutoRuConfig.SEARCH_URL

    def __init__(
        self, 
        headless: bool = True, 
        use_proxy: bool = None,  # По умолчанию None, чтобы использовать конфиг
        proxy_list: List[str] = None,
        max_requests_per_session: int = AutoRuConfig.DEFAULT_MAX_REQUESTS_PER_SESSION,
        base_delay: float = AutoRuConfig.DEFAULT_BASE_DELAY,
        randomize_delay: bool = AutoRuConfig.DEFAULT_RANDOMIZE_DELAY
    ):
        self.headless = headless
        # Используем прокси из параметра или из конфигурации
        if proxy_list is None:
            proxy_list = AutoRuConfig.PROXY_LIST or []
        # Если use_proxy не указан явно, включаем его если есть прокси
        self.use_proxy = use_proxy if use_proxy is not None else bool(proxy_list)
        self.proxy_manager = ProxyManager(proxy_list)
        self.user_agent_rotator = UserAgentRotator(AutoRuConfig.USER_AGENTS)
        self.current_proxy = None
        
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        
        # Менеджеры для управления сессией и задержками
        self.session_manager = SessionManager(max_requests_per_session)
        self.delay_manager = DelayManager(
            base_delay=base_delay,
            randomize=randomize_delay
        )

    async def init_browser(self):
        """Инициализация браузера Playwright с улучшенной эмуляцией человека"""
        if self.browser is None:
            playwright = await async_playwright().start()
            
            # Ротация прокси через ProxyManager
            if self.use_proxy and not self.proxy_manager.is_empty():
                self.current_proxy = self.proxy_manager.get_next_proxy()
                host = self.current_proxy.split("@")[-1] if self.current_proxy else ""
                logger.info(f"Using proxy host: {host}")
            
            # Рандомизация User-Agent через UserAgentRotator
            user_agent = self.user_agent_rotator.get_user_agent()
            logger.debug(f"Using User-Agent: {user_agent[:50]}...")
            
            # Аргументы для обхода детекции автоматизации из конфига
            browser_args = AutoRuConfig.get_browser_args(self.headless)
            
            from app.core.proxy import ProxySettings
            if self.use_proxy:
                pw_proxy = ProxySettings.playwright_proxy(scheme="http")
                if pw_proxy:
                    browser_args["proxy"] = pw_proxy
            elif self.current_proxy:
                proxy_server = self.current_proxy
                if "://" not in proxy_server:
                    proxy_server = f"http://{proxy_server}"
                if "@" in proxy_server:
                    left, host = proxy_server.split("@", 1)
                    scheme, creds = left.split("://", 1) if "://" in left else ("http", left)
                    user, _, password = creds.partition(":")
                    browser_args["proxy"] = {
                        "server": f"{scheme}://{host}",
                        "username": user,
                        "password": password,
                    }
                else:
                    browser_args["proxy"] = {"server": proxy_server}

            self.browser = await playwright.chromium.launch(**browser_args)
            
            # Создание контекста с эмуляцией реального пользователя
            self.context = await self.browser.new_context(
                user_agent=user_agent,
                viewport={"width": 1920, "height": 1080},
                locale="ru-RU",
                timezone_id="Europe/Moscow",
                color_scheme="light",
                device_scale_factor=1,
                has_touch=False,
                is_mobile=False,
            )
            
            # Скрипт для скрытия признаков автоматизации
            await self.context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                Object.defineProperty(navigator, 'languages', {get: () => ['ru-RU', 'ru', 'en-US', 'en']});
                window.navigator.chrome = {runtime: {}, loadTimes: function(){}, csi: function(){}};
                
                // Эмуляция случайных движений мыши
                let mouseX = 0, mouseY = 0;
                document.addEventListener('mousemove', (e) => {
                    mouseX = e.clientX;
                    mouseY = e.clientY;
                });
            """)
            
            self.page = await self.context.new_page()
            self.session_manager.reset()
            
            logger.info("Browser initialized successfully")

    def _get_next_proxy(self) -> str:
        """Получение следующего прокси из списка (устарело, использовать proxy_manager)"""
        return self.proxy_manager.get_next_proxy()

    async def close(self):
        """Закрытие браузера и очистка ресурсов"""
        if self.browser:
            try:
                await self.browser.close()
            except Exception as e:
                logger.error(f"Error closing browser: {e}")
            finally:
                self.browser = None
                self.context = None
                self.page = None

    def build_url(self, filters: Dict[str, Any]) -> str:
        """Построение URL поиска с фильтрами"""
        brand = filters.get("brand", "").lower()
        model = filters.get("model", "").lower()
        region = filters.get("region", "")
        price_from = filters.get("price_from")
        price_to = filters.get("price_to")
        year_from = filters.get("year_from")
        year_to = filters.get("year_to")
        
        url = f"{self.SEARCH_URL}"
        params = []
        
        region_map = {
            "moscow": "moskva",
            "spb": "sankt-peterburg",
            "ekaterinburg": "ekaterinburg",
            "novosibirsk": "novosibirsk",
            "kazan": "kazan",
        }
        region_slug = region_map.get(str(region).lower()) if region else None

        if brand and model and region_slug:
            url = f"https://auto.ru/{region_slug}/cars/{brand}/{model}/used/"
        elif brand and model:
            url = f"https://auto.ru/cars/{brand}/{model}/used/"
        elif brand and region_slug:
            url = f"https://auto.ru/{region_slug}/cars/{brand}/used/"
        elif brand:
            url = f"https://auto.ru/cars/{brand}/used/"
        
        if region:
            params.append(f"geo={region}")
        if price_from:
            params.append(f"price[from]={price_from}")
        if price_to:
            params.append(f"price[to]={price_to}")
        if year_from:
            params.append(f"year[from]={year_from}")
        if year_to:
            params.append(f"year[to]={year_to}")
        
        if params:
            url += "?" + "&".join(params)
        
        return url

    async def search(self, filters: Dict[str, Any], limit: int = 10) -> List[CarListing]:
        """
        Поиск автомобилей с применением фильтров
        
        Args:
            filters: Словарь с параметрами поиска
            limit: Максимальное количество результатов
            
        Returns:
            Список объектов CarListing
        """
        await self.init_browser()
        url = self.build_url(filters)
        logger.info(f"AUTO.RU SEARCH: {url}")
        
        cars = []
        
        try:
            # Переход на страницу поиска
            response = await self.page.goto(url, wait_until="domcontentloaded", timeout=AutoRuConfig.PAGE_LOAD_TIMEOUT)
            if not response or response.status not in (200, 301, 302):
                fallback = f"https://auto.ru/cars/{filters.get('brand','')}/{filters.get('model','')}/used/"
                logger.warning(f"AUTO.RU {response.status if response else 'none'} → fallback {fallback}")
                response = await self.page.goto(fallback, wait_until="domcontentloaded", timeout=AutoRuConfig.PAGE_LOAD_TIMEOUT)
            if not response or response.status >= 400:
                logger.error(f"Failed to load page: {response.status if response else 'No response'}")
                # всё равно пробуем вытащить карточки с того, что открылось
            else:
                logger.info(f"STATUS {response.status}: {self.page.url}")
            
            # Ожидание загрузки контента
            await self.page.wait_for_timeout(AutoRuConfig.SCROLL_DELAY)
            
            # Поиск работающих селекторов из конфига
            found_selector = None
            for selector in AutoRuConfig.LISTING_SELECTORS:
                try:
                    await self.page.wait_for_selector(selector, timeout=AutoRuConfig.SELECTOR_WAIT_TIMEOUT)
                    found_selector = selector
                    logger.info(f"Found listings with selector: {selector}")
                    break
                except Exception:
                    continue
            
            if not found_selector:
                logger.warning("No listings found on page")
                return []
            
            # Прокрутка страницы для подгрузки контента
            await self._scroll_page()
            
            # Извлечение карточек
            cards_data = await self._extract_cards()
            logger.info(f"AUTO.RU FOUND CARDS: {len(cards_data)}")

            for card_info in cards_data[:limit]:
                try:
                    title = card_info.get("title") or "auto.ru"
                    year_m = re.search(r"(19\d{2}|20\d{2})", title)
                    price = self._clean_price(str(card_info.get("price") or "0"))
                    cars.append(
                        CarListing(
                            url=card_info.get("url") or "",
                            title=title[:180],
                            platform="auto_ru",
                            price=price,
                            year=int(year_m.group(1)) if year_m else 0,
                            mileage=self._clean_number(str(card_info.get("mileage") or "0")),
                            region=card_info.get("region") or "",
                            brand=(filters.get("brand") or "").capitalize(),
                            model=filters.get("model") or "",
                        )
                    )
                except Exception as ve:
                    logger.warning(f"Listing card skip: {ve}")
            if cars:
                logger.info(f"AUTO.RU PARSED FROM LISTING: {len(cars)}")
                return cars

            for i, card_info in enumerate(cards_data[: min(limit, 4)]):
                car_data = await self._parse_card_detail(card_info['url'])
                
                if car_data:
                    try:
                        car = CarListing(
                            url=car_data.get('url', ''),
                            title=car_data.get('title', f"{car_data.get('brand', '')} {car_data.get('model', '')}"),
                            platform="auto_ru",
                            price=car_data.get('price', 0),
                            year=car_data.get('year') or 0,
                            mileage=car_data.get('mileage', 0),
                            region=car_data.get('region', 'Unknown'),
                            brand=car_data.get('brand', '').capitalize(),
                            model=car_data.get('model', ''),
                            body_type=car_data.get('body_type', ''),
                            drive=car_data.get('drive', ''),
                            owners=car_data.get('owners'),
                            accidents=car_data.get('accidents'),
                            pts=car_data.get('pts', ''),
                            engine=f"{car_data.get('engine_volume', 0)}L {car_data.get('horsepower', 0)}HP",
                            transmission=car_data.get('transmission', ''),
                            engine_volume=car_data.get('engine_volume', 0),
                            horsepower=car_data.get('horsepower', 0),
                            image_url=car_data.get('image_url')
                        )
                        cars.append(car)
                        logger.debug(f"Parsed car: {car.brand} {car.model} {car.year} - {car.price}₽")
                    except Exception as ve:
                        logger.warning(f"Validation error for car data: {ve}")
                
                # Умная задержка через DelayManager
                if i < limit - 1:
                    await self.delay_manager.wait()
                
                # Ротация сессии через SessionManager
                self.session_manager.increment_request()
                if self.session_manager.should_rotate():
                    logger.info("Session limit reached, rotating browser session")
                    await self.close()
                    await self.init_browser()
            
            logger.info(f"AUTO.RU PARSED: {len(cars)} cars successfully")
            
        except Exception as e:
            logger.error(f"Search error: {type(e).__name__}: {e}")
        
        finally:
            await self.close()
        
        return cars

    async def _scroll_page(self):
        """Прокрутка страницы для подгрузки ленивого контента"""
        scroll_steps = 1
        for i in range(scroll_steps):
            try:
                await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await self.page.wait_for_timeout(2000)
                await self.page.evaluate("window.scrollTo(0, 0)")
                await self.page.wait_for_timeout(1000)
            except Exception as e:
                logger.warning(f"Scroll error: {e}")
                break

    async def _extract_cards(self) -> List[Dict[str, str]]:
        """Извлечение ссылок на карточки товаров со страницы"""
        cards = []
        
        script = """() => {
            const items = [];
            const selectors = [
                'a[href*="/cars/sale/offer/"]',
                'a.ListingItemTitle',
                'div[class*="ListingItem"] a'
            ];
            
            let allLinks = [];
            selectors.forEach(selector => {
                const links = document.querySelectorAll(selector);
                links.forEach(link => {
                    const href = link.href || '';
                    if (href.includes('auto.ru') && (href.includes('/cars/') || href.includes('/offer/')) && !href.includes('#')) {
                        const box = link.closest('[class*="ListingItem"]') || link.parentElement;
                        const text = (box && box.innerText) ? box.innerText.replace(/\\s+/g, ' ') : (link.textContent || '');
                        allLinks.push({
                            url: href,
                            title: link.textContent?.trim() || '',
                            price: text,
                            mileage: text,
                            region: text
                        });
                    }
                });
            });
            
            // Удаление дубликатов
            const seen = new Set();
            allLinks.forEach(item => {
                if (!seen.has(item.url)) {
                    seen.add(item.url);
                    items.push(item);
                }
            });
            
            return items;
        }"""
        
        try:
            raw_cards = await self.page.evaluate(script)
            for item in raw_cards:
                if item.get('url'):
                    cards.append(item)
        except Exception as e:
            logger.error(f"Error extracting cards: {e}")
        
        return cards

    async def _parse_card_detail(self, url: str) -> Optional[Dict[str, Any]]:
        """Парсинг страницы с деталями автомобиля"""
        if not self.page:
            await self.init_browser()
        
        try:
            logger.info(f"AUTO.RU DETAIL: {url}")
            
            response = await self.page.goto(url, wait_until="domcontentloaded", timeout=12000)
            if not response or response.status != 200:
                logger.warning(f"Failed to load detail page: {response.status if response else 'No response'}")
                return None
            
            await self.page.wait_for_timeout(2000)
            
            # Извлечение данных через JavaScript
            data = await self.page.evaluate(self._get_extraction_script())
            
            if not data.get('price') and not data.get('title'):
                logger.warning("No essential data found on detail page")
                return None
            
            # Постобработка данных
            car_data = {
                "platform": "auto_ru",
                "url": url,
                "title": data.get('title', ''),
                "price": self._clean_price(data.get('price', '0')),
                "year": int(data.get('year', 0)) if data.get('year') else None,
                "mileage": self._clean_number(data.get('mileage', '0')),
                "region": data.get('region', ''),
                "brand": data.get('brand', ''),
                "model": data.get('model', ''),
                "engine_volume": float(data.get('engine_volume', 0)) if data.get('engine_volume') else 0,
                "horsepower": int(data.get('horsepower', 0)) if data.get('horsepower') else 0,
                "transmission": data.get('transmission', ''),
                "drive": data.get('drive', ''),
                "body_type": data.get('body_type', ''),
                "owners": int(data.get('owners', 0)) if data.get('owners') else None,
                "accidents": int(data.get('accidents', 0)) if data.get('accidents') else None,
                "pts": data.get('pts', ''),
                "image_url": data.get('image_url'),
                "photos": data.get('photos', [])
            }
            
            return car_data
            
        except Exception as e:
            logger.error(f"Detail parse error for {url}: {type(e).__name__}: {e}")
            return None

    def _get_extraction_script(self) -> str:
        """JavaScript для извлечения данных со страницы автомобиля"""
        return """() => {
            const getText = (selector) => {
                const el = document.querySelector(selector);
                return el ? el.textContent.trim() : '';
            };
            
            let title = getText('h1[class*="Title"]') || getText('.Card__title') || '';
            let price = getText('span[class*="Price"]') || getText('.OfferPriceCaption') || '';
            
            const yearMatch = title.match(/\\b(19|20)\\d{2}\\b/);
            let year = yearMatch ? yearMatch[0] : '';
            
            let mileage = getText('[data-name="mileage"]') || '';
            let region = getText('[data-name="region"]') || '';
            
            const allText = document.body.innerText;
            const lines = allText.split('\\n').map(l => l.trim()).filter(l => l);
            
            let engine_volume = '', horsepower = '', transmission = '', drive = '', 
                body_type = '', owners = '', accidents = '', pts = '', 
                brand = '', model = '';
            
            // Извлечение марки и модели из URL
            const urlParts = window.location.pathname.split('/');
            if (urlParts.includes('cars') && urlParts.includes('sale')) {
                const idx = urlParts.indexOf('sale');
                if (urlParts.length > idx + 1) brand = urlParts[idx + 1];
                if (urlParts.length > idx + 2) model = urlParts[idx + 2];
            }
            
            // Парсинг характеристик из текста
            lines.forEach(line => {
                if (line.includes('Объем') || line.includes('двигателя')) {
                    const match = line.match(/(\\d+\\.?\\d*)\\s?л/);
                    if (match) engine_volume = match[1];
                }
                if (line.includes('Мощность') || line.includes('л.с.')) {
                    const match = line.match(/(\\d+)\\s?л\\.?с/);
                    if (match) horsepower = match[1];
                }
                if (line.includes('Коробка') || line.includes('трансмиссия')) {
                    transmission = line.split(':')[1]?.trim() || line;
                }
                if (line.includes('Привод')) {
                    drive = line.split(':')[1]?.trim() || line;
                }
                if (line.includes('Кузов')) {
                    body_type = line.split(':')[1]?.trim() || line;
                }
                if (line.includes('Владельцев') || line.includes('владелец')) {
                    const match = line.match(/(\\d+)/);
                    if (match) owners = match[1];
                }
                if (line.includes('ДТП') || line.includes('аварий')) {
                    const match = line.match(/(\\d+)/);
                    if (match) accidents = match[1];
                }
                if (line.includes('ПТС')) {
                    pts = line.split(':')[1]?.trim() || line;
                }
            });
            
            // Извлечение фотографий
            let photos = [];
            const imgSelectors = [
                'img[class*="Image"], img[data-src]',
                '.Carousel__item img',
                '.PhotoViewer__item img',
                '[class*="photo"] img'
            ];
            
            imgSelectors.forEach(selector => {
                const imgs = document.querySelectorAll(selector);
                imgs.forEach(img => {
                    let src = img.src || img.dataset?.src || img.getAttribute('data-src');
                    if (src && !src.includes('placeholder') && !photos.includes(src)) {
                        // Нормализация URL
                        if (src.startsWith('//')) src = 'https:' + src;
                        else if (src.startsWith('/')) src = 'https://auto.ru' + src;
                        photos.push(src);
                    }
                });
            });
            
            // Берем первую фотографию как основную
            let image_url = photos.length > 0 ? photos[0] : null;
            
            return {
                title, price, year, mileage, region, brand, model,
                engine_volume, horsepower, transmission, drive, body_type,
                owners, accidents, pts, image_url, photos
            };
        }"""

    def _clean_price(self, price_str: str) -> int:
        """Очистка строки цены и преобразование в число"""
        if not price_str:
            return 0
        try:
            cleaned = price_str.replace('\xa0', '').replace(' ', '').replace('₽', '').replace('руб', '')
            return int(float(cleaned))
        except (ValueError, TypeError):
            return 0

    def _clean_number(self, number_str: str) -> int:
        """Очистка строки числа и преобразование в integer"""
        if not number_str:
            return 0
        try:
            cleaned = number_str.replace('\xa0', '').replace(' ', '').replace('км', '').replace(',', '.')
            return int(float(cleaned))
        except (ValueError, TypeError):
            return 0

    def _calculate_delay(self) -> float:
        """Расчет умной задержки для эмуляции человека"""
        if self._randomize_delay:
            base = self._base_delay
            jitter = random.uniform(-0.5, 0.5)
            return max(0.5, base + jitter)
        return self._base_delay

    def search_sync(self, filters: Dict[str, Any], limit: int = 10) -> List[CarListing]:
        """Синхронная обертка для асинхронного search"""
        return asyncio.run(self.search(filters, limit))

    def parse_card(self, card):
        """Заглушка для совместимости с базовым классом"""
        pass
