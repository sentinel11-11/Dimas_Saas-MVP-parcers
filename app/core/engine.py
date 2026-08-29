import math
from collections import defaultdict
from datetime import datetime


class AutoAnalysisEngine:

    def __init__(self, ads: list[dict]):
        self.ads = ads
        self.market_by_region = defaultdict(list)

    # =========================
    # MAIN PIPELINE
    # =========================
    def enrich(self):
        """
        Готовит структуру + группирует рынок по регионам
        """
        for ad in self.ads:

            region = ad.get("region")
            price = ad.get("price")

            if region and price:
                self.market_by_region[region].append(price)

        return self.ads

    def analyze(self, ads: list[dict]):

        enriched = []

        for ad in ads:

            ad = dict(ad)

            ad["liquidity_score"] = self.liquidity_score(ad)
            ad["regional_median"] = self.regional_median(ad)
            ad["transport_cost"] = self.transport_cost(ad)

            ad["market_score"] = self.market_score(ad)
            ad["final_score"] = self.final_score(ad)

            ad["is_overpriced"] = self.detect_overpriced(ad)
            ad["is_liquid"] = ad["liquidity_score"] > 60

            enriched.append(ad)

        return sorted(
            enriched,
            key=lambda x: x["final_score"],
            reverse=True
        )

    # =========================
    # 1. LIQUIDITY SCORE
    # =========================
    def liquidity_score(self, ad):

        region = ad.get("region")
        if not region:
            return 50

        count = len(self.market_by_region.get(region, []))

        # логика насыщения рынка
        if count > 50:
            return 90
        if count > 30:
            return 75
        if count > 15:
            return 60
        if count > 5:
            return 45

        return 30

    # =========================
    # 2. REGIONAL MEDIAN
    # =========================
    def regional_median(self, ad):

        region = ad.get("region")
        price = ad.get("price")

        if not region or not price:
            return None

        prices = self.market_by_region.get(region, [])

        if not prices:
            return price

        sorted_prices = sorted(prices)
        n = len(sorted_prices)

        if n == 0:
            return price

        if n % 2 == 1:
            return sorted_prices[n // 2]

        return (
            sorted_prices[n // 2 - 1] +
            sorted_prices[n // 2]
        ) / 2

    # =========================
    # 3. MARKET SCORE (price deviation)
    # =========================
    def market_score(self, ad):

        price = ad.get("price")
        median = ad.get("regional_median")

        if not price or not median:
            return 50

        diff = (median - price) / median * 100

        if diff >= 30:
            return 100
        if diff >= 20:
            return 90
        if diff >= 10:
            return 80
        if diff >= 0:
            return 70
        if diff >= -10:
            return 60
        if diff >= -20:
            return 40

        return 20
    def transport_cost(self, ad):

        """
        Реальная модель:
        - топливо
        - амортизация
        - расстояние между регионами (proxy)
        """

        region = ad.get("region")

        distance_map = {
            "moscow": 0,
            "spb": 700,
            "novosibirsk": 3300,
            "krasnoyarsk": 4100,
            "chelyabinsk": 1800,
            "tyumen": 2100,
            "ulyanovsk": 900
        }

        distance = distance_map.get(region, 1500)

        fuel_price = 60  # ₽/литр (среднее)
        consumption = 10  # л/100км

        fuel_cost = (distance / 100) * consumption * fuel_price

        amortization = distance * 3  # ₽/км (износ, риск, логистика)

        driver_fee = 15000  # средний перегонщик

        return fuel_cost + amortization + driver_fee

    def detect_overpriced(self, ad):

        price = ad.get("price")
        median = ad.get("regional_median")

        if not price or not median:
            return False

        return price > median * 1.2


    def final_score(self, ad):

        base = 0


        base += ad.get("market_score", 50) * 0.4


        base += ad.get("liquidity_score", 50) * 0.2

        base += 30


        transport_penalty = ad.get("transport_cost", 0) / 1000

        base -= transport_penalty

        # бонус за адекватность
        if not ad.get("is_overpriced"):
            base += 10

        return max(0, min(100, base))