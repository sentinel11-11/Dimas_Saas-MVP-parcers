import json, os
from pathlib import Path
from threading import Lock
import requests
from loguru import logger
class AvitoUrlConverter:
    endpoint=os.getenv("AVITO_SPFA_ENDPOINT","https://spfa.pro/api/avito-url/")
    _lock=Lock()
    def __init__(self,cache_path="data/avito_api_urls.json",timeout=20):
        self.cache_path=Path(cache_path); self.timeout=timeout; self.cache=self._load()
    def convert(self,url):
        if url in self.cache:return self.cache[url]
        with self._lock:
            if url in self.cache:return self.cache[url]
            r=requests.post(self.endpoint,json={"url":url},timeout=self.timeout)
            if r.status_code!=200: raise RuntimeError(f"SPFA HTTP {r.status_code}")
            payload=r.json(); api_url=payload.get("api_url")
            if not payload.get("success") or not api_url: raise RuntimeError("SPFA did not return api_url")
            self.cache[url]=api_url; self._save(); logger.info("AVITO URL CONVERTED: {}",url); return api_url
    def _load(self):
        try:
            data=json.loads(self.cache_path.read_text(encoding="utf-8")); return data if isinstance(data,dict) else {}
        except (OSError,ValueError): return {}
    def _save(self):
        self.cache_path.parent.mkdir(parents=True,exist_ok=True); tmp=self.cache_path.with_suffix(".tmp"); tmp.write_text(json.dumps(self.cache,ensure_ascii=False,indent=2),encoding="utf-8"); tmp.replace(self.cache_path)
