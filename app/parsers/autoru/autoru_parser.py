import asyncio
import random
from typing import List, Optional, Dict, Any
from loguru import logger
from playwright.async_api import async_playwright, Browser, Page, BrowserContext
from app.parsers.base_parser import BaseParser
from app.models.car_listing import CarListing


class AutoRuParser(BaseParser):
    """
    Улучшенный парсер для auto.ru на основе vavilovnv/auto-ru-parser
    Использует Playwright + Selenium-like подход для обхода защиты и рендеринга JS.
    Поддерживает proxy rotation, рандомизацию user-agent и умную задержку.
    """

    BASE_URL = "https://auto.ru"
    SEARCH_URL = "https://auto.ru/cars/sale/"

    def __init__(self, headless: bool = True, use_proxy: bool = False, proxy_list: List[str] = None):
        self.headless = headless
        self.use_proxy = use_proxy
        self.proxy_list = proxy_list or []
        self.current_proxy = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._request_count = 0
        self._max_requests_per_session = 50

    async def init_browser(self):
        """Инициализация браузера Playwright с улучшенной эмуляцией"""
        if self.browser is None:
            playwright = await async_playwright().start()
            if self.use_proxy and self.proxy_list:
                self.current_proxy = self._get_next_proxy()
                logger.info(f"Using proxy: {self.current_proxy}")
            user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            ]
            user_agent = random.choice(user_agents)
            args = ["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage", "--disable-web-security", "--disable-features=IsolateOrigins,site-per-process", "--disable-software-rasterizer", "--disable-gpu-sandbox"]
            browser_args = {"headless": self.headless, "args": args}
            if self.current_proxy:
                browser_args["proxy"] = {"server": self.current_proxy}
            self.browser = await playwright.chromium.launch(**browser_args)
            self.context = await self.browser.new_context(user_agent=user_agent, viewport={"width": 1920, "height": 1080}, locale="ru-RU", timezone_id="Europe/Moscow", color_scheme="light")
            await self.context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined}); Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]}); Object.defineProperty(navigator, 'languages', {get: () => ['ru-RU', 'ru', 'en-US', 'en']}); window.navigator.chrome = {runtime: {}, loadTimes: function(){}, csi: function(){}};")
            self.page = await self.context.new_page()
            self._request_count = 0

    def _get_next_proxy(self) -> str:
        if not self.proxy_list:
            return None
        return random.choice(self.proxy_list)

    async def close(self):
        if self.browser:
            await self.browser.close()
            self.browser = None
            self.context = None
            self.page = None

    def build_url(self, filters: Dict[str, Any]) -> str:
        brand = filters.get("brand", "").lower()
        model = filters.get("model", "").lower()
        region = filters.get("region", "")
        price_from = filters.get("price_from")
        price_to = filters.get("price_to")
        year_from = filters.get("year_from")
        year_to = filters.get("year_to")
        url = f"{self.SEARCH_URL}"
        params = []
        if brand and model:
            url = f"https://auto.ru/cars/sale/{brand}/{model}/"
        elif brand:
            url = f"https://auto.ru/cars/sale/{brand}/"
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
        await self.init_browser()
        url = self.build_url(filters)
        logger.info(f"AUTO.RU SEARCH: {url}")
        cars = []
        try:
            response = await self.page.goto(url, wait_until="networkidle", timeout=30000)
            if not response or response.status != 200:
                logger.error(f"Failed to load page: {response.status if response else 'No response'}")
                return []
            logger.info(f"STATUS {response.status}: {url}")
            await self.page.wait_for_timeout(3000)
            selectors_to_try = ['div[class*="ListingItem"]', 'a[href*="/cars/sale/offer/"]', 'section[class*="Listing"]', 'article[class*="card"]']
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
                logger.warning("No listings found")
                return []
            await self._scroll_page()
            cards_data = await self._extract_cards()
            logger.info(f"AUTO.RU FOUND CARDS: {len(cards_data)}")
            for i, card_info in enumerate(cards_data[:limit]):
                car_data = await self._parse_card_detail(card_info['url'])
                if car_data:
                    try:
                        car = CarListing(url=car_data.get('url', ''), title=car_data.get('title', f"{car_data.get('brand', '')} {car_data.get('model', '')}"), platform="auto_ru", price=car_data.get('price', 0), year=car_data.get('year') or 0, mileage=car_data.get('mileage', 0), region=car_data.get('region', 'Unknown'), brand=car_data.get('brand', '').capitalize(), model=car_data.get('model', ''), body_type=car_data.get('body_type', ''), drive=car_data.get('drive', ''), owners=car_data.get('owners'), accidents=car_data.get('accidents'), pts=car_data.get('pts', ''), engine=f"{car_data.get('engine_volume', 0)}L {car_data.get('horsepower', 0)}HP", transmission=car_data.get('transmission', ''), engine_volume=car_data.get('engine_volume', 0), horsepower=car_data.get('horsepower', 0))
                        cars.append(car)
                    except Exception as ve:
                        logger.warning(f"Validation error: {ve}")
                if i < limit - 1:
                    await asyncio.sleep(random.uniform(1.0, 2.0))
                self._request_count += 1
                if self._request_count >= self._max_requests_per_session:
                    logger.info("Session limit reached, rotating browser")
                    await self.close()
                    await self.init_browser()
            logger.info(f"AUTO.RU PARSED: {len(cars)} cars")
        except Exception as e:
            logger.error(f"Search error: {e}")
        return cars

    async def _scroll_page(self):
        for i in range(3):
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await self.page.wait_for_timeout(2000)
            await self.page.evaluate("window.scrollTo(0, 0)")
            await self.page.wait_for_timeout(1000)

    async def _extract_cards(self) -> List[Dict[str, str]]:
        cards = []
        script = """() => { const items = []; const selectors = ['a[href*="/cars/sale/offer/"]', 'a.ListingItemTitle', 'div[class*="ListingItem"] a']; let allLinks = []; selectors.forEach(selector => { const links = document.querySelectorAll(selector); links.forEach(link => { const href = link.href; if (href && href.includes('/cars/sale/') && !href.includes('#')) { allLinks.push({ url: href, title: link.textContent?.trim() || '' }); } }); }); const seen = new Set(); allLinks.forEach(item => { if (!seen.has(item.url)) { seen.add(item.url); items.push(item); } }); return items; }"""
        try:
            raw_cards = await self.page.evaluate(script)
            for item in raw_cards:
                if item.get('url'):
                    cards.append(item)
        except Exception as e:
            logger.error(f"Error extracting cards: {e}")
        return cards

    async def _parse_card_detail(self, url: str) -> Optional[Dict[str, Any]]:
        if not self.page:
            await self.init_browser()
        try:
            logger.info(f"AUTO.RU DETAIL: {url}")
            response = await self.page.goto(url, wait_until="networkidle", timeout=30000)
            if not response or response.status != 200:
                return None
            await self.page.wait_for_timeout(2000)
            data = await self.page.evaluate(self._get_extraction_script())
            if not data.get('price') and not data.get('title'):
                return None
            car_data = {"platform": "auto_ru", "url": url, "title": data.get('title', ''), "price": int(data.get('price', 0).replace('\xa0', '').replace(' ', '')) if data.get('price') else 0, "year": int(data.get('year', 0)) if data.get('year') else None, "mileage": int(data.get('mileage', '0').replace('\xa0', '').replace(' км', '').replace(' ', '')) if data.get('mileage') else 0, "region": data.get('region', ''), "brand": data.get('brand', ''), "model": data.get('model', ''), "engine_volume": float(data.get('engine_volume', 0)) if data.get('engine_volume') else 0, "horsepower": int(data.get('horsepower', 0)) if data.get('horsepower') else 0, "transmission": data.get('transmission', ''), "drive": data.get('drive', ''), "body_type": data.get('body_type', ''), "owners": int(data.get('owners', 0)) if data.get('owners') else None, "accidents": int(data.get('accidents', 0)) if data.get('accidents') else None, "pts": data.get('pts', '')}
            return car_data
        except Exception as e:
            logger.error(f"Detail parse error for {url}: {e}")
            return None

    def _get_extraction_script(self) -> str:
        return """() => { const getText = (selector) => { const el = document.querySelector(selector); return el ? el.textContent.trim() : ''; }; let title = getText('h1[class*="Title"]') || getText('.Card__title') || ''; let price = getText('span[class*="Price"]') || getText('.OfferPriceCaption') || ''; const yearMatch = title.match(/\\b(19|20)\\d{2}\\b/); let year = yearMatch ? yearMatch[0] : ''; let mileage = getText('[data-name="mileage"]') || ''; let region = getText('[data-name="region"]') || ''; const allText = document.body.innerText; const lines = allText.split('\\n').map(l => l.trim()).filter(l => l); let engine_volume = '', horsepower = '', transmission = '', drive = '', body_type = '', owners = '', accidents = '', pts = '', brand = '', model = ''; const urlParts = window.location.pathname.split('/'); if (urlParts.includes('cars') && urlParts.includes('sale')) { const idx = urlParts.indexOf('sale'); if (urlParts.length > idx + 1) brand = urlParts[idx + 1]; if (urlParts.length > idx + 2) model = urlParts[idx + 2]; } lines.forEach(line => { if (line.includes('Объем') || line.includes('двигателя')) { const match = line.match(/(\\d+\\.?\\d*)\\s?л/); if (match) engine_volume = match[1]; } if (line.includes('Мощность') || line.includes('л.с.')) { const match = line.match(/(\\d+)\\s?л\\.?с/); if (match) horsepower = match[1]; } if (line.includes('Коробка') || line.includes('трансмиссия')) { transmission = line.split(':')[1]?.trim() || line; } if (line.includes('Привод')) { drive = line.split(':')[1]?.trim() || line; } if (line.includes('Кузов')) { body_type = line.split(':')[1]?.trim() || line; } if (line.includes('Владельцев') || line.includes('владелец')) { const match = line.match(/(\\d+)/); if (match) owners = match[1]; } if (line.includes('ДТП') || line.includes('аварий')) { const match = line.match(/(\\d+)/); if (match) accidents = match[1]; } if (line.includes('ПТС')) { pts = line.split(':')[1]?.trim() || line; } }); return { title, price, year, mileage, region, brand, model, engine_volume, horsepower, transmission, drive, body_type, owners, accidents, pts }; }"""

    def search_sync(self, filters: Dict[str, Any], limit: int = 10) -> List[CarListing]:
        return asyncio.run(self.search(filters, limit))

    def parse_card(self, card):
        pass
