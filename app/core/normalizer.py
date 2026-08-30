from typing import Any, Dict, Optional

from app.core.geo import infer_fuel


TRANSMISSION_ALIASES = {
    "automatic": "automatic",
    "автомат": "automatic",
    "акпп": "automatic",
    "at": "automatic",
    "manual": "manual",
    "механика": "manual",
    "мкпп": "manual",
    "mt": "manual",
    "robot": "robot",
    "робот": "robot",
    "amt": "robot",
    "dct": "robot",
    "variator": "variator",
    "вариатор": "variator",
    "cvt": "variator",
}

FUEL_ALIASES = {
    "petrol": "petrol",
    "бензин": "petrol",
    "gasoline": "petrol",
    "diesel": "diesel",
    "дизель": "diesel",
    "electric": "electric",
    "электро": "electric",
    "hybrid": "hybrid",
    "гибрид": "hybrid",
    "gas": "gas",
    "газ": "gas",
    "гбо": "gas",
}

DRIVE_ALIASES = {
    "front": "front",
    "передний": "front",
    "fwd": "front",
    "rear": "rear",
    "задний": "rear",
    "rwd": "rear",
    "four_wheel": "four_wheel",
    "полный": "four_wheel",
    "awd": "four_wheel",
    "4wd": "four_wheel",
}

BODY_ALIASES = {
    "sedan": "sedan",
    "седан": "sedan",
    "suv": "suv",
    "внедорожник": "suv",
    "crossover": "crossover",
    "кроссовер": "crossover",
    "hatchback": "hatchback",
    "хэтчбек": "hatchback",
    "wagon": "wagon",
    "универсал": "wagon",
    "coupe": "coupe",
    "купе": "coupe",
    "convertible": "convertible",
    "кабриолет": "convertible",
    "minivan": "minivan",
    "минивэн": "minivan",
}


_LABEL_ONLY = {
    "коробка", "привод", "кузов", "птс", "трансмиссия", "топливо",
    "двигатель", "мощность", "пробег", "год",
}


def _alias(value: Optional[str], mapping: Dict[str, str]) -> Optional[str]:
    if value is None or value == "":
        return None
    key = str(value).strip().lower().split(":")[-1].strip()
    if key in _LABEL_ONLY:
        return None
    return mapping.get(key, key)


class DataNormalizer:
    @staticmethod
    def _parse_price(price_value):
        if isinstance(price_value, (int, float)):
            return int(price_value)
        if not price_value or not isinstance(price_value, str):
            return 0
        digits = "".join(c for c in str(price_value) if c.isdigit() or c == "-")
        return int(digits) if digits else 0

    @staticmethod
    def _to_int(value, default=0):
        if value is None or value == "":
            return default
        if isinstance(value, bool):
            return default
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        digits = "".join(c for c in str(value) if c.isdigit() or c == "-")
        return int(digits) if digits else default

    @staticmethod
    def _to_float(value, default=0.0):
        if value is None or value == "":
            return default
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(str(value).replace(",", "."))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def normalize(ad: Dict[str, Any]) -> Dict[str, Any]:
        fuel_raw = ad.get("fuel") or ad.get("fuel_type")
        normalized = {
            "title": ad.get("title") or "Unknown",
            "url": ad.get("url") or "",
            "brand": ad.get("brand"),
            "model": ad.get("model"),
            "price": DataNormalizer._parse_price(ad.get("price", 0)),
            "year": DataNormalizer._to_int(ad.get("year", 0), 0),
            "mileage": DataNormalizer._to_int(ad.get("mileage", 0), 0)
            if ad.get("mileage") is not None
            else 0,
            "engine_volume": DataNormalizer._to_float(ad.get("engine_volume"), 0.0),
            "horsepower": DataNormalizer._to_int(ad.get("horsepower"), 0),
            "transmission": _alias(ad.get("transmission"), TRANSMISSION_ALIASES) or "",
            "drive": _alias(ad.get("drive"), DRIVE_ALIASES),
            "body_type": _alias(ad.get("body_type"), BODY_ALIASES),
            "fuel": infer_fuel(
                _alias(fuel_raw, FUEL_ALIASES),
                DataNormalizer._to_float(ad.get("engine_volume"), 0.0),
                DataNormalizer._to_int(ad.get("horsepower"), 0),
            ),
            "owners": ad.get("owners"),
            "accidents": ad.get("accidents"),
            "pts": ad.get("pts"),
            "vin": ad.get("vin"),
            "color": ad.get("color"),
            "steering": ad.get("steering"),
            "region": ad.get("region") or "",
            "data_confidence": ad.get("data_confidence", 0.5),
            "platform": ad.get("platform") or ad.get("source") or "",
        }

        if "image_url" in ad:
            normalized["image_url"] = ad["image_url"]
        elif ad.get("photos"):
            photos = ad["photos"]
            normalized["image_url"] = photos[0] if isinstance(photos, list) else photos

        if normalized["owners"] is not None:
            try:
                normalized["owners"] = int(normalized["owners"])
            except (TypeError, ValueError):
                normalized["owners"] = None

        return normalized
