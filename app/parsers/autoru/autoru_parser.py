import re
import random
import asyncio
from typing import List, Optional, Dict, Any
from loguru import logger
from playwright.async_api import async_playwright, Browser, Page, BrowserContext
from app.parsers.base_parser import BaseParser
from app.models.car_listing import CarListing


class AutoRuParser(BaseParser):
    """
    Парсер для auto.ru
    Использует Playwright для обхода защиты и рендеринга JS.
    """

    BASE_URL = "https://auto.ru"
    SEARCH_URL = "https://auto.ru/cars/sale/"

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def init_browser(self):
        """Инициализация браузера Playwright"""
        if self.browser is None:
            playwright = await async_playwright().start()
            
            # Эмуляция реального пользователя
            user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            
            self.browser = await playwright.chromium.launch(
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-web-security",
                    "--disable-features=IsolateOrigins,site-per-process"
                ]
            )
            
            self.context = await self.browser.new_context(
                user_agent=user_agent,
                viewport={"width": 1920, "height": 1080},
                locale="ru-RU",
                timezone_id="Europe/Moscow"
            )
            
            # Скрипт для скрытия факта автоматизации
            await self.context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
                window.navigator.chrome = {
                    runtime: {},
                    // другие свойства...
                };
            """)
            
            self.page = await self.context.new_page()

    async def close(self):
        """Закрытие браузера"""
        if self.browser:
            await self.browser.close()
            self.browser = None
            self.context = None
            self.page = None

    def build_url(self, filters: Dict[str, Any]) -> str:
        """Построение URL поиска с параметрами"""
        brand = filters.get("brand", "").lower()
        model = filters.get("model", "").lower()
        region = filters.get("region", "")
        price_from = filters.get("price_from")
        price_to = filters.get("price_to")
        year_from = filters.get("year_from")
        year_to = filters.get("year_to")
        mileage_from = filters.get("mileage_from")
        mileage_to = filters.get("mileage_to")
        
        # Формируем базовый URL
        url = f"{self.SEARCH_URL}"
        
        # Параметры передаются через query string или форму на сайте
        # Auto.ru использует сложную структуру URL, часто через POST или JSON
        # Для простоты начнем с базового поиска по марке/модели
        
        params = []
        
        if brand and model:
            # Пример: https://auto.ru/cars/sale/bmw/x5/
            url = f"https://auto.ru/cars/sale/{brand}/{model}/"
        elif brand:
            url = f"https://auto.ru/cars/sale/{brand}/"
            
        # Добавляем параметры фильтрации
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

    async def search(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Поиск объявлений по фильтрам.
        Возвращает список словарей с данными объявлений.
        """
        await self.init_browser()
        
        url = self.build_url(filters)
        logger.info(f"AUTO.RU SEARCH: {url}")
        
        try:
            # Переход на страницу поиска
            response = await self.page.goto(url, wait_until="networkidle", timeout=30000)
            
            if not response or response.status != 200:
                logger.error(f"Failed to load page: {response.status if response else 'No response'}")
                return []
            
            logger.info(f"STATUS {response.status}: {url}")
            
            # Даем время на прогрузку контента и скриптов
            await self.page.wait_for_timeout(3000)
            
            # Ждем появления карточек объявлений
            try:
                await self.page.wait_for_selector('div[class*="ListingItem"]', timeout=10000)
            except Exception:
                logger.warning("No listings found or selector changed")
                return []
            
            # Скроллим страницу для подгрузки всех объявлений (ленивая загрузка)
            await self._scroll_page()
            
            # Извлекаем HTML после рендеринга
            html = await self.page.content()
            
            # Парсим карточки
            cards = await self._extract_cards()
            logger.info(f"AUTO.RU FOUND: {len(cards)} listings")
            
            results = []
            for card_data in cards:
                try:
                    # Детальный парсинг каждой карточки
                    detail_data = await self._parse_card_detail(card_data['url'])
                    if detail_data:
                        results.append(detail_data)
                except Exception as e:
                    logger.error(f"Error parsing card {card_data.get('url')}: {e}")
                    
            return results
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []

    async def _scroll_page(self):
        """Прокрутка страницы для загрузки ленивого контента"""
        scroll_times = 3
        for i in range(scroll_times):
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await self.page.wait_for_timeout(2000)
            await self.page.evaluate("window.scrollTo(0, 0)")
            await self.page.wait_for_timeout(1000)

    async def _extract_cards(self) -> List[Dict[str, str]]:
        """Извлечение ссылок на объявления со страницы поиска"""
        cards = []
        
        # Используем JavaScript для извлечения данных - обновленные селекторы для Auto.ru 2026
        script = """
        () => {
            const items = [];
            // Пробуем несколько возможных селекторов
            const selectors = [
                'a[href*="/cars/sale/offer/"]',
                'a.ListingItemTitle',
                'div[class*="ListingItem"] a',
                'section[class*="Listing"] a[href*="/cars/"]',
                'article a[href*="/cars/sale/"]'
            ];
            
            let allLinks = [];
            selectors.forEach(selector => {
                const links = document.querySelectorAll(selector);
                links.forEach(link => {
                    const href = link.href;
                    if (href && href.includes('/cars/sale/') && !href.includes('#')) {
                        const title = link.textContent?.trim() || '';
                        allLinks.push({ url: href, title: title });
                    }
                });
            });
            
            // Убираем дубликаты
            const seen = new Set();
            allLinks.forEach(item => {
                if (!seen.has(item.url)) {
                    seen.add(item.url);
                    items.push(item);
                }
            });
            
            return items;
        }
        """
        
        try:
            raw_cards = await self.page.evaluate(script)
            for item in raw_cards:
                if item.get('url'):
                    cards.append(item)
        except Exception as e:
            logger.error(f"Error extracting cards: {e}")
            
        return cards

    async def _parse_card_detail(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Парсинг детальной страницы объявления.
        Можно оптимизировать, открывая несколько вкладок или переиспользуя одну.
        """
        if not self.page:
            await self.init_browser()
            
        try:
            # Открываем детальную страницу в той же вкладке (или новой, если нужно)
            # Для скорости можно попробовать извлечь данные прямо со страницы поиска, 
            # если там есть вся информация. Но для надежности пойдем на страницу.
            
            # Сохраняем текущую вкладку поиска (упрощенно - просто переходим и возвращаемся)
            # В продакшене лучше использовать context.new_page()
            
            logger.info(f"AUTO.RU DETAIL: {url}")
            
            response = await self.page.goto(url, wait_until="networkidle", timeout=30000)
            if not response or response.status != 200:
                return None
                
            await self.page.wait_for_timeout(2000) # Ждем рендеринга
            
            # Извлекаем данные через JS
            data = await self.page.evaluate(self._get_extraction_script())
            
            if not data.get('price') and not data.get('title'):
                return None
                
            # Нормализация данных
            car_data = {
                "platform": "auto_ru",
                "url": url,
                "title": data.get('title', ''),
                "price": int(data.get('price', 0).replace('\xa0', '').replace(' ', '')) if data.get('price') else 0,
                "year": int(data.get('year', 0)) if data.get('year') else None,
                "mileage": int(data.get('mileage', '0').replace('\xa0', '').replace(' км', '').replace(' ', '')) if data.get('mileage') else 0,
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
            }
            
            # Возвращаемся на страницу поиска (упрощенно - просто перезагружаем поиск в следующем вызове)
            # В реальной реализации нужно управлять историей или вкладками
            
            return car_data
            
        except Exception as e:
            logger.error(f"Detail parse error for {url}: {e}")
            return None

    def _get_extraction_script(self) -> str:
        """Возвращает JS скрипт для извлечения данных со страницы объявления"""
        return """
        () => {
            const getText = (selector) => {
                const el = document.querySelector(selector);
                return el ? el.textContent.trim() : '';
            };
            
            const getAllText = (selector) => {
                const els = document.querySelectorAll(selector);
                return Array.from(els).map(el => el.textContent.trim());
            };

            // Заголовок
            let title = getText('h1[class*="Title"]') || getText('.Card__title') || '';
            
            // Цена
            let price = getText('span[class*="Price"]') || getText('.OfferPriceCaption') || '';
            
            // Год и модель часто в заголовке или отдельными блоками
            const yearMatch = title.match(/\\b(19|20)\\d{2}\\b/);
            let year = yearMatch ? yearMatch[0] : '';
            
            // Пробег
            let mileage = getText('[data-name="mileage"]') || getText('.MetroXLSRow') || ''; 
            // Иногда пробег в списке характеристик
            
            // Регион
            let region = getText('[data-name="region"]') || getText('.Card__metro') || '';
            
            // Характеристики - ищем по ключевым словам в таблице
            const allText = document.body.innerText;
            const lines = allText.split('\\n').map(l => l.trim()).filter(l => l);
            
            let engine_volume = '';
            let horsepower = '';
            let transmission = '';
            let drive = '';
            let body_type = '';
            let owners = '';
            let accidents = '';
            let pts = '';
            let brand = '';
            let model = '';
            
            // Пытаемся найти бренд и модель из заголовка или URL
            const urlParts = window.location.pathname.split('/');
            if (urlParts.includes('cars') && urlParts.includes('sale')) {
                const idx = urlParts.indexOf('sale');
                if (urlParts.length > idx + 1) brand = urlParts[idx + 1];
                if (urlParts.length > idx + 2) model = urlParts[idx + 2];
            }

            // Парсинг характеристик (формат может меняться)
            // Ищем строки вида "Объем двигателя: 3.0 л"
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

            return {
                title,
                price,
                year,
                mileage,
                region,
                brand,
                model,
                engine_volume,
                horsepower,
                transmission,
                drive,
                body_type,
                owners,
                accidents,
                pts
            };
        }
        """

    # Синхронная обертка для совместимости с текущей архитектурой
    def search_sync(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Синхронный метод для вызова асинхронного парсера"""
        return asyncio.run(self.search(filters))

    def parse_card(self, card):
        """
        Метод required by BaseParser.
        В нашем случае card - это уже спарсенные данные из search(),
        поэтому просто возвращаем их.
        """
        return card

    async def parse_search(
        self,
        brand: str,
        model: str,
        region: str = "",
        price_from: Optional[int] = None,
        price_to: Optional[int] = None,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        limit: int = 20
    ) -> List[CarListing]:
        """
        Асинхронный метод парсинга поиска, совместимый с интерфейсом DromSearchParser.
        Возвращает список объектов CarListing.
        """
        await self.init_browser()
        
        # Формируем фильтры для метода search
        filters = {
            "brand": brand,
            "model": model,
            "region": region,
            "price_from": price_from,
            "price_to": price_to,
            "year_from": year_from,
            "year_to": year_to,
        }
        
        url = self.build_url(filters)
        logger.info(f"AUTO.RU SEARCH: {url}")
        
        cars = []
        
        try:
            # Переход на страницу поиска
            response = await self.page.goto(url, wait_until="networkidle", timeout=30000)
            
            if not response or response.status != 200:
                logger.error(f"Failed to load page: {response.status if response else 'No response'}")
                return []
            
            logger.info(f"STATUS {response.status}: {url}")
            
            # Даем время на прогрузку контента и скриптов
            await self.page.wait_for_timeout(3000)
            
            # Ждем появления карточек объявлений - используем несколько селекторов
            selectors_to_try = [
                'div[class*="ListingItem"]',
                'a[href*="/cars/sale/offer/"]',
                'section[class*="Listing"]',
                'article[class*="card"]'
            ]
            
            found_selector = None
            for selector in selectors_to_try:
                try:
                    await self.page.wait_for_selector(selector, timeout=5000)
                    found_selector = selector
                    logger.info(f"Found listings with selector: {selector}")
                    break
                except Exception:
                    continue
            
            if not found_selector:
                logger.warning("No listings found with any known selector")
                # Для отладки: сохраняем HTML страницы
                html = await self.page.content()
                logger.debug(f"Page HTML length: {len(html)}")
                # Проверяем, есть ли капча или блок
                if "captcha" in html.lower() or "robot" in html.lower():
                    logger.error("Possible captcha or bot detection detected!")
                return []
            
            # Скроллим страницу для подгрузки всех объявлений (ленивая загрузка)
            await self._scroll_page()
            
            # Извлекаем ссылки на объявления
            cards_data = await self._extract_cards()
            logger.info(f"AUTO.RU FOUND CARDS: {len(cards_data)}")
            
            # Парсим первые 'limit' объявлений
            for i, card_info in enumerate(cards_data[:limit]):
                car_data = await self._parse_card_detail(card_info['url'])
                if car_data:
                    try:
                        # Преобразуем словарь в модель CarListing
                        car = CarListing(
                            url=car_data.get('url', ''),
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
                        )
                        cars.append(car)
                    except Exception as ve:
                        logger.warning(f"Validation error for car data: {ve}")
                
                # Небольшая задержка между переходами
                if i < limit - 1:
                    await asyncio.sleep(random.uniform(1.0, 2.0))
            
            logger.info(f"AUTO.RU PARSED: {len(cars)} cars")
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        return cars