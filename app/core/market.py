import statistics
import math


class MarketEngine:

    def __init__(self, ads):

        self.ads = ads

    # =========================================
    # SIMILARITY SCORE
    # =========================================

    def similarity_score(
        self,
        ad,
        target
    ):

        score = 0

        # ---------------------------------
        # YEAR
        # ---------------------------------

        year_diff = abs(
            ad.get("year", 0)
            - target.get("year", 0)
        )

        if year_diff <= 1:
            score += 35

        elif year_diff <= 2:
            score += 20

        elif year_diff <= 3:
            score += 10

        # ---------------------------------
        # ENGINE
        # ---------------------------------

        engine_diff = abs(
            float(ad.get("engine_volume") or 0)
            - float(
                target.get("engine_volume") or 0
            )
        )

        if engine_diff <= 0.3:
            score += 20

        elif engine_diff <= 0.7:
            score += 10

        # ---------------------------------
        # MILEAGE
        # ---------------------------------

        mileage_diff = abs(
            int(ad.get("mileage") or 0)
            - int(target.get("mileage") or 0)
        )

        if mileage_diff <= 30000:
            score += 20

        elif mileage_diff <= 70000:
            score += 10

        # ---------------------------------
        # REGION
        # ---------------------------------

        if ad.get("region") == target.get("region"):
            score += 10

        # ---------------------------------
        # OWNERS
        # ---------------------------------

        owners = ad.get("owners") or 0

        if owners <= 2:
            score += 10

        elif owners <= 4:
            score += 5

        return score

    # =========================================
    # COMPARABLES
    # =========================================

    def find_comparables(self, target_ad):

        comparables = []

        for ad in self.ads:

            if ad["url"] == target_ad["url"]:
                continue

            # same brand/model
            if (
                ad.get("brand")
                != target_ad.get("brand")
            ):
                continue

            if (
                ad.get("model")
                != target_ad.get("model")
            ):
                continue

            similarity = self.similarity_score(
                ad,
                target_ad
            )

            if similarity < 25:
                continue

            ad["similarity"] = similarity

            comparables.append(ad)

        comparables.sort(
            key=lambda x: x["similarity"],
            reverse=True
        )

        return comparables[:20]

    # =========================================
    # MARKET PRICE
    # =========================================

    def calculate_market_price(
        self,
        comparables
    ):

        prices = []

        for ad in comparables:

            price = ad.get("price")

            if price and price > 0:
                prices.append(price)

        if not prices:
            return None

        # robust median
        return statistics.median(prices)

    # =========================================
    # DEVIATION
    # =========================================

    def calculate_deviation(
        self,
        real_price,
        market_price
    ):

        if not market_price:
            return 0

        return round(
            (
                market_price - real_price
            ) / market_price,
            4
        )

    # =========================================
    # PRICE SCORE
    # =========================================

    def price_score(self, target_ad):

        comparables = self.find_comparables(
            target_ad
        )

        if len(comparables) < 3:
            return 50

        market_price = self.calculate_market_price(
            comparables
        )

        if not market_price:
            return 50

        target_price = target_ad.get("price")

        if not target_price:
            return 50

        diff_percent = (
            (
                market_price - target_price
            )
            / market_price
        ) * 100

        # ---------------------------------
        # UNDERVALUED
        # ---------------------------------

        if diff_percent >= 35:
            return 99

        elif diff_percent >= 25:
            return 95

        elif diff_percent >= 15:
            return 88

        elif diff_percent >= 10:
            return 80

        # ---------------------------------
        # FAIR PRICE
        # ---------------------------------

        elif diff_percent >= 0:
            return 70

        # ---------------------------------
        # OVERPRICED
        # ---------------------------------

        elif diff_percent >= -10:
            return 55

        elif diff_percent >= -20:
            return 40

        return 20

    # =========================================
    # MARKET LIQUIDITY
    # =========================================

    def liquidity_score(self, ad):

        score = 50

        # fresh cars
        if ad.get("year", 0) >= 2020:
            score += 20

        elif ad.get("year", 0) >= 2016:
            score += 10

        # mileage
        mileage = ad.get("mileage") or 0

        if mileage <= 100000:
            score += 15

        elif mileage <= 180000:
            score += 7

        # owners
        owners = ad.get("owners") or 0

        if owners <= 2:
            score += 10

        elif owners <= 4:
            score += 5

        # region bonus
        if ad.get("region") in [
            "moscow",
            "spb",
            "ekaterinburg",
            "novosibirsk"
        ]:
            score += 10

        return min(score, 100)