"""Честный скоринг по текущей выборке, не «рынок РФ»."""
from __future__ import annotations

import statistics
from typing import List, Optional

from app.models.car_listing import CarListing


def dedup(cars: List[CarListing]) -> List[CarListing]:
    seen_urls = set()
    fingerprints = []
    result = []
    for car in cars:
        url = (car.url or "").split("?")[0]
        if url in seen_urls:
            continue
        fp = (
            car.year or 0,
            round((car.mileage or 0) / 1500),
            round((car.price or 0) / 2000),
            (car.brand or "").lower(),
            (car.model or "").lower(),
        )
        if fp in fingerprints and car.price:
            continue
        seen_urls.add(url)
        fingerprints.append(fp)
        result.append(car)
    return result


def apply_filters(car: CarListing, f: dict) -> bool:
    year_min = int(f.get("year_min") or 0)
    year_max = int(f.get("year_max") or 9999)
    if car.year and (car.year < year_min or car.year > year_max):
        return False
    mileage_min = int(f.get("mileage_min") or 0)
    mileage_max = int(f.get("mileage_max") or 10**9)
    if car.mileage and (car.mileage < mileage_min or car.mileage > mileage_max):
        return False
    owners_min = int(f.get("owners_min") or 0)
    owners_max = int(f.get("owners_max") or 99)
    if car.owners is not None and (car.owners < owners_min or car.owners > owners_max):
        return False
    price_min = int(f.get("price_min") or 0)
    price_max = int(f.get("price_max") or 10**12)
    if car.price and (car.price < price_min or car.price > price_max):
        return False

    def match(wanted: Optional[str], actual: Optional[str]) -> bool:
        if not wanted:
            return True
        if not actual:
            return True
        return wanted.lower() == str(actual).lower()

    if not match(f.get("transmission") or None, car.transmission):
        return False
    if not match(f.get("fuel") or None, car.fuel):
        return False
    if not match(f.get("drive") or None, car.drive):
        return False
    if not match(f.get("body_type") or None, car.body_type):
        return False
    region = (f.get("region") or "").lower()
    if region and car.region and region not in str(car.region).lower():
        return False
    return True


def score_batch(cars: List[CarListing]) -> List[CarListing]:
    prices = [c.price for c in cars if c.price and c.price > 0]
    mileages = [c.mileage for c in cars if c.mileage]
    median_price = statistics.median(prices) if prices else 0
    median_mileage = statistics.median(mileages) if mileages else 0

    for car in cars:
        car.market_price = float(median_price or car.price or 0)
        if car.market_price > 0 and car.price:
            car.market_deviation = round(
                (car.market_price - car.price) / car.market_price, 4
            )
        else:
            car.market_deviation = 0.0

        score = 0.5
        if car.market_deviation > 0.15:
            score += 0.2
        elif car.market_deviation > 0.05:
            score += 0.1
        elif car.market_deviation < -0.1:
            score -= 0.15

        if median_mileage and car.mileage:
            if car.mileage < median_mileage * 0.8:
                score += 0.1
            elif car.mileage > median_mileage * 1.3:
                score -= 0.1

        if car.owners is None:
            pass
        elif car.owners <= 1:
            score += 0.1
        elif car.owners >= 3:
            score -= 0.08

        if car.year and car.year >= 2020:
            score += 0.05

        car.liquidity_score = round(max(0.0, min(1.0, score)), 4)
        car.probability_good_deal = car.liquidity_score
        car.market_score = round(car.liquidity_score * 100, 2)

    cars.sort(key=lambda x: x.probability_good_deal or 0, reverse=True)
    return cars
