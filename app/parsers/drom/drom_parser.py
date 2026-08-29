import re

from bs4 import BeautifulSoup

from loguru import logger

from app.parsers.base_parser import BaseParser
from app.utils.http_client import HTTPClient


class DromParser(BaseParser):

    BASE_URL = "https://auto.drom.ru"

    def __init__(self):

        self.client = HTTPClient()

    def build_url(self, filters):

        brand = filters.get("brand", "").lower()

        model = filters.get("model", "").lower()

        return (
            f"{self.BASE_URL}/"
            f"{brand}/"
            f"{model}/"
        )

    def search(self, filters):

        url = self.build_url(filters)

        logger.info(f"DROM SEARCH: {url}")

        response = self.client.get(url)

        if not response:
            return []

        html = response.text

        soup = BeautifulSoup(
            html,
            "lxml"
        )

        cards = soup.find_all(
            "div",
            attrs={
                "data-ftid": "bulls-list_bull"
            }
        )

        logger.info(f"REAL CARDS: {len(cards)}")

        result = []

        for card in cards:

            try:

                ad = self.parse_card(card)

                if ad:
                    result.append(ad)

            except Exception as e:

                logger.error(e)

        return result

    def parse_card(self, card):

        title = ""

        title_tag = card.find(
            attrs={
                "data-ftid": "bull_title"
            }
        )

        if title_tag:

            title = title_tag.text.strip()

        # PRICE
        price = 0

        price_tag = card.find(
            attrs={
                "data-ftid": "bull_price"
            }
        )

        if price_tag:

            digits = re.sub(
                r"\D",
                "",
                price_tag.text
            )

            if digits:
                price = int(digits)

        # URL
        url = ""

        link_tag = card.find("a", href=True)

        if link_tag:

            url = link_tag["href"]

        # YEAR
        year = None

        year_match = re.search(
            r"(19\d{2}|20\d{2})",
            title
        )

        if year_match:

            year = int(year_match.group(1))

        # MILEAGE
        mileage = None

        mileage_match = re.search(
            r"(\d[\d\s]+)\s?км",
            card.text
        )

        if mileage_match:

            digits = re.sub(
                r"\D",
                "",
                mileage_match.group(1)
            )

            if digits:
                mileage = int(digits)

        if not title or not url:
            return None

        return {
            "title": title,
            "price": price,
            "year": year,
            "mileage": mileage,
            "url": url,
            "source": "drom"
        }