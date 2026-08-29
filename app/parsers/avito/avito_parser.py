from app.parsers.base_parser import BaseParser
from app.parsers.avito.core.parser_engine import AvitoParserEngine
from app.parsers.avito.normalizer import normalize_avito_item
class AvitoParser(BaseParser):
    def __init__(self): self.engine=AvitoParserEngine()
    def search(self,filters): return [normalize_avito_item(x,filters.get("brand",""),filters.get("model","")) for x in self.engine.search(filters)]
    def parse_card(self,card): return self.engine.parse_card(card)
