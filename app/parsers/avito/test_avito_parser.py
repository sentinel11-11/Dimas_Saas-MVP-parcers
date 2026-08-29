from bs4 import BeautifulSoup

from app.parsers.avito.avito_parser import AvitoParser
from app.parsers.avito.core.parser_engine import AvitoParserEngine


def test_avito_url():
    url = AvitoParserEngine().build_url(
        {"brand": "bmw", "model": "x5", "region": "moskva"}, 2
    )
    assert "/moskva/avtomobili/bmw/x5/" in url
    assert "p=2" in url


def test_avito_adapter():
    assert AvitoParser().engine is not None


def test_avito_card_normalization():
    html = '''
    <div data-marker="item">
      <h3>BMW X5, 2018</h3>
      <div data-marker="item-price">3 950 000 ₽</div>
      <div>85 000 км</div>
      <a data-marker="item-title" href="/moskva/avtomobili/bmw/x5/123456789">BMW X5</a>
    </div>
    '''
    card = BeautifulSoup(html, "lxml").select_one("div[data-marker='item']")
    item = AvitoParser().parse_card(card)
    assert item["title"] == "BMW X5, 2018"
    assert item["price"] == 3950000
    assert item["year"] == 2018
    assert item["mileage"] == 85000
    assert item["url"].endswith("123456789")
