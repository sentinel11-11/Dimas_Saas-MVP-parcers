"""
FastAPI веб-приложение для парсинга автомобилей
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import asyncio
import json
from loguru import logger

from app.database.db import init_db, get_all_listings
from app.services.search_service import run_search, start_job, get_job

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("Web application started")
    yield


app = FastAPI(
    title="Car Parser MVP",
    description="Быстрый подбор автомобилей",
    lifespan=lifespan,
)

# Подключение статики и шаблонов
# Список всех марок автомобилей (расширенный)
ALL_BRANDS = [
    "audi", "bmw", "chevrolet", "chrysler", "citroen", "dodge", "fiat", "ford",
    "genesis", "gmc", "honda", "hyundai", "infiniti", "jaguar", "jeep",
    "kia", "land rover", "lexus", "mazda", "mercedes", "mini", "mitsubishi",
    "nissan", "opel", "peugeot", "porsche", "renault", "skoda", "subaru",
    "suzuki", "toyota", "volkswagen", "volvo", "lada", "gaz", "uaz",
    "chery", "haval", "geely", "exeed", "tank", "omoda", "jaecoo", "kowloon",
    "faaw", "dongfeng", "foton", "great wall", "lifan", "brilliance"
]

# Полный список регионов России для поиска
ALL_REGIONS = [
    {"value": "", "label": "Вся Россия"},
    {"value": "moscow", "label": "Москва"},
    {"value": "spb", "label": "Санкт-Петербург"},
    {"value": "novosibirsk", "label": "Новосибирск"},
    {"value": "ekaterinburg", "label": "Екатеринбург"},
    {"value": "kazan", "label": "Казань"},
    {"value": "krasnoyarsk", "label": "Красноярск"},
    {"value": "vladivostok", "label": "Владивосток"},
    {"value": "samara", "label": "Самара"},
    {"value": "chelyabinsk", "label": "Челябинск"},
    {"value": "rostov-na-donu", "label": "Ростов-на-Дону"},
    {"value": "ufa", "label": "Уфа"},
    {"value": "perm", "label": "Пермь"},
    {"value": "volgograd", "label": "Волгоград"},
    {"value": "voronezh", "label": "Воронеж"},
    {"value": "saransk", "label": "Саранск"},
    {"value": "tyumen", "label": "Тюмень"},
    {"value": "omsk", "label": "Омск"},
    {"value": "irkutsk", "label": "Иркутск"},
    {"value": "khabarovsk", "label": "Хабаровск"},
    {"value": "yuzhno-sakhalinsk", "label": "Южно-Сахалинск"},
    {"value": "petropavlovsk-kamchatsky", "label": "Петропавловск-Камчатский"},
    {"value": "yakutsk", "label": "Якутск"},
    {"value": "krasnodar", "label": "Краснодар"},
    {"value": "sochi", "label": "Сочи"},
    {"value": "simferopol", "label": "Симферополь"},
    {"value": "sevastopol", "label": "Севастополь"},
    {"value": "kaliningrad", "label": "Калининград"},
    {"value": "murmansk", "label": "Мурманск"},
    {"value": "arkhangelsk", "label": "Архангельск"},
    {"value": "vologda", "label": "Вологда"},
    {"value": "nizhny-novgorod", "label": "Нижний Новгород"},
    {"value": "saratov", "label": "Саратов"},
    {"value": "penza", "label": "Пенза"},
    {"value": "tolyatti", "label": "Тольятти"},
    {"value": "izhevsk", "label": "Ижевск"},
    {"value": "barnaul", "label": "Барнаул"},
    {"value": "tomsk", "label": "Томск"},
    {"value": "kemerovo", "label": "Кемерово"},
    {"value": "novokuznetsk", "label": "Новокузнецк"},
    {"value": "chita", "label": "Чита"},
    {"value": "ulan-ude", "label": "Улан-Удэ"},
    {"value": "magadan", "label": "Магадан"},
    {"value": "blagoveshchensk", "label": "Благовещенск"},
    {"value": "birobidzhan", "label": "Биробиджан"},
    {"value": "gorno-altaysk", "label": "Горно-Алтайск"},
    {"value": "abakan", "label": "Абакан"},
    {"value": "kyzyl", "label": "Кызыл"},
    {"value": "salekhard", "label": "Салехард"},
    {"value": "khanty-mansiysk", "label": "Ханты-Мансийск"},
    {"value": "naryan-mar", "label": "Нарьян-Мар"},
    {"value": "syktyvkar", "label": "Сыктывкар"},
    {"value": "kirov", "label": "Киров"},
    {"value": "orel", "label": "Орел"},
    {"value": "kursk", "label": "Курск"},
    {"value": "belgorod", "label": "Белгород"},
    {"value": "lipetsk", "label": "Липецк"},
    {"value": "tambov", "label": "Тамбов"},
    {"value": "ryazan", "label": "Рязань"},
    {"value": "tula", "label": "Тула"},
    {"value": "kaluga", "label": "Калуга"},
    {"value": "smolensk", "label": "Смоленск"},
    {"value": "tver", "label": "Тверь"},
    {"value": "yaroslavl", "label": "Ярославль"},
    {"value": "kostroma", "label": "Кострома"},
    {"value": "ivanovo", "label": "Иваново"},
    {"value": "vladimir", "label": "Владимир"},
    {"value": "veliky-novgorod", "label": "Великий Новгород"},
    {"value": "pskov", "label": "Псков"},
    {"value": "petrozavodsk", "label": "Петрозаводск"},
    {"value": "makhachkala", "label": "Махачкала"},
    {"value": "grozny", "label": "Грозный"},
    {"value": "nalchik", "label": "Нальчик"},
    {"value": "vladikavkaz", "label": "Владикавказ"},
    {"value": "cherkessk", "label": "Черкесск"},
    {"value": "elista", "label": "Элиста"},
    {"value": "stavropol", "label": "Ставрополь"},
    {"value": "pyatigorsk", "label": "Пятигорск"},
    {"value": "mineralnye-vody", "label": "Минеральные Воды"},
    {"value": "armavir", "label": "Армавир"},
    {"value": "novorossiysk", "label": "Новороссийск"},
    {"value": "anapa", "label": "Анапа"},
    {"value": "gelendzhik", "label": "Геленджик"}
]

# Популярные модели для каждой марки
POPULAR_MODELS = {
    "bmw": ["1 серия", "2 серия", "3 серия", "4 серия", "5 серия", "6 серия", "7 серия", "8 серия", 
            "X1", "X2", "X3", "X4", "X5", "X6", "X7", "Z4", "i3", "i4", "iX"],
    "mercedes": ["A-Class", "B-Class", "C-Class", "CLA", "CLS", "E-Class", "G-Class", "GLA", "GLB", 
                 "GLC", "GLE", "GLS", "S-Class", "SL", "AMG GT"],
    "audi": ["A1", "A3", "A4", "A5", "A6", "A7", "A8", "Q2", "Q3", "Q4", "Q5", "Q7", "Q8", "TT", "e-tron"],
    "toyota": ["Camry", "Corolla", "RAV4", "Land Cruiser", "Highlander", "Prius", "Yaris", "Avalon"],
    "honda": ["Accord", "Civic", "CR-V", "HR-V", "Pilot", "Odyssey", "Fit"],
    "nissan": ["Almera", "Altima", "Juke", "Kashqai", "Leaf", "Maxima", "Murano", "Note", "Pathfinder", "Qashqai", "Terrano", "X-Trail"],
    "volkswagen": ["Golf", "Jetta", "Passat", "Polo", "Tiguan", "Touareg", "Arteon"],
    "ford": ["Fiesta", "Focus", "Fusion", "Kuga", "Mondeo", "Mustang", "Explorer", "F-150"],
    "hyundai": ["Accent", "Elantra", "Genesis", "Grandeur", "i30", "Santa Fe", "Sonata", "Tucson"],
    "kia": ["Ceed", "Cerato", "K5", "Mohave", "Optima", "Picanto", "Rio", "Sorento", "Sportage", "Stinger"],
    "lexus": ["ES", "GS", "IS", "LS", "LX", "NX", "RX", "UX"],
    "mazda": ["2", "3", "5", "6", "CX-3", "CX-5", "CX-7", "CX-9", "MX-5"],
    "subaru": ["Forester", "Impreza", "Legacy", "Outback", "WRX", "XV"],
    "mitsubishi": ["ASX", "Eclipse Cross", "L200", "Lancer", "Outlander", "Pajero"],
    "porsche": ["718", "911", "Cayenne", "Macan", "Panamera", "Taycan"],
    "volvo": ["S40", "S60", "S90", "V40", "V60", "V90", "XC40", "XC60", "XC90"],
    "lada": ["Granta", "Kalina", "Priora", "Vesta", "XRAY", "Niva", "Largus"],
    "gaz": ["Volga", "Gazelle", "Next"],
    "uaz": ["Patriot", "Hunter", "Pickup", "Cargo"]
}

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

parsing_results: Dict[str, List[Dict[str, Any]]] = {}


class SearchRequest(BaseModel):
    brand: str
    model: str
    sources: List[str] = ["drom"]
    limit: int = 10


def _form_params(**kwargs) -> dict:
    sources = kwargs.get("sources") or ["drom"]
    if isinstance(sources, str):
        sources = [sources]
    return {**kwargs, "sources": sources}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "title": "Быстрый подбор автомобиля",
            "brands": ALL_BRANDS,
            "regions": ALL_REGIONS,
            "models_json": json.dumps(POPULAR_MODELS),
            "custom_limit_enabled": True,
        },
    )


@app.post("/search", response_class=HTMLResponse)
async def search_cars(
    request: Request,
    brand: str = Form(...),
    model: str = Form(...),
    sources: List[str] = Form(default=["drom"]),
    limit: int = Form(default=20),
    year_min: int = Form(default=2018),
    year_max: int = Form(default=2026),
    mileage_min: int = Form(default=0),
    mileage_max: int = Form(default=300000),
    owners_min: int = Form(default=1),
    owners_max: int = Form(default=3),
    price_min: int = Form(default=0),
    price_max: int = Form(default=100000000),
    transmission: str = Form(default=""),
    fuel: str = Form(default=""),
    drive: str = Form(default=""),
    body_type: str = Form(default=""),
    region: str = Form(default=""),
):
    params = _form_params(
        brand=brand,
        model=model,
        sources=sources,
        limit=limit,
        year_min=year_min,
        year_max=year_max,
        mileage_min=mileage_min,
        mileage_max=mileage_max,
        owners_min=owners_min,
        owners_max=owners_max,
        price_min=price_min,
        price_max=price_max,
        transmission=transmission,
        fuel=fuel,
        drive=drive,
        body_type=body_type,
        region=region,
    )
    logger.info(f"Search request: {params}")
    try:
        data = await asyncio.to_thread(run_search, params)
    except Exception as e:
        logger.exception("search failed")
        data = {
            "results": [],
            "errors": [str(e)],
            "sources_used": params.get("sources"),
            "filters_applied": params,
            "brand": brand,
            "model": model,
            "total": 0,
            "sample_size": 0,
        }
    session_key = f"{brand}_{model}"
    parsing_results[session_key] = data.get("results") or []
    return templates.TemplateResponse(
        "results.html",
        {
            "request": request,
            "results": data.get("results") or [],
            "brand": brand.capitalize(),
            "model": model.capitalize(),
            "total": data.get("total") or 0,
            "errors": data.get("errors") or [],
            "sources_used": data.get("sources_used") or [],
            "filters_applied": data.get("filters_applied") or params,
            "sample_size": data.get("sample_size") or 0,
        },
    )


@app.post("/api/search/jobs")
async def create_search_job(request: Request):
    form = await request.form()
    sources = form.getlist("sources") or ["drom"]
    params = {
        "brand": form.get("brand"),
        "model": form.get("model"),
        "sources": sources,
        "limit": form.get("limit") or 20,
        "year_min": form.get("year_min") or 2018,
        "year_max": form.get("year_max") or 2026,
        "mileage_min": form.get("mileage_min") or 0,
        "mileage_max": form.get("mileage_max") or 300000,
        "owners_min": form.get("owners_min") or 1,
        "owners_max": form.get("owners_max") or 3,
        "price_min": form.get("price_min") or 0,
        "price_max": form.get("price_max") or 100000000,
        "transmission": form.get("transmission") or "",
        "fuel": form.get("fuel") or "",
        "drive": form.get("drive") or "",
        "body_type": form.get("body_type") or "",
        "region": form.get("region") or "",
    }
    job_id = start_job(params)
    return {"job_id": job_id}


@app.get("/api/search/jobs/{job_id}")
async def job_status(job_id: str):
    job = get_job(job_id)
    if not job:
        return JSONResponse({"error": "not found"}, status_code=404)
    return job


@app.get("/search/wait/{job_id}", response_class=HTMLResponse)
async def search_wait(request: Request, job_id: str):
    return templates.TemplateResponse(
        "wait.html",
        {"request": request, "job_id": job_id},
    )


def get_badge_class(probability: float) -> str:
    if probability >= 0.8:
        return "bg-success"
    elif probability >= 0.6:
        return "bg-primary"
    elif probability >= 0.4:
        return "bg-warning"
    return "bg-danger"


@app.get("/results/{brand}/{model}", response_class=HTMLResponse)
async def view_results(request: Request, brand: str, model: str):
    session_key = f"{brand}_{model}"
    results = parsing_results.get(session_key, [])
    if not results:
        try:
            db_listings = get_all_listings()
            for listing in db_listings:
                results.append(
                    {
                        "title": listing.title,
                        "price": listing.price,
                        "year": listing.year,
                        "mileage": listing.mileage,
                        "region": listing.region,
                        "url": listing.url,
                        "platform": listing.source,
                        "market_price": listing.market_score,
                        "market_deviation": 0,
                        "probability": listing.final_score,
                        "liquidity": 0.5,
                        "badge_class": get_badge_class(listing.final_score or 0),
                        "fuel": listing.fuel_type,
                    }
                )
        except Exception as e:
            logger.error(f"DB LOAD ERROR: {e}")
    return templates.TemplateResponse(
        "results.html",
        {
            "request": request,
            "results": results,
            "brand": brand.capitalize(),
            "model": model.capitalize(),
            "total": len(results),
            "errors": [],
            "sources_used": [],
            "sample_size": len(results),
        },
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
