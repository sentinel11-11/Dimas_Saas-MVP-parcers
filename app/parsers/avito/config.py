import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем .env из корня проекта
env_path = Path(__file__).parent.parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

class AvitoConfig:
    base_url = "https://www.avito.ru"
    search_limit = int(os.getenv("AVITO_SEARCH_LIMIT", "20"))
    max_pages = int(os.getenv("AVITO_MAX_PAGES", "5"))  # Увеличено с 3 до 5
    request_timeout = int(os.getenv("AVITO_REQUEST_TIMEOUT", "12"))
    save_debug_html = os.getenv("AVITO_DEBUG_HTML", "true").lower() == "true"
    use_spfa_converter = os.getenv("AVITO_USE_SPFA_CONVERTER", "false").lower() == "true"
    retry_delay = int(os.getenv("AVITO_RETRY_DELAY", "5"))  # Задержка перед повторной попыткой при 429
    max_retries = int(os.getenv("AVITO_MAX_RETRIES", "1"))
    
    # Прокси конфигурация
    proxy_list = [p.strip() for p in os.getenv("AVITO_PROXIES", "").split(",") if p.strip()] if os.getenv("AVITO_PROXIES") else None
    if not proxy_list:
        try:
            from app.core.proxy import ProxySettings
            proxy_list = ProxySettings.proxy_list() or None
        except Exception:
            proxy_list = None
config = AvitoConfig()
