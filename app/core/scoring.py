"""Скоринг лотов относительно сопоставимой когорты, не «рынка РФ»."""
from __future__ import annotations

import math
import statistics
from typing import List, Optional, Tuple

from app.models.car_listing import CarListing
from app.core.listing_signals import extract_signals

LIQUID_REGIONS = {
    "moscow", "spb", "khimki", "balashikha", "podolsk", "korolev",
    "mytishchi", "lyubertsy", "krasnogorsk", "odintsovo", "domodedovo",
    "zelenograd", "istra",
}


def dedup(cars: List[CarListing]) -> List[CarListing]:
    seen_urls = set()
    fingerprints = set()
    result = []
    for car in cars:
        url = (car.url or "").split("?")[0]
        if url in seen_urls:
            continue
        fp = (
            (car.platform or "").lower(),
            car.year or 0,
            round((car.mileage or 0) / 1500),
            round((car.price or 0) / 2000),
            (car.brand or "").lower(),
            (car.model or "").lower(),
        )
        if fp in fingerprints and car.price:
            continue
        seen_urls.add(url)
        fingerprints.add(fp)
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


def _robust_median(vals: List[float]) -> float:
    if not vals:
        return 0.0
    m = statistics.median(vals)
    if len(vals) < 4:
        return float(m)
    mad = statistics.median([abs(v - m) for v in vals]) or 1.0
    band = 3.5 * 1.4826 * mad
    kept = [v for v in vals if abs(v - m) <= band]
    return float(statistics.median(kept) if kept else m)


def _peer_key(car: CarListing) -> Tuple:
    year_bin = ((car.year or 0) // 2) * 2
    hp_bin = int(round((car.horsepower or 0) / 40.0) * 40) if car.horsepower else 0
    vol_bin = int(round((car.engine_volume or 0) * 2)) if car.engine_volume else 0
    trans = (car.transmission or "").lower()[:4]
    drive = (car.drive or "").lower()[:6]
    return year_bin, hp_bin, vol_bin, trans, drive


def _peers(car: CarListing, cars: List[CarListing]) -> List[CarListing]:
    key = _peer_key(car)
    same = [c for c in cars if _peer_key(c) == key and c.price]
    if len(same) >= 3:
        return same
    y = car.year or 0
    hp = car.horsepower or 0
    vol = car.engine_volume or 0
    close = [
        c
        for c in cars
        if c.price
        and abs((c.year or 0) - y) <= 2
        and (not hp or not c.horsepower or abs(c.horsepower - hp) <= 40)
        and (not vol or not c.engine_volume or abs((c.engine_volume or 0) - vol) <= 0.3)
    ]
    if len(close) >= 2:
        return close
    return [c for c in cars if c.price and abs((c.year or 0) - y) <= 1] or [car]


def _mileage_factor(car: CarListing, peers: List[CarListing]) -> float:
    miles = [c.mileage for c in peers if c.mileage]
    if not miles or not car.mileage:
        return 1.0
    med = statistics.median(miles)
    # ~0.7% цены за каждые 10 тыс. км относительно медианы когорты
    delta = (car.mileage - med) / 10000.0
    factor = 1.0 - 0.007 * delta
    return max(0.82, min(1.12, factor))


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def score_batch(cars: List[CarListing]) -> List[CarListing]:
    if not cars:
        return cars

    for car in cars:
        peers = _peers(car, cars)
        peer_prices = [c.price for c in peers if c.price]
        raw_median = _robust_median(peer_prices)
        fair = raw_median * _mileage_factor(car, peers)
        reloc = car.relocation or {}
        landed = int(car.price or 0) + int(reloc.get("total") or 0)
        car.market_price = float(round(fair))
        net = fair - landed
        if fair > 0 and car.price:
            car.market_deviation = round(net / fair, 4)
        else:
            car.market_deviation = 0.0
        car.net_vs_market = round(net)
        car.landed_price = landed
        car.peer_size = len(peers)

        deal = _sigmoid(car.market_deviation * 6.0)

        region = str(car.region or "").lower()
        liquidity = 0.55
        if region in LIQUID_REGIONS:
            liquidity += 0.2
        elif reloc.get("distance_km", 0) > 2500:
            liquidity -= 0.12
        if car.owners is None:
            liquidity -= 0.02
        elif car.owners <= 1:
            liquidity += 0.08
        elif car.owners >= 3:
            liquidity -= 0.08
        if car.accidents:
            liquidity -= min(0.15, 0.05 * int(car.accidents))
        miles = [c.mileage for c in peers if c.mileage]
        if miles and car.mileage:
            med_m = statistics.median(miles)
            if car.mileage < med_m * 0.7:
                liquidity += 0.06
            elif car.mileage > med_m * 1.4:
                liquidity -= 0.08

        flags = extract_signals(car, [c.mileage for c in peers if c.mileage])
        for fl in flags:
            liquidity += float(fl.get("delta") or 0)
        car.risk_flags = flags

        suspicious = fair > 0 and car.price and car.price < fair * 0.55
        if suspicious:
            deal = min(deal, 0.42)
            note = "Цена сильно ниже похожих машин — проверьте комплектацию и состояние"
        else:
            note = f"Типичная цена похожих {int(fair):,} ₽ (сравнили {len(peers)})".replace(",", " ")
        if flags:
            note = note + ". " + "; ".join(f["label"] for f in flags[:4])

        car.liquidity_score = round(max(0.05, min(0.98, liquidity)), 4)
        car.probability_good_deal = round(max(0.05, min(0.97, 0.62 * deal + 0.38 * car.liquidity_score)), 4)
        car.market_score = round(car.probability_good_deal * 100, 2)
        car.scoring_note = note
        car.suspicious = suspicious

    cars.sort(
        key=lambda x: (
            x.net_vs_market if getattr(x, "net_vs_market", None) is not None else 0,
            x.probability_good_deal or 0,
        ),
        reverse=True,
    )
    return cars
