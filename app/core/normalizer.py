class DataNormalizer:

    @staticmethod
    def _parse_price(price_value):
        """Парсинг цены из строки формата '2 500 000 ₽' или числа"""
        if isinstance(price_value, (int, float)):
            return int(price_value)
        if not price_value or not isinstance(price_value, str):
            return 0
        # Удаляем все нецифровые символы кроме минус
        digits = ''.join(c for c in str(price_value) if c.isdigit() or c == '-')
        return int(digits) if digits else 0

    @staticmethod
    def normalize(ad):

        normalized = {}

        normalized["title"] = ad.get(
            "title",
            "Unknown"
        )

        normalized["url"] = ad.get(
            "url"
        )

        normalized["brand"] = ad.get(
            "brand"
        )

        normalized["model"] = ad.get(
            "model"
        )

        normalized["price"] = DataNormalizer._parse_price(ad.get("price", 0))

        normalized["year"] = int(
            ad.get("year", 0)
        )

        mileage = ad.get("mileage")

        if mileage is None:
            mileage = 0
        elif isinstance(mileage, str):
            mileage = DataNormalizer._parse_price(mileage)

        normalized["mileage"] = mileage

        normalized["engine_volume"] = ad.get(
            "engine_volume"
        )

        normalized["horsepower"] = ad.get(
            "horsepower"
        )

        normalized["transmission"] = ad.get(
            "transmission"
        )

        normalized["drive"] = ad.get(
            "drive"
        )

        normalized["body_type"] = ad.get(
            "body_type"
        )

        normalized["owners"] = ad.get(
            "owners"
        )

        normalized["accidents"] = ad.get(
            "accidents"
        )

        normalized["pts"] = ad.get(
            "pts"
        )

        normalized["region"] = ad.get(
            "region"
        )

        normalized["data_confidence"] = ad.get(
            "data_confidence",
            0.5
        )

        return normalized