"""Расстояние и оценка перегона (топливо + работа водителя)."""
from __future__ import annotations

import math
from typing import Optional, Tuple

from app.data.geo_cities import COORDS, LABELS

FUEL_RUB_PER_LITER = 62.0
DRIVER_RUB_PER_KM = 12.0
ROAD_FACTOR = 1.25  # прямая vs дорога


def _lookup(slug: Optional[str]) -> Optional[Tuple[float, float]]:
    if not slug:
        return None
    key = str(slug).strip().lower()
    if key in COORDS:
        return COORDS[key]
    for s, (lat, lon) in COORDS.items():
        if key in s or s in key:
            return (lat, lon)
        if LABELS.get(s, "").lower() == key:
            return (lat, lon)
    return None


def haversine_km(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    r = 6371.0
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def estimate_l_per_100(engine_volume: float = 0, fuel: Optional[str] = None, horsepower: int = 0) -> float:
    fuel = (fuel or "petrol").lower()
    if fuel in ("electric", "электро"):
        return 0.0
    vol = engine_volume or 1.6
    if fuel in ("diesel", "дизель"):
        base = 5.0 + vol * 2.0
    elif fuel in ("hybrid", "гибрид"):
        base = 4.5 + vol * 1.2
    else:
        base = 6.5 + vol * 2.4
    if horsepower and horsepower > 250:
        base += 1.5
    return round(max(4.0, min(base, 18.0)), 1)


def relocation(buyer_city: str, listing_region: str, engine_volume: float = 0, fuel: str = "", horsepower: int = 0) -> dict:
    origin = _lookup(listing_region)
    dest = _lookup(buyer_city)
    if not origin or not dest or not buyer_city:
        return {
            "distance_km": 0,
            "fuel_l_100": estimate_l_per_100(engine_volume, fuel, horsepower),
            "fuel_cost": 0,
            "driver_cost": 0,
            "total": 0,
            "same_city": True,
        }
    if origin == dest:
        return {
            "distance_km": 0,
            "fuel_l_100": estimate_l_per_100(engine_volume, fuel, horsepower),
            "fuel_cost": 0,
            "driver_cost": 0,
            "total": 0,
            "same_city": True,
        }
    dist = round(haversine_km(origin, dest) * ROAD_FACTOR)
    l100 = estimate_l_per_100(engine_volume, fuel, horsepower)
    liters = dist / 100.0 * l100
    fuel_cost = round(liters * FUEL_RUB_PER_LITER)
    driver = round(dist * DRIVER_RUB_PER_KM)
    return {
        "distance_km": dist,
        "fuel_l_100": l100,
        "fuel_cost": fuel_cost,
        "driver_cost": driver,
        "total": fuel_cost + driver,
        "same_city": False,
        "from_label": LABELS.get(str(listing_region).lower(), listing_region),
        "to_label": LABELS.get(str(buyer_city).lower(), buyer_city),
    }
