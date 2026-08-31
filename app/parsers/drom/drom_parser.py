import re

from bs4 import BeautifulSoup

from loguru import logger

from app.parsers.base_parser import BaseParser
from app.utils.http_client import HTTPClient


class DromParser(BaseParser):

    BASE_URL = "https://auto.drom.ru"

    def __init__(self):

        self.client = HTTPClient(min_delay=0.3, max_delay=0.8, retry_count=3)

    def build_url(self, filters):

        from app.data.brands import slug_part

        brand = slug_part(filters.get("brand", ""))
        model = slug_part(filters.get("model", ""))
        region = (filters.get("region") or "").strip().lower()

        page = int(filters.get("page") or 1)
        if region:
            url = f"{self.BASE_URL}/{region}/{brand}/{model}/"
        else:
            url = f"{self.BASE_URL}/{brand}/{model}/"
        if page > 1:
            url = url.rstrip("/") + f"/page{page}/"

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
        pages = max(1, min(int(filters.get("drom_pages") or 5), 5))
        seen = set()
        result = []
        for page in range(1, pages + 1):
            payload = dict(filters)
            payload["page"] = page
            url = self.build_url(payload)
            logger.info(f"DROM SEARCH: {url}")
            response = self.client.get(url)
            if not response:
                break
            soup = BeautifulSoup(response.text, "lxml")
            cards = soup.find_all("div", attrs={"data-ftid": "bulls-list_bull"})
            logger.info(f"REAL CARDS page{page}: {len(cards)}")
            if not cards:
                title = (soup.title.string or "").strip() if soup.title else ""
                hint = "не найдено" if "не найден" in response.text.lower() else "нет bulls-list"
                logger.info(f"DROM EMPTY page{page}: {hint}; title={title[:80]!r}")
                break
            for card in cards:
                try:
                    ad = self.parse_card(card)
                    if not ad or ad["url"] in seen:
                        continue
                    seen.add(ad["url"])
                    result.append(ad)
                except Exception as e:
                    logger.error(e)
        logger.info(f"DROM TOTAL UNIQUE: {len(result)}")
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

        # IMAGES
        image_url = self._card_image(card)

        if not title or not url:
            return None

        region = ""
        try:
            from urllib.parse import urlparse
            parts = urlparse(url).path.split("/")
            if len(parts) > 1:
                region = parts[1]
        except Exception:
            pass

        return {
            "title": title,
            "price": price,
            "year": year,
            "mileage": mileage,
            "url": url,
            "source": "drom",
            "image_url": image_url,
            "region": region,
        }

    @staticmethod
    def _card_image(card) -> str:
        skip = ("data:", "placeholder", "no-photo", "nophoto", "stub", "logo", "icon", "1x1", ".svg")
        cands = []
        for img in card.find_all(["img", "source"]):
            for attr in ("src", "data-src", "data-lazy", "data-original", "srcset", "data-srcset"):
                raw = img.get(attr) or ""
                if not raw:
                    continue
                first = raw.split(",")[0].strip().split()[0]
                cands.append(first)
        for tag in card.find_all(style=True):
            m = re.search(r"url\(['\"]?([^'\")]+)['\"]?\)", tag.get("style") or "")
            if m:
                cands.append(m.group(1))
        for raw in cands:
            s = raw.strip()
            if not s or any(x in s.lower() for x in skip):
                continue
            if s.startswith("//"):
                s = "https:" + s
            if s.startswith("http"):
                return s
        return None