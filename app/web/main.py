"""
FastAPI веб-приложение для парсинга автомобилей
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Form

from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import asyncio
import json
from loguru import logger

from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, RedirectResponse
from app.database.db import (
    init_db,
    get_all_listings,
    save_search,
    list_saved_searches,
    get_saved_search,
    delete_saved_search,
)
from app.services.search_service import run_search, start_job, get_job, LAST_RESULTS
from app.services.monitor import check_saved_search
from app.exports.exporter import DataExporter

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    from app.core.proxy import ProxySettings
    logger.info(ProxySettings.status_line())
    logger.info("Web application started")
    yield


app = FastAPI(
    title="Car Parser MVP",
    description="Быстрый подбор автомобилей",
    lifespan=lifespan,
)

from app.data.brands import ALL_BRANDS, POPULAR_MODELS
from app.data.geo_cities import regions_for_ui

ALL_REGIONS = regions_for_ui()

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


@app.get("/img")
async def img_proxy(u: str = ""):
    from urllib.parse import unquote
    from fastapi.responses import Response
    import requests as req

    url = unquote(u or "")
    if not url.startswith("https://"):
        return RedirectResponse("/static/images/no-car-image.png")
    host_ok = any(x in url for x in ("avatars.mds.yandex.net", "autoru-vos", "auto.ru", "yandex.net"))
    if not host_ok:
        return RedirectResponse("/static/images/no-car-image.png")
    try:
        r = req.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://auto.ru/",
                "Accept": "image/avif,image/webp,image/*,*/*;q=0.8",
            },
            timeout=12,
        )
        if r.status_code >= 400 or not r.content:
            return RedirectResponse("/static/images/no-car-image.png")
        ctype = r.headers.get("content-type") or "image/jpeg"
        return Response(content=r.content, media_type=ctype.split(";")[0])
    except Exception:
        return RedirectResponse("/static/images/no-car-image.png")


@app.get("/health")
async def health():
    from app.core.proxy import ProxySettings
    return {
        "status": "ok",
        "proxy": ProxySettings.status_line(),
        "proxy_enabled": ProxySettings.enabled(),
        "proxy_host": ProxySettings.host() or None,
        "proxy_protocol": ProxySettings.protocol(),
    }


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
    limit: int = Form(default=50),
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
    buyer_city: str = Form(default="moscow"),
    fuel_price: float = Form(default=62),
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
        buyer_city=buyer_city,
        fuel_price=fuel_price,
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
        "buyer_city": form.get("buyer_city") or "moscow",
        "fuel_price": form.get("fuel_price") or 62,
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


@app.post("/searches/save")
async def searches_save(
    email: str = Form(default=""),
    brand: str = Form(...),
    model: str = Form(...),
    year_min: int = Form(default=2018),
    year_max: int = Form(default=2026),
    mileage_min: int = Form(default=0),
    mileage_max: int = Form(default=300000),
    owners_min: int = Form(default=1),
    owners_max: int = Form(default=3),
    price_min: int = Form(default=0),
    price_max: int = Form(default=100000000),
    region: str = Form(default=""),
    sources: List[str] = Form(default=["drom"]),
):
    params = _form_params(
        brand=brand,
        model=model,
        sources=sources,
        year_min=year_min,
        year_max=year_max,
        mileage_min=mileage_min,
        mileage_max=mileage_max,
        owners_min=owners_min,
        owners_max=owners_max,
        price_min=price_min,
        price_max=price_max,
        region=region,
        limit=20,
    )
    prices = [r.get("price") or 0 for r in (LAST_RESULTS.get("results") or [])]
    min_price = min([p for p in prices if p], default=0)
    save_search(email, params, last_min_price=min_price, last_count=len(prices))
    return RedirectResponse(f"/searches?email={email}", status_code=303)


@app.get("/searches", response_class=HTMLResponse)
async def searches_page(request: Request, email: str = ""):
    rows = list_saved_searches(email)
    return templates.TemplateResponse(
        "saved.html",
        {"request": request, "searches": rows, "email": email},
    )


@app.post("/searches/{search_id}/delete")
async def searches_delete(search_id: int, email: str = Form(default="")):
    delete_saved_search(search_id)
    return RedirectResponse(f"/searches?email={email}", status_code=303)


@app.post("/searches/{search_id}/check")
async def searches_check(request: Request, search_id: int):
    report = await asyncio.to_thread(check_saved_search, search_id)
    return templates.TemplateResponse(
        "monitor.html",
        {"request": request, "report": report},
    )


@app.get("/export/csv")
async def export_csv():
    cars = LAST_RESULTS.get("results") or []
    if not cars:
        return JSONResponse({"error": "Нет результатов для экспорта"}, status_code=400)
    path = DataExporter.export_to_csv(cars)
    return FileResponse(path, filename="cars.csv", media_type="text/csv")


@app.post("/import/csv")
async def import_csv(request: Request):
    form = await request.form()
    upload = form.get("file")
    if not upload:
        return JSONResponse({"error": "Файл не передан"}, status_code=400)
    raw = await upload.read()
    import csv
    import io
    from types import SimpleNamespace
    from app.database.db import save_listing

    text = raw.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    count = 0
    for row in reader:
        obj = SimpleNamespace(
            title=row.get("title") or "import",
            price=int(row.get("price") or 0),
            year=int(row.get("year") or 0),
            mileage=int(row.get("mileage") or 0),
            owners=int(row.get("owners") or 0) if row.get("owners") else None,
            engine_volume=float(row.get("engine_volume") or 0),
            horsepower=int(row.get("horsepower") or 0),
            transmission=row.get("transmission") or "",
            drive=row.get("drive"),
            body_type=row.get("body_type"),
            fuel=row.get("fuel") or row.get("fuel_type"),
            region=row.get("region") or "",
            accidents=None,
            pts=None,
            market_score=0,
            probability_good_deal=0,
            url=row.get("url") or f"import://{count}",
            platform=row.get("platform") or "csv",
        )
        try:
            save_listing(obj)
            count += 1
        except Exception as e:
            logger.error(f"CSV import row error: {e}")
    return {"imported": count}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
