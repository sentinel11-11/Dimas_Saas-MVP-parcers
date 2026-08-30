import re
import json
import asyncio

from urllib.parse import urlparse

from bs4 import BeautifulSoup
from loguru import logger

from app.utils.http_client import HTTPClient


class DromDetailParser:

    def __init__(self):
        self.client = HTTPClient(min_delay=0.35, max_delay=0.9, retry_count=2)

    async def parse_async(self, url: str):
        """Асинхронная версия парсинга."""
        return await asyncio.to_thread(self.parse, url)

    def parse(self, url: str):

        logger.info(f"DETAIL V5: {url}")

        try:
            r = self.client.get(url)

            if not r:
                return None

            # =========================
            # FIX: HTTPClient may return str OR Response
            # =========================
            if isinstance(r, str):
                html = r
            else:
                html = getattr(r, "text", None) or ""

            if not html:
                return None

            soup = BeautifulSoup(html, "lxml")

            text = soup.get_text(" ", strip=True)

            json_data = self.extract_json_state(html)

            data = {
                "url": url,

                "engine_volume": None,
                "horsepower": None,
                "transmission": None,
                "drive": None,
                "owners": None,
                "vin": None,
                "accidents": None,
                "pts": None,
                "mileage": None,
                "region": None,
                "brand": None,
                "model": None,
                "body_type": None,
                "fuel": None,

                "data_confidence": 0.5
            }

            # JSON parsing
            if json_data:
                parsed_json = self.parse_json(json_data)
                data.update(parsed_json)
                data["data_confidence"] += 0.2

            # DOM parsing
            dom_data = self.parse_dom(soup, text, url)

            for k, v in dom_data.items():
                if data.get(k) is None:
                    data[k] = v

            # normalize
            data = self.normalize(data)

            # confidence
            missing = sum(1 for v in data.values() if v is None)
            data["data_confidence"] = max(0.3, 1 - missing * 0.08)

            return data

        except Exception as e:
            logger.error(f"DETAIL ERROR: {e}")
            return None

    # =========================
    # JSON STATE
    # =========================
    def extract_json_state(self, html: str):

        patterns = [
            r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});',
            r'__INITIAL_STATE__\s*=\s*(\{.*?\});'
        ]

        for p in patterns:
            m = re.search(p, html, re.DOTALL)

            if m:
                try:
                    return json.loads(m.group(1))
                except:
                    continue

        return None

    # =========================
    # JSON PARSER
    # =========================
    def parse_json(self, data):

        result = {}

        try:
            car = data.get("card", {}) or data.get("advert", {})

            result["engine_volume"] = car.get("engine_volume")
            result["horsepower"] = car.get("horsepower")
            result["mileage"] = car.get("mileage")
            result["vin"] = car.get("vin")
            result["owners"] = car.get("owners_count")
            result["accidents"] = car.get("accident_count")

        except:
            pass

        return result

    # =========================
    # DOM PARSER
    # =========================
    def parse_dom(self, soup, text, url):

        return {
            "engine_volume": self.extract_engine(text),
            "horsepower": self.extract_hp(text),
            "transmission": self.extract_transmission(text),
            "drive": self.extract_drive(text),
            "owners": self.extract_owners(text),
            "vin": self.extract_vin(text),
            "accidents": self.extract_accidents(text),
            "pts": self.extract_pts(text),
            "mileage": self.extract_mileage(text),
            "region": self.extract_region(url),
            "brand": self.extract_brand(soup, text),
            "model": self.extract_model(soup, text),
            "body_type": self.extract_body_type(text)
        }

    # =========================
    # NORMALIZATION
    # =========================
    def normalize(self, d):

        # engine - ensure float with default
        if isinstance(d.get("engine_volume"), str):
            try:
                d["engine_volume"] = float(d["engine_volume"].replace(",", "."))
            except:
                d["engine_volume"] = 0.0
        elif d.get("engine_volume") is None:
            d["engine_volume"] = 0.0
            
        if d.get("engine_volume") and d["engine_volume"] > 10:
            d["engine_volume"] = 0.0

        # hp sanity - ensure int with default
        if d.get("horsepower"):
            try:
                d["horsepower"] = int(d["horsepower"])
            except:
                d["horsepower"] = 0
        else:
            d["horsepower"] = 0
            
        if d.get("horsepower") and d["horsepower"] > 1500:
            d["horsepower"] = 0

        # mileage sanity
        if d.get("mileage") and d["mileage"] > 2_000_000:
            d["mileage"] = None

        return d

    # =========================
    # EXTRACTORS
    # =========================
    def extract_engine(self, text):
        patterns = [r"(\d\.\d)\s*л(?!\.?\s?с)", r"(\d,\d)\s*л(?!\.?\s?с)"]

        t = text.lower()

        for p in patterns:
            m = re.search(p, t)
            if m:
                try:
                    return float(m.group(1).replace(",", "."))
                except:
                    pass

        return None

    def extract_hp(self, text):
        m = re.search(r"(\d{2,4})\s*л\.?\s?с", text.lower())
        return int(m.group(1)) if m else None

    def extract_transmission(self, text):

        t = text.lower()

        mapping = {
            "автомат": "AT",
            "акпп": "AT",
            "робот": "AMT",
            "вариатор": "CVT",
            "механика": "MT"
        }

        for k, v in mapping.items():
            if k in t:
                return v

        return None

    def extract_drive(self, text):

        t = text.lower()

        if "полный" in t:
            return "AWD"
        if "задний" in t:
            return "RWD"
        if "передний" in t:
            return "FWD"

        return None

    def extract_owners(self, text):

        m = re.search(r"(\d+)\s*влад", text.lower())
        return int(m.group(1)) if m else None

    def extract_vin(self, text):

        m = re.search(r"\b[A-HJ-NPR-Z0-9]{17}\b", text)
        return m.group(0) if m else None

    def extract_accidents(self, text):

        t = text.lower()

        if "дтп не было" in t:
            return 0

        m = re.search(r"(\d+)\s*дтп", t)
        return int(m.group(1)) if m else None

    def extract_pts(self, text):

        t = text.lower()

        if "оригинал птс" in t:
            return "original"
        if "дубликат" in t:
            return "duplicate"

        return None

    def extract_mileage(self, text):

        m = re.search(r"([\d\s\xa0]+)\s*км", text.lower())

        if not m:
            return None

        digits = re.sub(r"\D", "", m.group(1))

        return int(digits) if digits else None

    def extract_region(self, url):

        try:
            path = urlparse(url).path
            parts = path.split("/")

            if len(parts) > 1:
                return parts[1]

        except:
            pass

        return None

    def extract_brand(self, soup, text):
        # Try to get brand from title or h1
        title = soup.find("h1") or soup.find("title")
        if title:
            title_text = title.get_text(" ", strip=True)
            # Drom titles usually start with brand
            parts = title_text.split()
            if parts:
                return parts[0].strip().rstrip(",")
        return None

    def extract_model(self, soup, text):
        # Try to get model from title or h1
        title = soup.find("h1") or soup.find("title")
        if title:
            title_text = title.get_text(" ", strip=True)
            parts = title_text.split()
            if len(parts) >= 2:
                return parts[1].strip().rstrip(",")
        return None

    def extract_fuel(self, text):
        t = text.lower()
        if "дизель" in t:
            return "diesel"
        if "гибрид" in t:
            return "hybrid"
        if "электро" in t:
            return "electric"
        if "гбо" in t or "газ" in t:
            return "gas"
        if "бензин" in t:
            return "petrol"
        return None

    def extract_body_type(self, text):
        body_types = ["седан", "хэтчбек", "универсал", "внедорожник", "купе", 
                      "кабриолет", "родстер", "пикап", "минивэн", "фургон", 
                      "лифтбек", "тарга", "спидстер"]
        t = text.lower()
        for bt in body_types:
            if bt in t:
                return bt
        return None