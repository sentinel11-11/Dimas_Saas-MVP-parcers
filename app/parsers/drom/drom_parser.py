import re

from bs4 import BeautifulSoup

from loguru import logger

from app.parsers.base_parser import BaseParser
from app.utils.http_client import HTTPClient


class DromParser(BaseParser):

    BASE_URL = "https://auto.drom.ru"

    def __init__(self):

        self.client = HTTPClient(min_delay=0.3, max_delay=0.8, retry_count=2)

    def build_url(self, filters):

        brand = filters.get("brand", "").lower()
        model = filters.get("model", "").lower()
        region = (filters.get("region") or "").strip().lower()

        if region:
            url = f"{self.BASE_URL}/{region}/{brand}/{model}/"
        else:
            url = f"{self.BASE_URL}/{brand}/{model}/"

        params = []
        year_min = filters.get("year_min") or filters.get("year_from")
        year_max = filters.get("year_max") or filters.get("year_to")
        price_min = filters.get("price_min") or filters.get("price_from")
        price_max = filters.get("price_max") or filters.get("price_to")
        if year_min:
            params.append(f"minyear={int(year_min)}")
        if year_max:
            params.append(f"maxyear={int(year_max)}")
        if price_min:
            params.append(f"minprice={int(price_min)}")
        if price_max and int(price_max) < 100000000:
            params.append(f"maxprice={int(price_max)}")
        if params:
            url += "?" + "&".join(params)
        return url

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

        # IMAGES - извлечение фотографии
        image_url = None
        img_tag = card.find("img")
        if img_tag:
            image_url = img_tag.get("src") or img_tag.get("data-src")
            if image_url and image_url.startswith("//"):
                image_url = "https:" + image_url

        if not title or not url:
            return None

        return {
            "title": title,
            "price": price,
            "year": year,
            "mileage": mileage,
            "url": url,
            "source": "drom",
            "image_url": image_url
        }