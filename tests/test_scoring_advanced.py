from app.core.geo import estimate_l_per_100, infer_fuel, relocation
from app.core.scoring import score_batch
from app.models.car_listing import CarListing


def _car(**kw):
    base = dict(
        url="https://example.com/a",
        title="BMW M3",
        platform="drom",
        brand="bmw",
        model="m3",
        price=10000000,
        year=2022,
        mileage=30000,
        engine_volume=3.0,
        horsepower=510,
        fuel="petrol",
        transmission="automatic",
        drive="four_wheel",
        owners=1,
        region="moscow",
    )
    base.update(kw)
    return CarListing(**base)


def test_ice_not_electric():
    assert infer_fuel("electric", 3.0, 510) == "petrol"
    l100 = estimate_l_per_100(3.0, "electric", 510)
    assert l100 >= 10


def test_relocation_has_fuel_for_m3():
    r = relocation("moscow", "krasnodar", 3.0, "electric", 510)
    assert r["fuel_l_100"] > 0
    assert r["fuel_cost"] > 0
    assert r["same_city"] is False


def test_ussuriisk_known():
    r = relocation("moscow", "ussuriisk", 3.0, "petrol", 510)
    assert r["distance_km"] > 6000


def test_sakhalin_ferry():
    r = relocation("moscow", "yuzhno-sakhalinsk", 3.0, "petrol", 510)
    assert r["ferry_cost"] >= 80000


def test_peer_does_not_mix_480_and_new_530():
    cheap = _car(url="https://x/spb", price=5999999, year=2021, horsepower=480, region="spb", mileage=68000)
    mid = _car(url="https://x/m1", price=10250000, year=2022, horsepower=510, region="moscow")
    mid2 = _car(url="https://x/m2", price=10500000, year=2022, horsepower=510, region="saratov")
    new = _car(url="https://x/new", price=15000000, year=2025, horsepower=530, region="barnaul", mileage=7000)
    new2 = _car(url="https://x/new2", price=14990000, year=2025, horsepower=530, region="moscow", mileage=4430)
    for c in (cheap, mid, mid2, new, new2):
        c.relocation = {"total": 0, "same_city": True, "distance_km": 0}
    scored = score_batch([cheap, mid, mid2, new, new2])
    by_url = {c.url: c for c in scored}
    # 2025 не должны считаться «дороже рынка» относительно 6 млн 2021
    assert by_url["https://x/new"].market_price > 12_000_000
    assert by_url["https://x/spb"].market_price < 9_000_000 or by_url["https://x/spb"].suspicious


def test_sort_by_landed_savings():
    far = _car(url="https://x/far", price=8500000, region="krasnodar")
    far.relocation = {"total": 40000, "same_city": False, "distance_km": 1500}
    local = _car(url="https://x/loc", price=8600000, region="moscow")
    local.relocation = {"total": 0, "same_city": True, "distance_km": 0}
    peer = _car(url="https://x/p", price=10500000, region="moscow")
    peer.relocation = {"total": 0, "same_city": True, "distance_km": 0}
    scored = score_batch([far, local, peer])
    assert scored[0].url in ("https://x/far", "https://x/loc")
    assert scored[0].net_vs_market >= scored[-1].net_vs_market
