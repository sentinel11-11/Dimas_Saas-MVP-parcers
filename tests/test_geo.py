from app.core.geo import haversine_km, relocation, estimate_l_per_100
from app.data.geo_cities import COORDS, regions_for_ui


def test_cities_cover_capitals():
    ui = regions_for_ui()
    assert len(ui) > 80
    assert "moscow" in COORDS and "spb" in COORDS


def test_moscow_spb_distance_sane():
    d = haversine_km(COORDS["moscow"], COORDS["spb"])
    assert 600 < d < 750


def test_relocation_cheaper_example():
    r = relocation("moscow", "spb", engine_volume=2.0, fuel="petrol")
    assert r["distance_km"] > 600
    assert r["total"] > 0
    assert r["driver_cost"] == 0
    assert r["total"] == r["fuel_cost"] + r["ferry_cost"]
    assert r["total"] < 400_000  # не миллион за перегон легкового


def test_same_city_zero():
    r = relocation("moscow", "moscow")
    assert r["total"] == 0


def test_consumption_diesel_lower():
    assert estimate_l_per_100(2.0, "diesel") < estimate_l_per_100(2.0, "petrol")


def test_fuel_price_scales_cost():
    cheap = relocation("moscow", "spb", engine_volume=2.0, fuel="petrol", fuel_price=50)
    dear = relocation("moscow", "spb", engine_volume=2.0, fuel="petrol", fuel_price=100)
    assert dear["fuel_cost"] > cheap["fuel_cost"]
    assert abs(dear["fuel_cost"] - cheap["fuel_cost"] * 2) < 5
