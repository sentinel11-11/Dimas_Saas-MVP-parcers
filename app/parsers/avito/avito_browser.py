"""Avito через Playwright: сначала домашний IP, затем HTTP-прокси."""
from __future__ import annotations

import asyncio
import re
from typing import Any, Dict, List, Optional

from loguru import logger

from app.core.proxy import ProxySettings
from app.data.brands import slug_part

JS_ITEMS = """() => {
  const items = [];
  const nodes = document.querySelectorAll('[data-marker="item"], article, div[data-item-id]');
  const pool = nodes.length ? nodes : document.querySelectorAll('a[href*="/avtomobili/"]');
  pool.forEach(node => {
    const a = node.querySelector
      ? (node.querySelector('a[itemprop="url"], a[data-marker="item-title"], a[href*="_"]') || node)
      : node;
    const href = a && a.href ? a.href : '';
    if (!href || !href.includes('avito.ru') || href.includes('/brands/')) return;
    const title = (a.textContent || node.innerText || '').trim().split('\\n')[0];
    const text = (node.innerText || '').replace(/\\s+/g, ' ');
    items.push({ url: href.split('?')[0], title, text });
  });
  return items;
}"""


def search_sync(filters: Dict[str, Any], limit: int = 12) -> List[dict]:
    try:
        return asyncio.run(_search(filters, limit))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_search(filters, limit))
        finally:
            loop.close()


def _cards(raw, brand: str, model: str, limit: int) -> List[dict]:
    ads: List[dict] = []
    seen = set()
    for item in raw or []:
        u = item.get("url") or ""
        if not u or u in seen:
            continue
        seen.add(u)
        title = (item.get("title") or "Avito").strip()[:180]
        text = item.get("text") or ""
        price_m = re.search(r"(\d[\d\s]{3,})\s*₽", text)
        year_m = re.search(r"\b(19\d{2}|20\d{2})\b", title + " " + text)
        km_m = re.search(r"([\d\s]{2,})\s*км", text, re.I)
        ads.append(
            {
                "url": u,
                "title": title or f"{brand} {model}",
                "price": int(re.sub(r"\D", "", price_m.group(1))) if price_m else 0,
                "year": int(year_m.group(1)) if year_m else 0,
                "mileage": int(re.sub(r"\D", "", km_m.group(1))) if km_m else 0,
                "brand": brand,
                "model": model,
                "platform": "avito",
                "source": "avito",
            }
        )
        if len(ads) >= limit:
            break
    return ads


async def _open(url: str, proxy: Optional[dict], brand: str, model: str, limit: int) -> List[dict]:
    from playwright.async_api import async_playwright

    launch = {"headless": True, "args": ["--disable-blink-features=AutomationControlled"]}
    label = "direct"
    if proxy:
        launch["proxy"] = proxy
        label = proxy.get("server", "proxy")
    async with async_playwright() as p:
        browser = await p.chromium.launch(**launch)
        try:
            context = await browser.new_context(
                locale="ru-RU",
                viewport={"width": 1366, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                ),
            )
            await context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
            )
            page = await context.new_page()
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=35000)
            status = resp.status if resp else 0
            logger.info(f"AVITO PLAYWRIGHT STATUS {status} via {label}")
            if resp is None or status in (0, 403, 429, 407):
                return []
            await page.wait_for_timeout(3500)
            raw = await page.evaluate(JS_ITEMS)
            ads = _cards(raw, brand, model, limit)
            logger.info(f"AVITO PLAYWRIGHT FOUND: {len(ads)} via {label}")
            return ads
        finally:
            await browser.close()


async def _search(filters: Dict[str, Any], limit: int) -> List[dict]:
    brand = slug_part(filters.get("brand") or "")
    model = slug_part(filters.get("model") or "")
    region = (filters.get("region") or filters.get("target_region") or "rossiya").strip().lower()
    if region in ("", "russia"):
        region = "rossiya"
    url = f"https://www.avito.ru/{region}/avtomobili/"
    if brand and model:
        url += f"{brand}/{model}/"
    elif brand:
        url += f"{brand}/"
    logger.info(f"AVITO PLAYWRIGHT: {url}")

    modes: List[Optional[dict]] = [None]
    http_proxy = ProxySettings.playwright_proxy(scheme="http")
    if http_proxy:
        modes.append(http_proxy)

    last_error = None
    for proxy in modes:
        try:
            ads = await _open(url, proxy, brand, model, limit)
            if ads:
                return ads
        except Exception as e:
            last_error = e
            logger.error(f"AVITO PLAYWRIGHT ERROR: {e}")
    if last_error:
        logger.error(f"AVITO failed: {last_error}")
    return []
