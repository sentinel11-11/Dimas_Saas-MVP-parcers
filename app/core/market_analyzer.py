from statistics import median
import math


class MarketAnalyzer:

    @staticmethod
    def calculate_market_price(cars, target):

        scored = []

        for car in cars:

            # защита
            if not car.get("price"):
                continue

            if (
                car.get("brand") != target.brand
                or car.get("model") != target.model
            ):
                continue

            score = 0

            # -------------------------
            # YEAR
            # -------------------------
            year_diff = abs(
                car.get("year", 0) - target.year
            )

            if year_diff <= 1:
                score += 35

            elif year_diff <= 2:
                score += 20

            elif year_diff <= 3:
                score += 10

            # -------------------------
            # MILEAGE
            # -------------------------
            mileage = car.get("mileage") or 0

            mileage_diff = abs(
                mileage - target.mileage
            )

            if mileage_diff <= 30000:
                score += 25

            elif mileage_diff <= 60000:
                score += 15

            elif mileage_diff <= 100000:
                score += 7

            # -------------------------
            # ENGINE
            # -------------------------
            engine_diff = abs(
                (car.get("engine_volume") or 0)
                - (target.engine_volume or 0)
            )

            if engine_diff <= 0.3:
                score += 15

            elif engine_diff <= 0.7:
                score += 8

            # -------------------------
            # REGION BONUS
            # -------------------------
            if (
                car.get("region")
                == target.region
            ):
                score += 10

            # -------------------------
            # OWNERS
            # -------------------------
            owners = car.get("owners") or 0

            if owners <= 2:
                score += 10

            elif owners <= 4:
                score += 5

            scored.append({
                "price": car["price"],
                "score": score
            })

        # нет похожих
        if not scored:
            return target.price

        # сортируем по похожести
        scored.sort(
            key=lambda x: x["score"],
            reverse=True
        )

        # берем TOP похожих
        top_similar = scored[:15]

        prices = [
            x["price"]
            for x in top_similar
        ]

        return median(prices)

    @staticmethod
    def calculate_market_deviation(
        real_price,
        market_price
    ):

        if market_price <= 0:
            return 0

        return round(
            (
                market_price - real_price
            ) / market_price,
            4
        )

    @staticmethod
    def calculate_liquidity_score(car):

        score = 0.5

        # свежее авто
        if car.year >= 2020:
            score += 0.15

        elif car.year >= 2016:
            score += 0.1

        # пробег
        if car.mileage <= 100000:
            score += 0.15

        elif car.mileage <= 180000:
            score += 0.08

        # владельцы
        owners = car.owners or 0

        if owners <= 2:
            score += 0.1

        elif owners <= 4:
            score += 0.05

        # ДТП
        accidents = car.accidents or 0
        
        if accidents == 0:
            score += 0.1

        # ликвидные регионы
        if car.region in [
            "moscow",
            "spb",
            "ekaterinburg",
            "novosibirsk"
        ]:
            score += 0.1

        return min(
            round(score, 4),
            1.0
        )

    @staticmethod
    def calculate_confidence(car):

        fields = [
            car.year,
            car.price,
            car.mileage,
            car.engine_volume,
            car.owners,
            car.transmission,
            car.drive,
            car.body_type
        ]

        filled = sum(
            1 for x in fields
            if x not in [None, "", 0]
        )

        return round(
            filled / len(fields),
            4
        )

    @staticmethod
    def sigmoid(x):

        return 1 / (
            1 + math.exp(-x)
        )

    @staticmethod
    def calculate_final_probability(car):

        z = 0

        # рынок
        z += car.market_deviation * 3.5

        # ликвидность
        z += car.liquidity_score * 2.0

        # confidence
        z += car.data_confidence * 1.5

        # market score
        z += car.market_score * 2.0

        return round(
            MarketAnalyzer.sigmoid(z),
            4
        )