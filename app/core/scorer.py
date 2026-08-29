from datetime import datetime


class CarScorer:

    @staticmethod
    def calculate(ad: dict):

        score = 100

        year = ad.get("year")
        mileage = ad.get("mileage")
        price = ad.get("price")

        current_year = datetime.now().year

        if year:

            age = current_year - year

            if age <= 3:
                score += 10
            elif age >= 15:
                score -= 20

        if mileage and year:

            age = max(current_year - year, 1)

            yearly = mileage / age

            if yearly < 10000:
                score += 15
            elif yearly > 30000:
                score -= 20

        if price and year:

            base_price = (current_year - year) * 300000 + 500000

            if price < base_price * 0.5:
                score -= 25

            elif price > base_price * 1.5:
                score -= 10

        if mileage and mileage < 5000:
            score -= 10

        return max(0, min(100, score))