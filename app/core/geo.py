"""Расстояние и оценка перегона (только топливо + паром ДВ)."""
from __future__ import annotations

import math
from typing import Optional, Tuple

from app.data.geo_cities import COORDS, LABELS

FUEL_RUB_PER_LITER = 62.0
DRIVER_RUB_PER_KM = 0.0
ROAD_FACTOR = 1.25
FERRY_CITIES = {
    "yuzhno-sakhalinsk": 85000,
    "petropavlovsk-kamchatsky": 120000,
    "anadyr": 150000,
    "magadan": 90000,
}


def infer_fuel(fuel: Optional[str], engine_volume: float = 0, horsepower: int = 0) -> str:
    """Drom часто пишет electric на бензиновые M3/M4 из-за селектора."""
    raw = (fuel or "").strip().lower()
    ice = engine_volume >= 0.8 or horsepower >= 70
    if raw in ("electric", "электро") and ice:
        return "petrol"
    if raw in ("petrol", "бензин", "gasoline", "diesel", "дизель", "hybrid", "гибрид", "gas", "газ"):
        if raw in ("бензин", "gasoline"):
            return "petrol"
        if raw == "дизель":
            return "diesel"
        if raw == "гибрид":
            return "hybrid"
        if raw in ("газ",):
            return "gas"
        return raw
    if ice:
        return "petrol"
    if raw in ("electric", "электро"):
        return "electric"
    return "petrol"


ALIASES = {
    "arhangelsk": "arkhangelsk",
    "salehard": "salekhard",
    "uhta": "ukhta",
    "ukhta": "ukhta",
    "belokuriha": "belokurikha",
    "goryachiy-kluch": "goryachiy-klyuch",
    "goryachiy-klyuch": "goryachiy-klyuch",
    "togliatti": "tolyatti",
    "tolyatti": "tolyatti",
    "rasskazovka": "moscow",
    "kommunarka": "moscow",
    "butovo": "moscow",
    "mitino": "moscow",
    "kapotnya": "moscow",
}


def _lookup(slug: Optional[str]) -> Optional[Tuple[float, float]]:
    if not slug:
        return None
    raw = str(slug).strip()
    first = raw.split(",")[0].strip()
    candidates = [raw, first, first.replace("ё", "е")]
    for cand in candidates:
        key = cand.lower().replace(" ", "-")
        key = ALIASES.get(key, key)
        if key in COORDS:
            return COORDS[key]
        for s, label in LABELS.items():
            if label.lower() == cand.lower():
                return COORDS.get(s)
    lowered = raw.lower()
    for hint, slug in (
        ("мкад", "moscow"),
        ("рассказовка", "moscow"),
        ("коммунарка", "moscow"),
        ("московская область", "moscow"),
    ):
        if hint in lowered:
            return COORDS.get(slug)
    if "беларусь" in lowered or "белоруссия" in lowered:
        return COORDS.get("minsk")
    best = None
    best_len = 0
    for s, label in LABELS.items():
        name = label.lower()
        if name and len(name) >= 4 and name in lowered and len(name) > best_len:
            best = COORDS.get(s)
            best_len = len(name)
    return best


def haversine_km(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    r = 6371.0
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def estimate_l_per_100(engine_volume: float = 0, fuel: Optional[str] = None, horsepower: int = 0) -> float:
    fuel = infer_fuel(fuel, engine_volume, horsepower)
    if fuel == "electric":
        return 0.0
    vol = engine_volume or 1.6
    hp = horsepower or 0
    if fuel == "diesel":
        base = 4.8 + vol * 1.8
    elif fuel == "hybrid":
        base = 4.2 + vol * 1.1
    elif fuel == "gas":
        base = 8.0 + vol * 2.0
    else:
        base = 6.2 + vol * 2.2
    if hp > 200:
        base += (hp - 200) / 180.0
    if hp > 400:
        base += 1.2
    return round(max(5.0, min(base, 22.0)), 1)


def place_label(raw: Optional[str]) -> str:
    if not raw:
        return ""
    text = str(raw).strip()
    first = text.split(",")[0].strip()
    key = first.lower().replace(" ", "-").replace("ё", "е")
    key = ALIASES.get(key, key)
    if key in LABELS:
        return LABELS[key]
    for _s, label in LABELS.items():
        if label.lower() == first.lower():
            return label
    return text


def relocation(
    buyer_city: str,
    listing_region: str,
    engine_volume: float = 0,
    fuel: str = "",
    horsepower: int = 0,
    fuel_price: float = None,
) -> dict:
    origin = _lookup(listing_region)
    dest = _lookup(buyer_city)
    l100 = estimate_l_per_100(engine_volume, fuel, horsepower)
    empty = {
        "distance_km": 0,
        "fuel_l_100": l100,
        "fuel_cost": 0,
        "driver_cost": 0,
        "ferry_cost": 0,
        "total": 0,
        "same_city": True,
        "from_label": listing_region,
        "to_label": buyer_city,
        "unknown": False,
        "fuel_price": FUEL_RUB_PER_LITER if fuel_price is None else float(fuel_price),
    }
    if not origin or not dest or not buyer_city:
        empty["same_city"] = False
        empty["unknown"] = True
        return empty
    if origin == dest:
        return empty
    dist = round(haversine_km(origin, dest) * ROAD_FACTOR)
    liters = dist / 100.0 * l100
    price_l = FUEL_RUB_PER_LITER if fuel_price is None else float(fuel_price)
    price_l = max(30.0, min(price_l, 250.0))
    fuel_cost = round(liters * price_l)
    driver = 0
    region_key = str(listing_region).strip().split(",")[0].strip().lower()
    ferry = FERRY_CITIES.get(region_key.replace(" ", "-"), 0)
    from_lab = place_label(listing_region) or listing_region
    to_lab = place_label(buyer_city) or buyer_city
    return {
        "distance_km": dist,
        "fuel_l_100": l100,
        "fuel_cost": fuel_cost,
        "driver_cost": 0,
        "ferry_cost": ferry,
        "total": fuel_cost + ferry,
        "same_city": False,
        "from_label": from_lab,
        "to_label": to_lab,
        "fuel_price": price_l,
        "unknown": False,
    }
