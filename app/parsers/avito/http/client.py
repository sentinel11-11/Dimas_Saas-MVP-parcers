import random,time
from dataclasses import dataclass
import requests
from loguru import logger
@dataclass
class AvitoHttpResponse:
    status_code:int
    text:str
    url:str
class AvitoHttpClient:
    def __init__(self,timeout=20):
        self.timeout=timeout; self.session=requests.Session(); self.session.headers.update({"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151.0 Safari/537.36","Accept-Language":"ru-RU,ru;q=0.9,en;q=0.8","Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"})
    def get(self,url,params=None,retries=3):
        for attempt in range(retries):
            try:
                if attempt: time.sleep(min(8,2**attempt+random.random()))
                r=self.session.get(url,params=params,timeout=self.timeout); logger.info("AVITO HTTP {}: {}",r.status_code,r.url)
                if r.status_code in (403,429,439): logger.warning("AVITO BLOCK/RATE LIMIT {}",r.status_code); continue
                if r.status_code>=500: continue
                return AvitoHttpResponse(r.status_code,r.text,r.url)
            except requests.RequestException as e: logger.warning("AVITO HTTP ERROR: {}",e)
        return None
