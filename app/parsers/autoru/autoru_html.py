"""Разбор выдачи Auto.ru из HTML (SSR / JSON), без ожидания селекторов Playwright."""
from __future__ import annotations

import json
import re
from html import unescape
from typing import Any, Dict, List
from urllib.parse import unquote

from loguru import logger

SALE_RE = re.compile(
    r"https://auto\.ru/cars/used/sale/[a-z0-9_-]+/[a-z0-9_-]+/\d+[a-z0-9-]+/?",
    re.I,
)
PHOTO_RE = re.compile(
    r"(?:https?:)?//(?:avatars\.(?:mds\.yandex\.net|avto\.ru)|photo\.auto\.ru|[^\s\"'<>]*autoru-vos)[^\s\"'<>]+",
    re.I,
)


def is_blocked(html: str, url: str = "", title: str = "") -> bool:
    u = (url or "").lower()
    t = (title or "").lower()
    h = (html or "")[:2500].lower()
    if "showcaptcha" in u or "showcaptcha" in h:
        return True
    if "робот" in t or "smartcaptcha" in h or "вы не робот" in h:
        return True
    return False


def _photo(chunk: str) -> str:
    found = PHOTO_RE.findall(chunk or "")
    if not found:
        return ""
    u = unescape(found[0]).split(",")[0].split(" ")[0]
    if u.startswith("//"):
        u = "https:" + u
    return u


def _cards_from_json_blob(obj: Any, out: List[Dict[str, Any]], seen: set) -> None:
    if isinstance(obj, dict):
        url = obj.get("url") or ""
        if isinstance(url, str) and "/cars/used/sale/" in url:
            if url.startswith("//"):
                url = "https:" + url
            if url.startswith("/"):
                url = "https://auto.ru" + url
            url = url.split("?")[0]
            if url not in seen:
                seen.add(url)
                price = 0
                pi = obj.get("price_info") or obj.get("price") or {}
                if isinstance(pi, dict):
                    price = pi.get("RUR") or pi.get("price") or 0
                elif isinstance(pi, (int, float)):
                    price = int(pi)
                docs = obj.get("documents") or {}
                state = obj.get("state") or {}
                vi = obj.get("vehicle_info") or {}
                mark = (vi.get("mark_info") or {}).get("name") or ""
                model = (vi.get("model_info") or {}).get("name") or ""
                year = docs.get("year") or 0
                title = f"{mark} {model} {year}".strip()
                loc = ((obj.get("seller") or {}).get("location") or {})
                region = (loc.get("region_info") or {}).get("name") or loc.get("address") or ""
                images = state.get("image_urls") or obj.get("images") or []
                image = ""
                if isinstance(images, list) and images:
                    first = images[0]
                    if isinstance(first, dict):
                        sizes = first.get("sizes") or first
                        image = (
                            sizes.get("456x342")
                            or sizes.get("320x240")
                            or sizes.get("1200x900")
                            or next((v for v in sizes.values() if isinstance(v, str) and "http" in v), "")
                        )
                    elif isinstance(first, str):
                        image = first
                if image.startswith("//"):
                    image = "https:" + image
                tech = vi.get("tech_param") or {}
                bits = []
                if tech.get("displacement"):
                    bits.append(f"{int(tech['displacement']) / 1000:.1f} л")
                if tech.get("power"):
                    bits.append(f"{tech['power']} л.с.")
                trans = {"AUTOMATIC": "автомат", "MECHANICAL": "механика", "ROBOT": "робот", "VARIATOR": "вариатор"}.get(
                    str(tech.get("transmission") or ""), str(tech.get("transmission") or "")
                )
                if trans:
                    bits.append(trans)
                fuel = {"GASOLINE": "бензин", "DIESEL": "дизель", "HYBRID": "гибрид", "ELECTRO": "электро"}.get(
                    str(tech.get("engine_type") or ""), ""
                )
                if fuel:
                    bits.append(fuel)
                drive = {"ALL_WHEEL_DRIVE": "полный", "FORWARD_CONTROL": "передний", "REAR_DRIVE": "задний"}.get(
                    str(tech.get("gear_type") or ""), ""
                )
                if drive:
                    bits.append(drive)
                mileage = state.get("mileage") or obj.get("mileage") or 0
                if mileage:
                    bits.append(f"{mileage} км")
                owners = docs.get("owners_number")
                if owners:
                    bits.append(f"{owners} владел")
                out.append(
                    {
                        "url": url,
                        "title": title,
                        "price": f"{price} ₽" if price else "",
                        "tech": " | ".join(bits),
                        "place": region or "",
                        "text": " ".join([title, str(price), *bits, region]),
                        "image": image,
                        "mileage": f"{mileage} км" if mileage else "",
                    }
                )
        for v in obj.values():
            _cards_from_json_blob(v, out, seen)
    elif isinstance(obj, list):
        for v in obj:
            _cards_from_json_blob(v, out, seen)


