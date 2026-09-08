from app.core.scoring import apply_filters, dedup, score_batch
from app.models.car_listing import CarListing


def _car(**kw):
    base = dict(
        url="https://example.com/a",
        title="Audi Q3",
        platform="drom",
        price=2000000,
        year=2020,
        mileage=50000,
        fuel="petrol",
        transmission="automatic",
        drive="four_wheel",
        owners=1,
        region="moscow",
    )
    base.update(kw)
    return CarListing(**base)


def test_carlisting_has_fuel_and_deviation():
    c = _car()
    assert c.fuel == "petrol"
    assert c.market_deviation == 0
    d = {
        "title": c.title,
        "fuel": c.fuel,
        "market_deviation": c.market_deviation,
    }
    assert d["fuel"] == "petrol"


def test_filters_year():
    c = _car(year=2015)
    assert apply_filters(c, {"year_min": 2018, "year_max": 2026}) is False
    assert apply_filters(_car(year=2020), {"year_min": 2018, "year_max": 2026}) is True


def test_dedup_by_url():
    a = _car(url="https://x/1")
    b = _car(url="https://x/1?utm=1", price=2100000)
    out = dedup([a, b])
    assert len(out) == 1


def test_score_batch_orders_cheaper_first():
    cheap = _car(url="https://x/cheap", price=1500000)
    dear = _car(url="https://x/dear", price=2500000)
    scored = score_batch([dear, cheap])
    assert scored[0].url.endswith("cheap")
