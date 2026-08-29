import os


class Config:

    BRAND = os.getenv(
        "BRAND",
        "audi"
    )

    MODEL = os.getenv(
        "MODEL",
        "q3"
    )
    
    # Параметры поиска (для MVP с максимальным функционалом)
    YEAR_MIN = int(os.getenv("YEAR_MIN", "2015"))
    YEAR_MAX = int(os.getenv("YEAR_MAX", "2026"))
    MILEAGE_MIN = int(os.getenv("MILEAGE_MIN", "0"))
    MILEAGE_MAX = int(os.getenv("MILEAGE_MAX", "300000"))
    OWNERS_MIN = int(os.getenv("OWNERS_MIN", "1"))
    OWNERS_MAX = int(os.getenv("OWNERS_MAX", "3"))
    PRICE_MIN = int(os.getenv("PRICE_MIN", "0"))
    PRICE_MAX = int(os.getenv("PRICE_MAX", "100000000"))
    
    TRANSMISSION = os.getenv("TRANSMISSION", None)  # automatic, manual, robot, variator
    FUEL = os.getenv("FUEL", None)  # petrol, diesel, electric, hybrid, gas
    DRIVE = os.getenv("DRIVE", None)  # front, rear, four_wheel
    BODY_TYPE = os.getenv("BODY_TYPE", None)
    REGION = os.getenv("REGION", None)

    REGIONS_PRIORITY = [
        "moscow",
        "spb",
        "novosibirsk",
        "krasnoyarsk",
        "ekaterinburg"
    ]

    SCORE_WEIGHTS = {
        "base_score": 0.6,
        "market_score": 0.4
    }

    MAX_YEAR_DIFF = 3
    MAX_ENGINE_DIFF = 1.0

    MIN_VALID_PRICE = 50_000
    MAX_INVALID_PRICE = 50_000_000

    DEBUG = True

    AVITO_ENABLED = os.getenv("AVITO_ENABLED", "true").lower() == "true"

    REQUEST_DELAY_MIN = 1.5
    REQUEST_DELAY_MAX = 4.5


config = Config()