def parse_listing_html(html: str) -> List[Dict[str, Any]]:
    if not html:
        return []
    html = unescape(html)
    cards: List[Dict[str, Any]] = []
    seen: set = set()

    for m in re.finditer(r'(?:window\.)?(?:__INITIAL_STATE__|INITIAL_STATE)\s*=\s*(\{.+?\})\s*;\s*</script>', html, re.S):
        raw = m.group(1)
        try:
            _cards_from_json_blob(json.loads(raw), cards, seen)
        except Exception:
            continue
        if cards:
            logger.info(f"AUTO.RU HTML JSON offers: {len(cards)}")
            return cards

    # Куски JSON с offers внутри огромной страницы
    for m in re.finditer(r'"offers"\s*:\s*(\[\{.+?\}\])\s*[,}]', html):
        blob = m.group(1)
        if len(blob) > 2_000_000:
            continue
        try:
            _cards_from_json_blob(json.loads(blob), cards, seen)
        except Exception:
            continue
        if len(cards) >= 8:
            logger.info(f"AUTO.RU HTML offers array: {len(cards)}")
            return cards

    for m in SALE_RE.finditer(html):
        url = m.group(0).rstrip("/").split("?")[0] + "/"
        if url in seen:
            continue
        seen.add(url)
        chunk = html[max(0, m.start() - 800) : min(len(html), m.end() + 1800)]
        title_m = re.search(r">([^<]{8,80})</a>", chunk)
        title = (title_m.group(1).strip() if title_m else "") or url
        price_m = re.search(r"(\d[\d\s\xa0]{4,})\s*₽", chunk)
        cards.append(
            {
                "url": url,
                "title": title,
                "price": (price_m.group(0) if price_m else chunk),
                "tech": chunk,
                "place": "",
                "text": re.sub(r"<[^>]+>", " ", chunk)[:4000],
                "image": _photo(chunk),
            }
        )
    if cards:
        logger.info(f"AUTO.RU HTML sale links: {len(cards)}")
    return attach_photos(html, cards)


def attach_photos(html: str, cards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not cards or not html:
        return cards
    raw = PHOTO_RE.findall(html)
    photos = []
    seen_p = set()
    for u in raw:
        u = unescape(u).split(",")[0].split(" ")[0]
        if u.startswith("//"):
            u = "https:" + u
        if "/32x32" in u or "/120x90" in u:
            continue
        if any(x in u for x in ("marketing", "adfox", "get-verba", "banner")):
            continue
        if u.rstrip("/") in ("https://avatars.avto.ru", "https://avatars.mds.yandex.net"):
            continue
        key = re.sub(r"/\d+x\d+(?:n)?/?$", "", u)
        if key in seen_p:
            continue
        seen_p.add(key)
        if re.search(r"/\d+x\d+(?:n)?/?$", u):
            u = re.sub(r"/\d+x\d+(?:n)?/?$", "/456x342", u)
        photos.append(u)
    if not photos:
        return cards
    i = 0
    for c in cards:
        if c.get("image"):
            continue
        if i < len(photos):
            c["image"] = photos[i]
            i += 1
    filled = sum(1 for c in cards if c.get("image"))
    logger.info(f"AUTO.RU photos attached {filled}/{len(cards)} pool={len(photos)}")
    return cards
