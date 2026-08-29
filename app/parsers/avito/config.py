import os
class AvitoConfig:
    base_url = "https://www.avito.ru"
    search_limit = int(os.getenv("AVITO_SEARCH_LIMIT", "20"))
    max_pages = int(os.getenv("AVITO_MAX_PAGES", "3"))
    request_timeout = int(os.getenv("AVITO_REQUEST_TIMEOUT", "20"))
    save_debug_html = os.getenv("AVITO_DEBUG_HTML", "true").lower() == "true"
    use_spfa_converter = os.getenv("AVITO_USE_SPFA_CONVERTER", "false").lower() == "true"
config = AvitoConfig()
