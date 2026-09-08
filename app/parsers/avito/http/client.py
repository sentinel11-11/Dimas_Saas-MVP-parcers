import random,time
from dataclasses import dataclass
import requests
from loguru import logger
from app.parsers.avito.config import config as avito_config

@dataclass
class AvitoHttpResponse:
    status_code:int
    text:str
    url:str
    
class AvitoHttpClient:
    def __init__(self,timeout=30, proxy_list=None):
        self.timeout=timeout; self.session=requests.Session()
        self.proxy_list = proxy_list or []
        self.current_proxy_index = 0
        # Ротация User-Agent для обхода блокировок
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        ]
        self.session.headers.update({
            "User-Agent": random.choice(self.user_agents),
            "Accept-Language":"ru-RU,ru;q=0.9,en;q=0.8",
            "Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Cache-Control": "max-age=0"
        })
    
    def _get_next_proxy(self) -> dict:
        """Получение следующего прокси из списка"""
        if not self.proxy_list:
            return {}
        proxy = self.proxy_list[self.current_proxy_index % len(self.proxy_list)]
        self.current_proxy_index += 1
        # Преобразование формата прокси в dict для requests
        # Поддерживаемые форматы: "user:pass@ip:port", "ip:port", "http://user:pass@ip:port"
        if "://" in proxy:
            return {"http": proxy, "https": proxy}
        else:
            return {"http": f"http://{proxy}", "https": f"http://{proxy}"}
    
    def rotate_proxy(self):
        """Ротация прокси для следующего запроса"""
        proxies = self._get_next_proxy()
        if proxies:
            self.session.proxies.update(proxies)
            logger.info(f"AVITO: Rotated proxy to {proxies.get('http', 'N/A')}")
        else:
            self.session.proxies.clear()
        
    def get(self,url,params=None,retries=None):
        if retries is None:
            retries = avito_config.max_retries
            
        for attempt in range(retries):
            try:
                # Ротация прокси при каждой попытке (если прокси настроены)
                if self.proxy_list:
                    self.rotate_proxy()
                
                # Увеличенная задержка перед каждым запросом для обхода rate limit
                if attempt == 0:
                    delay = random.uniform(8, 15)  # Начальная задержка 8-15 секунд
                else: 
                    delay = min(avito_config.retry_delay * (attempt + 3) + random.uniform(5, 15), 45)
                    logger.info("AVITO RETRY {}/{} after {}s", attempt+1, retries, round(delay, 2))
                
                time.sleep(delay)
                
                # Ротация User-Agent при каждой попытке
                self.session.headers["User-Agent"] = random.choice(self.user_agents)
                
                # Добавляем заголовки для эмуляции реального браузера
                self.session.headers["Sec-Ch-Ua"] = '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"'
                self.session.headers["Sec-Ch-Ua-Mobile"] = "?0"
                self.session.headers["Sec-Ch-Ua-Platform"] = '"Windows"'
                
                r=self.session.get(url,params=params,timeout=self.timeout); logger.info("AVITO HTTP {}: {}",r.status_code,r.url)
                
                if r.status_code in (403,429,439): 
                    logger.warning("AVITO BLOCK/RATE LIMIT {}",r.status_code)
                    if attempt < retries - 1:
                        continue
                    else:
                        logger.error("AVITO: Max retries reached, returning partial result")
                        return AvitoHttpResponse(r.status_code, r.text, r.url)
                        
                if r.status_code>=500: 
                    logger.warning("AVITO SERVER ERROR {}, retrying...", r.status_code)
                    continue
                    
                return AvitoHttpResponse(r.status_code,r.text,r.url)
                
            except requests.RequestException as e: 
                logger.warning("AVITO HTTP ERROR: {}",e)
                if attempt < retries - 1:
                    continue
                    
        return None
