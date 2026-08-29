import statistics
from collections import defaultdict


class MarketIntelligenceEngine:

    def __init__(self, ads):
        self.ads = ads

        self.by_region = self._group_by_region()

    def _group_by_region(self):

        grouped = defaultdict(list)

        for ad in self.ads:

            region = ad.get("region")

            if region:
                grouped[region].append(ad)

        return grouped

    # =========================
    # 1. MEDIAN PRICE BY REGION
    # =========================
    def region_median(self, region: str):

        prices = [
            ad["price"]
            for ad in self.by_region.get(region, [])
            if ad.get("price")
        ]

        if len(prices) < 3:
            return None

        return statistics.median(prices)

    # =========================
    # 2. LIQUIDITY SCORE
    # =========================
    def liquidity_score(self, ad):

        region = ad.get("region")

        region_ads = self.by_region.get(region, [])

        if len(region_ads) < 5:
            return 50

        prices = [
            a["price"]
            for a in region_ads
            if a.get("price")
        ]

        if not prices:
            return 50

        median_price = statistics.median(prices)

        price = ad.get("price")

        if not price:
            return 50

        deviation = abs(price - median_price) / median_price * 100

        # логика ликвидности
        if deviation < 10:
            return 95
        elif deviation < 20:
            return 80
        elif deviation < 35:
            return 60
        else:
            return 30

    # =========================
    # 3. OVERPRICED / UNDERPRICED INDEX
    # =========================
    def price_index(self, ad):

        region = ad.get("region")

        median = self.region_median(region)

        if not median:
            return 50

        price = ad.get("price")

        if not price:
            return 50

        return (price / median) * 100

    # =========================
    # 4. CROSS REGION OPPORTUNITY (АРБИТРАЖ)
    # =========================
    def arbitrage_score(self, ad):

        price = ad.get("price")
        region = ad.get("region")

        if not price:
            return 0

        best = 0

        for r, ads in self.by_region.items():

            if r == region:
                continue

            prices = [a["price"] for a in ads if a.get("price")]

            if len(prices) < 3:
                continue

            median = statistics.median(prices)

            diff = (median - price) / median * 100

            if diff > best:
                best = diff

        return max(0, min(100, best * 2))
