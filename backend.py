import os
import sys
import json
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Импорт наших модулей
try:
    from app.parsers.drom_parser import DromParser
    from app.parsers.avito_parser import AvitoParser
    from app.parsers.autoru_parser import AutoRuParser
    from app.models.config import CarSearchConfig
    from app.services.analyzer import MarketAnalyzer
    from app.services.normalizer import DataNormalizer
    PARSERS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Some parsers failed to import: {e}")
    PARSERS_AVAILABLE = False

app = FastAPI(title="Car Parser MVP")

# Разрешаем CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Монтируем статику и шаблоны
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except Exception:
    pass # Папка static может отсутствовать в некоторых сборках

# --- Модели данных ---

class SearchRequest(BaseModel):
    brand: Optional[str] = ""
    model: Optional[str] = ""
    year_min: Optional[int] = None
    year_max: Optional[int] = None
    price_min: Optional[int] = None
    price_max: Optional[int] = None
    mileage_min: Optional[int] = None
    mileage_max: Optional[int] = None
    owners_min: Optional[int] = None
    owners_max: Optional[int] = None
    transmission: Optional[str] = ""
    fuel: Optional[str] = ""
    drive: Optional[str] = ""
    body_type: Optional[str] = ""
    region: Optional[str] = ""
    sources: List[str] = ["drom"]  # drom, avito, autoru

class SearchResult(BaseModel):
    success: bool
    data: List[Dict[str, Any]]
    message: str = ""

# --- Логика парсинга ---

async def run_parsing_task(config: CarSearchConfig, sources: List[str]) -> List[Dict]:
    results = []
    normalizer = DataNormalizer()
    analyzer = MarketAnalyzer()
    
    parsers = []
    if "drom" in sources:
        parsers.append(DromParser())
    if "avito" in sources:
        parsers.append(AvitoParser())
    if "autoru" in sources:
        parsers.append(AutoRuParser())
    
    if not parsers:
        return []

    for parser in parsers:
        try:
            print(f"Starting parser: {parser.__class__.__name__}")
            raw_ads = await parser.search(config)
            
            for ad in raw_ads:
                # Нормализация
                normalized = normalizer.normalize(ad)
                if normalized:
                    # Расчет аналитики
                    liquidity = analyzer.calculate_liquidity(normalized)
                    probability = analyzer.calculate_deal_probability(normalized, config)
                    
                    normalized['liquidity_score'] = liquidity
                    normalized['deal_probability'] = probability
                    normalized['search_config_applied'] = config.dict()
                    
                    results.append(normalized)
        except Exception as e:
            print(f"Error in parser {parser.__class__.__name__}: {e}")
            continue
            
    return results

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Отдает главный HTML файл"""
    try:
        with open("templates/index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Ошибка: Файл index.html не найден. Убедитесь, что папка templates существует.</h1>", status_code=404)

@app.post("/api/search", response_model=SearchResult)
async def search_cars(request: SearchRequest):
    if not PARSERS_AVAILABLE:
        raise HTTPException(status_code=500, detail="Парсеры не инициализированы. Проверьте логи.")
    
    # Преобразование запроса в конфиг
    config_dict = request.dict(exclude_unset=True)
    # Очистка пустых строк
    clean_config = {k: v for k, v in config_dict.items() if v not in [None, "", []]}
    
    try:
        config = CarSearchConfig(**clean_config)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка валидации параметров: {str(e)}")
    
    # Запуск парсинга (в реальном приложении лучше через BackgroundTasks, но для MVP синхронно в async)
    try:
        results = await run_parsing_task(config, request.sources)
        return SearchResult(success=True, data=results, message=f"Найдено {len(results)} объявлений")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при парсинге: {str(e)}")

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "parsers_ready": PARSERS_AVAILABLE}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("backend:app", host="0.0.0.0", port=port, reload=False)
