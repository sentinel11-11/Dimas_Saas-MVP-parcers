class DataNormalizer:

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

        normalized["price"] = int(
            ad.get("price", 0)
        )

        normalized["year"] = int(
            ad.get("year", 0)
        )

        mileage = ad.get("mileage")

        if mileage is None:
            mileage = 0

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