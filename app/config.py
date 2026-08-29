import os


class Config:

    BRAND = os.getenv(
        "BRAND",
        "bmw"
    )

    MODEL = os.getenv(
        "MODEL",
        "x5"
    )

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