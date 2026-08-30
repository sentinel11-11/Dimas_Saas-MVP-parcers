import re
import random
import time
from pathlib import Path
from urllib.parse import urljoin,urlencode
from bs4 import BeautifulSoup
from loguru import logger
from app.parsers.avito.config import config
from app.parsers.avito.http.client import AvitoHttpClient
from app.parsers.avito.models import AvitoListing
from app.parsers.avito.normalizer import digits
from app.parsers.avito.selectors import CARD,LINK,PRICE,TITLE,IMAGE,PARAMS
class AvitoParserEngine:
    def __init__(self, client=None, proxy_list=None):
        self.client = client or AvitoHttpClient(config.request_timeout, proxy_list)
    def build_url(self,filters,page=1):
        brand=str(filters.get("brand") or "").strip().lower(); model=str(filters.get("model") or "").strip().lower(); region=str(filters.get("region") or filters.get("target_region") or "rossiya").strip().lower()
        path=f"/{region}/avtomobili/" + ((brand+"/"+model+"/") if brand and model else (brand+"/") if brand else "")
        return "https://www.avito.ru"+path+("?"+urlencode({"p":page}) if page>1 else "")
    def search(self,filters):
        limit=min(int(filters.get("limit") or config.search_limit),1000); results=[]; seen=set(); max_pages=max(1,min(config.max_pages,(limit+9)//10))
        for page in range(1,max_pages+1):
            if len(results)>=limit: break
            url=self.build_url(filters,page); logger.info("AVITO SEARCH: {}",url); response=self.client.get(url)
            if not response: 
                logger.warning("AVITO: No response received")
                continue
            if response.status_code==429:
                logger.error("AVITO: Rate limit exceeded, waiting 60 seconds...")
                time.sleep(60)
                # Повторная попытка с новым User-Agent
                self.client.session.headers["User-Agent"] = random.choice(self.client.user_agents)
                response=self.client.get(url)
            if not response or response.status_code!=200: 
                logger.warning("AVITO: Bad status code {}", response.status_code if response else "None")
                continue
            if config.save_debug_html:
                p=Path("data")/f"avito_debug_{page}.html"; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(response.text,encoding="utf-8")
            soup=BeautifulSoup(response.text,"lxml"); cards=self._find_cards(soup); logger.info("AVITO CARDS page={} count={}",page,len(cards))
            if not cards: break
            for card in cards:
                item=self.parse_card(card,filters)
                if not item or not item.get("url"): continue
                key=item.get("external_id") or item["url"]
                if key in seen: continue
                seen.add(key); results.append(item)
                if len(results)>=limit: break
        logger.info("AVITO FOUND: {}",len(results)); return results
    def _find_cards(self,soup):
        for selector in CARD:
            cards=soup.select(selector)
            if cards:return cards
        return []
    @staticmethod
    def _first_text(node,selectors):
        for selector in selectors:
            found=node.select_one(selector)
            if found:return found.get_text(" ",strip=True)
        return ""
    @staticmethod
    def _first_href(node,selectors):
        for selector in selectors:
            found=node.select_one(selector)
            if found and found.get("href"):return urljoin("https://www.avito.ru",found["href"])
        return ""
    
    @staticmethod
    def _first_image(node, selectors):
        """Извлечь URL изображения"""
        for selector in selectors:
            found = node.select_one(selector)
            if found:
                img_src = found.get("src") or found.get("data-src")
                if img_src:
                    if img_src.startswith("//"):
                        img_src = "https:" + img_src
                    elif not img_src.startswith("http"):
                        img_src = urljoin("https://www.avito.ru", img_src)
                    return img_src
        return None
    
    def parse_card(self,card,filters=None):
        filters=filters or {}; title=self._first_text(card,TITLE); url=self._first_href(card,LINK)
        if not title or not url:return None
        text=card.get_text(" ",strip=True); price=digits(self._first_text(card,PRICE)); ym=re.search(r"\b(19\d{2}|20\d{2})\b",title+" "+text); mm=re.search(r"([\d\s]{3,})\s*км",text,re.I); im=re.search(r"_(\d{6,})$",url.rstrip("/").split("/")[-1])
        image_url = self._first_image(card, IMAGE)
        photos = [image_url] if image_url else []
        
        # Извлечение параметров (топливо, коробка, привод и т.д.)
        params_node = card.select_one(PARAMS[0]) if PARAMS else None
        params_text = params_node.get_text(" ", strip=True).lower() if params_node else text.lower()
        
        # Тип топлива
        fuel = None
        if "бензин" in params_text: fuel = "petrol"
        elif "дизель" in params_text: fuel = "diesel"
        elif "электро" in params_text: fuel = "electric"
        elif "гибрид" in params_text: fuel = "hybrid"
        elif "газ" in params_text: fuel = "gas"
        
        # Коробка передач
        transmission = None
        if "автомат" in params_text or "акпп" in params_text: transmission = "automatic"
        elif "механик" in params_text: transmission = "manual"
        elif "робот" in params_text: transmission = "robot"
        elif "вариатор" in params_text: transmission = "variator"
        
        # Привод
        drive = None
        if "полный" in params_text: drive = "four_wheel"
        elif "задний" in params_text: drive = "rear"
        elif "передний" in params_text: drive = "front"
        
        # Тип кузова
        body_type = None
        body_types = {"седан": "sedan", "хэтчбек": "hatchback", "универсал": "wagon", 
                      "внедорожник": "suv", "купе": "coupe", "кабриолет": "cabriolet",
                      "пикап": "pickup", "минивэн": "minivan", "лифтбек": "liftback"}
        for bt_key, bt_value in body_types.items():
            if bt_key in params_text:
                body_type = bt_value
                break
        
        # Объем двигателя
        engine_volume = None
        ev_match = re.search(r"(\d\.?\d?)\s*л", params_text)
        if ev_match:
            try:
                engine_volume = float(ev_match.group(1).replace(",", "."))
            except:
                pass
        
        # Мощность
        horsepower = None
        hp_match = re.search(r"(\d+)\s*л\.?\s*с", params_text)
        if hp_match:
            try:
                horsepower = int(hp_match.group(1))
            except:
                pass
        
        # Количество владельцев
        owners = None
        owners_match = re.search(r"(\d+)\s*влад", params_text)
        if owners_match:
            try:
                owners = int(owners_match.group(1))
            except:
                pass
        
        return AvitoListing(
            url=url,
            title=title,
            price=price,
            year=int(ym.group(1)) if ym else None,
            mileage=digits(mm.group(1)) if mm else None,
            brand=filters.get("brand"),
            model=filters.get("model"),
            region=filters.get("region") or filters.get("target_region"),
            external_id=im.group(1) if im else None,
            photos=photos,
            transmission=transmission,
            fuel=fuel,
            drive=drive,
            body_type=body_type,
            engine_volume=engine_volume,
            horsepower=horsepower,
            owners=owners
        ).to_dict()
