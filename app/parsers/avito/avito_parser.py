from app.parsers.base_parser import BaseParser
from app.parsers.avito.core.parser_engine import AvitoParserEngine
from app.parsers.avito.normalizer import normalize_avito_item
from app.parsers.avito.config import config as avito_config

class AvitoParser(BaseParser):
    def __init__(self, proxy_list=None): 
        # Используем прокси из параметра или из конфигурации
        if proxy_list is None:
            proxy_list = avito_config.proxy_list
        self.engine = AvitoParserEngine(proxy_list=proxy_list)
    
    def search(self, filters, proxy_list=None): 
        return [normalize_avito_item(x, filters.get("brand",""), filters.get("model","")) for x in self.engine.search(filters)]
    
    def parse_card(self, card): 
        return self.engine.parse_card(card)
