import re
from pathlib import Path
from urllib.parse import urljoin,urlencode
from bs4 import BeautifulSoup
from loguru import logger
from app.parsers.avito.config import config
from app.parsers.avito.http.client import AvitoHttpClient
from app.parsers.avito.models import AvitoListing
from app.parsers.avito.normalizer import digits
from app.parsers.avito.selectors import CARD,LINK,PRICE,TITLE
class AvitoParserEngine:
    def __init__(self,client=None): self.client=client or AvitoHttpClient(config.request_timeout)
    def build_url(self,filters,page=1):
        brand=str(filters.get("brand") or "").strip().lower(); model=str(filters.get("model") or "").strip().lower(); region=str(filters.get("region") or filters.get("target_region") or "rossiya").strip().lower()
        path=f"/{region}/avtomobili/" + ((brand+"/"+model+"/") if brand and model else (brand+"/") if brand else "")
        return "https://www.avito.ru"+path+("?"+urlencode({"p":page}) if page>1 else "")
    def search(self,filters):
        limit=min(int(filters.get("limit") or config.search_limit),1000); results=[]; seen=set(); max_pages=max(1,min(config.max_pages,(limit+9)//10))
        for page in range(1,max_pages+1):
            if len(results)>=limit: break
            url=self.build_url(filters,page); logger.info("AVITO SEARCH: {}",url); response=self.client.get(url)
            if not response or response.status_code!=200: continue
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
    def parse_card(self,card,filters=None):
        filters=filters or {}; title=self._first_text(card,TITLE); url=self._first_href(card,LINK)
        if not title or not url:return None
        text=card.get_text(" ",strip=True); price=digits(self._first_text(card,PRICE)); ym=re.search(r"\b(19\d{2}|20\d{2})\b",title+" "+text); mm=re.search(r"([\d\s]{3,})\s*км",text,re.I); im=re.search(r"_(\d{6,})$",url.rstrip("/").split("/")[-1])
        return AvitoListing(url=url,title=title,price=price,year=int(ym.group(1)) if ym else None,mileage=digits(mm.group(1)) if mm else None,brand=filters.get("brand"),model=filters.get("model"),region=filters.get("region") or filters.get("target_region"),external_id=im.group(1) if im else None).to_dict()
