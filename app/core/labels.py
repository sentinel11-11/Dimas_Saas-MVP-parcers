"""Русские подписи для карточек."""
from __future__ import annotations

from app.data.geo_cities import LABELS

FUEL = {
    "petrol": "бензин",
    "diesel": "дизель",
    "electric": "электро",
    "hybrid": "гибрид",
    "gas": "газ",
}
TRANS = {
    "automatic": "автомат",
    "manual": "механика",
    "robot": "робот",
    "variator": "вариатор",
    "at": "автомат",
    "mt": "механика",
    "amt": "робот",
    "cvt": "вариатор",
}
DRIVE = {
    "front": "передний",
    "rear": "задний",
    "four_wheel": "полный",
    "fwd": "передний",
    "rwd": "задний",
    "awd": "полный",
}
BODY = {
    "sedan": "седан",
    "suv": "внедорожник",
    "crossover": "кроссовер",
    "hatchback": "хэтчбек",
    "wagon": "универсал",
    "coupe": "купе",
    "convertible": "кабриолет",
    "minivan": "минивэн",
}
PTS = {"original": "оригинал", "duplicate": "дубликат"}
STEER = {"left": "левый руль", "right": "правый руль"}


def ru(value, mapping: dict) -> str:
    if not value:
        return ""
    key = str(value).strip().lower()
    return mapping.get(key, str(value))


def city(slug: str) -> str:
    if not slug:
        return ""
    key = str(slug).strip().lower()
    return LABELS.get(key, slug)


def money(n) -> str:
    try:
        return f"{int(n):,}".replace(",", " ")
    except (TypeError, ValueError):
        return "0"
