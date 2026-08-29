import math


class ProbabilityEngine:

    @staticmethod
    def sigmoid(x):

        return 1 / (
            1 + math.exp(-x)
        )

    @staticmethod
    def calculate(car):

        score = 0

        # цена
        if car.market_score > 80:
            score += 2.0

        elif car.market_score > 60:
            score += 1.0

        # пробег
        if car.mileage < 100000:
            score += 1.5

        elif car.mileage < 180000:
            score += 0.5

        # владельцы
        if car.owners is not None:

            if car.owners <= 2:
                score += 1.2

            elif car.owners <= 4:
                score += 0.5

        # ДТП
        if car.accidents is not None:

            if car.accidents == 0:
                score += 1.5

            elif car.accidents <= 1:
                score += 0.5

        # confidence
        score += car.data_confidence * 2

        probability = (
            ProbabilityEngine.sigmoid(score)
        )

        return round(probability, 3)