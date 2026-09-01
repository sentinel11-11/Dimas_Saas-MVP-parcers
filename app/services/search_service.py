"""Оркестрация поиска: Drom-first, опциональные источники, кэш, jobs."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from loguru import logger

from app.core.labels import BODY, DRIVE, FUEL, PTS, STEER, TRANS, city, money, ru
from app.core.normalizer import DataNormalizer
from app.core.scoring import apply_filters, dedup, score_batch
from app.models.car_listing import CarListing

CACHE_TTL = 5 * 60
_cache: Dict[str, Dict[str, Any]] = {}
JOBS: Dict[str, Dict[str, Any]] = {}
LAST_RESULTS: Dict[str, Any] = {"results": [], "filters_applied": {}, "brand": "", "model": ""}


def _cache_key(payload: dict) -> str:
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()


def _image_src(url: Optional[str], platform: str = "") -> str:
    raw = (url or "").strip()
    if not raw or raw.startswith("/static/"):
        return raw or "/static/images/no-car-image.png"
    plat = (platform or "").lower()
    if plat in ("auto_ru", "autoru", "auto.ru") or "autoru-vos" in raw or "avatars.mds.yandex" in raw:
        from urllib.parse import quote
        return "/img?u=" + quote(raw, safe="")
    return raw


def _fmt_money(n) -> str:
    try:
        return f"{int(n or 0):,}".replace(",", " ")
    except (TypeError, ValueError):
        return "0"


def _listing_to_dict(car: CarListing) -> dict:
    extra = car.model_dump()
    reloc = extra.get("relocation") or {}
    landed = extra.get("landed_price") or ((car.price or 0) + int(reloc.get("total") or 0))
    net = extra.get("net_vs_market")
    if net is None:
        net = round((car.market_price or 0) - landed)
    return {
        "title": car.title,
        "price": car.price,
        "price_fmt": _fmt_money(car.price),
        "year": car.year,
        "mileage": car.mileage,
        "mileage_fmt": _fmt_money(car.mileage),
        "region": city(car.region) or car.region,
        "url": car.url,
        "platform": {"auto_ru": "autoru", "auto.ru": "autoru"}.get((car.platform or "").lower(), car.platform),
        "image_url": _image_src(car.image_url, car.platform),
        "market_price": car.market_price,
        "market_price_fmt": _fmt_money(car.market_price),
        "market_deviation": car.market_deviation,
        "probability": car.probability_good_deal,
        "deal_pct": int(round((car.probability_good_deal or 0) * 100)),
        "liquidity": car.liquidity_score,
        "liquidity_pct": int(round((car.liquidity_score or 0) * 100)),
        "badge_class": _badge(car.probability_good_deal),
        "owners": car.owners,
        "transmission": ru(car.transmission, TRANS),
        "fuel": ru(car.fuel, FUEL),
        "drive": ru(car.drive, DRIVE),
        "body_type": ru(car.body_type, BODY),
        "engine_volume": car.engine_volume,
        "horsepower": car.horsepower,
        "pts": ru(car.pts, PTS),
        "vin": extra.get("vin"),
        "color": extra.get("color"),
        "accidents": car.accidents,
        "steering": ru(extra.get("steering"), STEER),
        "relocation": reloc,
        "landed_price": landed,
        "landed_fmt": _fmt_money(landed),
        "net_vs_market": net,
        "net_fmt": money(net),
        "scoring_note": extra.get("scoring_note") or "",
        "suspicious": extra.get("suspicious") or False,
        "peer_size": extra.get("peer_size") or 0,
        "risk_flags": extra.get("risk_flags") or [],
        "description": (extra.get("description") or "")[:500],
    }


def _badge(probability: Optional[float]) -> str:
    p = probability or 0
    if p >= 0.8:
        return "bg-success"
    if p >= 0.6:
        return "bg-primary"
    if p >= 0.4:
        return "bg-warning"
    return "bg-danger"


def _to_car(ad: dict, platform: str) -> Optional[CarListing]:
    try:
        normalized = DataNormalizer.normalize(ad)
        normalized["platform"] = platform
        if not normalized.get("url") or not normalized.get("title"):
            return None
        if not normalized.get("price"):
            normalized["price"] = 0
        return CarListing(**normalized)
    except Exception as e:
        logger.error(f"NORMALIZE ERROR {platform}: {e}")
        return None


def _search_drom(filters: dict, limit: int, errors: list) -> List[CarListing]:
    from app.parsers.drom.drom_parser import DromParser
    from app.parsers.drom.drom_detail_parser import DromDetailParser

    parser = DromParser()
    detail = DromDetailParser()
    payload = dict(filters)
    payload["drom_pages"] = 5
    ads = parser.search(payload) or []
    logger.info(f"DROM FOUND: {len(ads)}")

    cars: List[CarListing] = []
    for ad in ads:
        car = _to_car(ad, "drom")
        if car:
            cars.append(car)

    pre = [c for c in cars if apply_filters(c, filters)]
    if not pre:
        pre = cars
    top_n = pre[: min(max(limit, 40), 80)]

    def enrich(car: CarListing) -> CarListing:
        try:
            extra = detail.parse(car.url)
            if extra:
                merged = {**car.model_dump(), **{k: v for k, v in extra.items() if v not in (None, "")}}
                rebuilt = _to_car(merged, "drom")
                return rebuilt or car
        except Exception as e:
            logger.error(f"DROM DETAIL ERROR: {e}")
            errors.append(f"Drom деталь: {e}")
        return car

    enriched: List[CarListing] = []
    workers = min(5, len(top_n) or 1)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(enrich, c): c for c in top_n}
        for fut in as_completed(futs):
            try:
                enriched.append(fut.result())
            except Exception as e:
                errors.append(f"Drom поток: {e}")
                enriched.append(futs[fut])
    return enriched


def _search_avito(filters: dict, limit: int, errors: list) -> List[CarListing]:
    from app.parsers.avito import avito_browser
    from app.core.proxy import ProxySettings

    logger.info(ProxySettings.status_line())
    ads = []
    # requests почти всегда 403 — сразу браузер через тот же прокси
    try:
        ads = avito_browser.search_sync(filters, limit=min(limit, 20))
    except Exception as e:
        logger.error(f"AVITO PLAYWRIGHT FAIL: {e}")
        errors.append("Avito Playwright: установите `playwright install chromium`")
    logger.info(f"AVITO FOUND: {len(ads)}")
    if not ads:
        errors.append("Avito пуст (антибот или прокси не принят). Проверьте строку Proxy: ON при старте.")
    cars = []
    for ad in ads:
        car = _to_car(ad, "avito")
        if car:
            cars.append(car)
    return cars


async def _search_autoru(filters: dict, limit: int, errors: list) -> List[CarListing]:
    from app.parsers.autoru.autoru_parser import AutoRuParser

    proxy_list_str = os.getenv("AUTORU_PROXIES", "")
    autoru_proxy_list = [p.strip() for p in proxy_list_str.split(",") if p.strip()] or None
    payload = {
        "brand": filters.get("brand"),
        "model": filters.get("model"),
        "region": filters.get("region"),
        "year_from": filters.get("year_min"),
        "year_to": filters.get("year_max"),
        "year_min": filters.get("year_min"),
        "year_max": filters.get("year_max"),
        "price_from": filters.get("price_min"),
        "price_to": filters.get("price_max"),
        "price_min": filters.get("price_min"),
        "price_max": filters.get("price_max"),
        "mileage_max": filters.get("mileage_max"),
    }
    cars = []
    try:
        from app.utils.http_client import HTTPClient
        from app.parsers.autoru.autoru_html import is_blocked, parse_listing_html
        from app.parsers.autoru.autoru_parser import AutoRuParser as _P

        brand = (payload.get("brand") or "").strip().lower()
        model = (payload.get("model") or "").strip().lower()
        http_url = f"https://auto.ru/cars/{brand}/{model}/used/?year_from={payload.get('year_from') or ''}&year_to={payload.get('year_to') or ''}"
        logger.info(f"AUTO.RU HTTP try {http_url}")
        resp = HTTPClient(min_delay=0.2, max_delay=0.5).get(http_url)
        if resp and resp.text and not is_blocked(resp.text, resp.url or http_url):
            html_cards = parse_listing_html(resp.text)
            parser_tmp = _P(headless=True, use_proxy=False)
            for card in html_cards[: min(limit, 24)]:
                parsed = parser_tmp._parse_listing_card(card, payload)
                if parsed:
                    cars.append(parsed)
            logger.info(f"AUTO.RU HTTP PARSED: {len(cars)}")
        elif resp:
            logger.warning("AUTO.RU HTTP blocked/captcha")
    except Exception as e:
        logger.warning(f"AUTO.RU HTTP skip: {e}")

    if not cars:
        for use_proxy in (False, True):
            parser = AutoRuParser(headless=True, use_proxy=use_proxy, proxy_list=autoru_proxy_list)
            logger.info(f"AUTO.RU try proxy={use_proxy}")
            try:
                cars = await asyncio.wait_for(
                    parser.search(filters=payload, limit=min(limit, 24)),
                    timeout=35,
                )
            except Exception as e:
                logger.error(f"AUTORU SEARCH ERROR proxy={use_proxy}: {e}")
                try:
                    await parser.close()
                except Exception:
                    pass
                cars = []
            if cars:
                break
    if not cars:
        errors.append("Auto.ru недоступен (таймаут или блокировка)")
        return []
    logger.info(f"AUTO.RU FOUND: {len(cars)}")
    result = []
    for car_data in cars:
        if isinstance(car_data, CarListing):
            result.append(car_data)
        else:
            car = _to_car(car_data, "autoru")
            if car:
                result.append(car)
    return result


def run_search(params: dict) -> dict:
    sources = params.get("sources") or ["drom"]
    if isinstance(sources, str):
        sources = [sources]
    limit = max(1, min(int(params.get("limit") or 50), 100))
    filters = {
        "brand": (params.get("brand") or "").strip().lower(),
        "model": (params.get("model") or "").strip().lower(),
        "year_min": int(params.get("year_min") or 2018),
        "year_max": int(params.get("year_max") or 2026),
        "mileage_min": int(params.get("mileage_min") or 0),
        "mileage_max": int(params.get("mileage_max") or 300000),
        "owners_min": int(params.get("owners_min") or 1),
        "owners_max": int(params.get("owners_max") or 3),
        "price_min": int(params.get("price_min") or 0),
        "price_max": int(params.get("price_max") or 100000000),
        "transmission": params.get("transmission") or "",
        "fuel": params.get("fuel") or "",
        "drive": params.get("drive") or "",
        "body_type": params.get("body_type") or "",
        "region": params.get("region") or "",
        "buyer_city": params.get("buyer_city") or "",
        "fuel_price": float(params.get("fuel_price") or 62),
    }
    cache_payload = {**filters, "sources": sources, "limit": limit}
    key = _cache_key(cache_payload)
    cached = _cache.get(key)
    if cached and time.time() - cached["ts"] < CACHE_TTL:
        logger.info("SEARCH CACHE HIT")
        return cached["data"]

    errors: List[str] = []
    enriched: List[CarListing] = []

    if "drom" in sources:
        try:
            enriched.extend(_search_drom(filters, limit, errors))
        except Exception as e:
            logger.error(f"DROM SEARCH ERROR: {e}")
            errors.append(f"Drom поиск: {e}")

    if "avito" in sources:
        try:
            enriched.extend(_search_avito(filters, limit, errors))
        except Exception as e:
            logger.error(f"AVITO SEARCH ERROR: {e}")
            errors.append("Avito недоступен")

    if "autoru" in sources:
        try:
            loop = asyncio.new_event_loop()
            try:
                autoru_cars = loop.run_until_complete(_search_autoru(filters, limit, errors))
                enriched.extend(autoru_cars)
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"AUTORU WRAP ERROR: {e}")
            errors.append("Auto.ru недоступен")

    logger.info(f"TOTAL ENRICHED BEFORE FILTERS: {len(enriched)}")
    filtered = [c for c in enriched if apply_filters(c, filters)]
    kept_urls = {(c.url or "").split("?")[0] for c in filtered}
    dropped_autoru = [
        c for c in enriched
        if (c.platform or "").lower() in ("auto_ru", "autoru")
        and (c.url or "").split("?")[0] not in kept_urls
    ]
    if dropped_autoru:
        sample = [(c.price, c.year, c.mileage, c.owners) for c in dropped_autoru[:8]]
        logger.info(f"AUTORU FILTERED OUT {len(dropped_autoru)} e.g. {sample}")
    if not filtered and enriched:
        filtered = enriched
        errors.append("Строгие фильтры не сработали — показана вся выборка")
    filtered = dedup(filtered)
    from collections import Counter
    logger.info(f"BY PLATFORM AFTER FILTERS: {dict(Counter((c.platform or '') for c in filtered))}")
    from app.core.geo import relocation

    buyer = filters.get("buyer_city") or ""
    fuel_price = float(filters.get("fuel_price") or 62)
    for car in filtered:
        car.fuel = car.fuel or ""
        reloc = relocation(
            buyer,
            car.region,
            engine_volume=car.engine_volume or 0,
            fuel=car.fuel or "",
            horsepower=car.horsepower or 0,
            fuel_price=fuel_price,
        )
        car.relocation = reloc
    filtered = score_batch(filtered)
    logger.info(f"TOTAL ENRICHED AFTER FILTERS: {len(filtered)}")
    if not filtered:
        errors.append(
            "Пусто: либо по фильтрам нет лотов (для M3 2018+ до 4,5 млн это часто так), "
            "либо Auto.ru отдал страницу без карточек. Модем вместо Wi‑Fi сам по себе ни при чём — важен IP."
        )

    try:
        from app.database.db import save_listing

        for car in filtered:
            try:
                save_listing(car)
            except Exception as e:
                logger.error(f"DB SAVE ERROR: {e}")
    except Exception as e:
        logger.error(f"DB ERROR: {e}")

    data = {
        "results": [_listing_to_dict(c) for c in filtered],
        "errors": errors,
        "sources_used": sources,
        "filters_applied": filters,
        "brand": filters["brand"],
        "model": filters["model"],
        "total": len(filtered),
        "sample_size": len(filtered),
    }
    _cache[key] = {"ts": time.time(), "data": data}
    LAST_RESULTS.clear()
    LAST_RESULTS.update(data)
    return data


def start_job(params: dict) -> str:
    job_id = uuid.uuid4().hex[:12]
    JOBS[job_id] = {"status": "running", "progress": "Ищем объявления…", "result": None, "error": None}

    def worker():
        try:
            JOBS[job_id]["progress"] = "Парсим Drom…"
            result = run_search(params)
            JOBS[job_id]["status"] = "done"
            JOBS[job_id]["result"] = result
            JOBS[job_id]["progress"] = "Готово"
        except Exception as e:
            logger.exception("JOB FAILED")
            JOBS[job_id]["status"] = "error"
            JOBS[job_id]["error"] = str(e)
            JOBS[job_id]["result"] = {
                "results": [],
                "errors": [str(e)],
                "sources_used": params.get("sources") or ["drom"],
                "filters_applied": params,
                "brand": params.get("brand", ""),
                "model": params.get("model", ""),
                "total": 0,
                "sample_size": 0,
            }

    ThreadPoolExecutor(max_workers=2).submit(worker)
    return job_id


def get_job(job_id: str) -> Optional[dict]:
    return JOBS.get(job_id)
