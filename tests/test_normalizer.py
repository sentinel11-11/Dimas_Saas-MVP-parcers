from app.core.normalizer import DataNormalizer


def test_normalize_price_and_fuel():
    ad = {
        "title": "Audi Q3",
        "url": "https://example.com/1",
        "price": "2 500 000 ₽",
        "year": "2019",
        "mileage": "45 000 км",
        "fuel_type": "бензин",
        "transmission": "автомат",
        "drive": "полный",
        "source": "drom",
    }
    n = DataNormalizer.normalize(ad)
    assert n["price"] == 2500000
    assert n["year"] == 2019
    assert n["mileage"] == 45000
    assert n["fuel"] == "petrol"
    assert n["transmission"] == "automatic"
    assert n["drive"] == "four_wheel"
    assert n["platform"] == "drom"


def test_missing_fields_do_not_crash():
    n = DataNormalizer.normalize({"title": "x", "url": "u"})
    assert n["price"] == 0
    assert n["engine_volume"] == 0.0
    assert n["fuel"] is None
