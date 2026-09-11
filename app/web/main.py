"""DIMAS: лендинг, кабинет, админка."""
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any
import asyncio
import json

from fastapi import FastAPI, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from loguru import logger

from app.database.db import (
    init_db,
    save_search,
    list_saved_searches,
    delete_saved_search,
    create_user,
    find_user_by_email,
    list_users,
    touch_login,
    log_search,
    list_search_logs,
)
from app.web.auth import (
    current_user,
    login_user,
    logout_user,
    verify_password,
    session_secret,
)
from app.services.search_service import run_search, start_job, get_job, LAST_RESULTS
from app.services.monitor import check_saved_search
from app.exports.exporter import DataExporter
from app.data.brands import ALL_BRANDS, POPULAR_MODELS
from app.data.geo_cities import regions_for_ui


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    from app.core.proxy import ProxySettings
    logger.info(ProxySettings.status_line())
    logger.info("Web application started")
    yield


app = FastAPI(title="DIMAS", description="Подбор автомобилей", lifespan=lifespan, docs_url=None, redoc_url=None)
app.add_middleware(SessionMiddleware, secret_key=session_secret(), max_age=60 * 60 * 24 * 14, same_site="lax")

ALL_REGIONS = regions_for_ui()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


def _ctx(request: Request, **extra):
    user = current_user(request)
    data = {"request": request, "user": user, "is_admin": bool(user and user.is_admin)}
    data.update(extra)
    return data


def _login_redirect(next_url: str = "/app"):
    return RedirectResponse(f"/login?next={next_url}", status_code=303)


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
    host_ok = any(
        x in url
        for x in (
            "avatars.mds.yandex.net",
            "avatars.avto.ru",
            "photo.auto.ru",
            "autoru-vos",
            "auto.ru",
            "yandex.net",
            "drom.ru",
        )
    )
    if not host_ok:
        return RedirectResponse("/static/images/no-car-image.png")
    try:
        r = req.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://auto.drom.ru/" if "drom.ru" in url else "https://auto.ru/",
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
    return {"status": "ok", "proxy": ProxySettings.status_line()}


@app.get("/how", response_class=HTMLResponse)
async def docs_page(request: Request):
    return templates.TemplateResponse("docs.html", _ctx(request))


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", _ctx(request))


@app.get("/register", response_class=HTMLResponse)
async def register_get(request: Request):
    if current_user(request):
        return RedirectResponse("/app", status_code=303)
    return templates.TemplateResponse("auth.html", _ctx(request, mode="register", error="", next="/app"))


@app.post("/register")
async def register_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    name: str = Form(default=""),
    next: str = Form(default="/app"),
):
    err = ""
    email = (email or "").strip().lower()
    if "@" not in email or "." not in email:
        err = "Укажите нормальный email"
    elif len(password or "") < 6:
        err = "Пароль от 6 символов"
    else:
        try:
            user = create_user(email, password, name)
            login_user(request, user)
            touch_login(user.id)
            return RedirectResponse(next or "/app", status_code=303)
        except ValueError:
            err = "Этот email уже зарегистрирован"
        except Exception:
            logger.exception("register")
            err = "Не получилось создать аккаунт"
    return templates.TemplateResponse("auth.html", _ctx(request, mode="register", error=err, next=next))


@app.get("/login", response_class=HTMLResponse)
async def login_get(request: Request, next: str = "/app"):
    if current_user(request):
        return RedirectResponse(next or "/app", status_code=303)
    return templates.TemplateResponse("auth.html", _ctx(request, mode="login", error="", next=next))


@app.post("/login")
async def login_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    next: str = Form(default="/app"),
):
    user = find_user_by_email(email)
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "auth.html",
            _ctx(request, mode="login", error="Неверный email или пароль", next=next),
        )
    login_user(request, user)
    touch_login(user.id)
    dest = next or "/app"
    if user.is_admin and dest in ("/app", "/"):
        dest = "/admin"
    return RedirectResponse(dest, status_code=303)


@app.get("/logout")
async def logout(request: Request):
    logout_user(request)
    return RedirectResponse("/", status_code=303)


@app.get("/app", response_class=HTMLResponse)
async def cabinet(request: Request):
    user = current_user(request)
    if not user:
        return _login_redirect("/app")
    return templates.TemplateResponse(
        "cabinet.html",
        _ctx(
            request,
            brands=ALL_BRANDS,
            brands_json=json.dumps(ALL_BRANDS),
            regions=ALL_REGIONS,
            models_json=json.dumps(POPULAR_MODELS),
            saved=list_saved_searches(user_id=user.id, email=user.email),
        ),
    )


@app.get("/admin", response_class=HTMLResponse)
async def admin_home(request: Request):
    user = current_user(request)
    if not user:
        return _login_redirect("/admin")
    if not user.is_admin:
        return RedirectResponse("/app", status_code=303)
    from app.core.proxy import ProxySettings
    return templates.TemplateResponse(
        "admin.html",
        _ctx(
            request,
            brands=ALL_BRANDS,
            brands_json=json.dumps(ALL_BRANDS),
            regions=ALL_REGIONS,
            models_json=json.dumps(POPULAR_MODELS),
            users=list_users(),
            logs=list_search_logs(),
            proxy_line=ProxySettings.status_line(),
        ),
    )


def _search_payload(form: dict, sources: List[str]) -> dict:
    return _form_params(
        brand=form.get("brand"),
        model=form.get("model"),
        sources=sources,
        limit=form.get("limit") or 50,
        year_min=form.get("year_min") or 0,
        year_max=form.get("year_max") or 0,
        mileage_min=form.get("mileage_min") or 0,
        mileage_max=form.get("mileage_max") or 0,
        owners_min=form.get("owners_min") or 0,
        owners_max=form.get("owners_max") or 0,
        price_min=form.get("price_min") or 0,
        price_max=form.get("price_max") or 0,
        transmission=form.get("transmission") or "",
        fuel=form.get("fuel") or "",
        drive=form.get("drive") or "",
        body_type=form.get("body_type") or "",
        region=form.get("region") or "",
        buyer_city=form.get("buyer_city") or "",
        fuel_price=form.get("fuel_price") or 62,
    )


async def _run_and_render(request, params, user):
    logger.info(f"Search request user={getattr(user, 'email', None)} {params}")
    try:
        data = await asyncio.to_thread(run_search, params)
    except Exception as e:
        logger.exception("search failed")
        data = {
            "results": [],
            "errors": [str(e)],
            "sources_used": params.get("sources"),
            "filters_applied": params,
            "brand": params.get("brand"),
            "model": params.get("model"),
            "total": 0,
            "sample_size": 0,
        }
    try:
        log_search(
            user.id if user else 0,
            user.email if user else "",
            params.get("brand") or "",
            params.get("model") or "",
            params.get("sources") or ["drom"],
            data.get("total") or 0,
        )
    except Exception:
        pass
    return templates.TemplateResponse(
        "results.html",
        _ctx(
            request,
            results=data.get("results") or [],
            brand=(params.get("brand") or "").capitalize(),
            model=(params.get("model") or "").capitalize(),
            total=data.get("total") or 0,
            errors=data.get("errors") or [],
            sources_used=data.get("sources_used") or [],
            filters_applied=data.get("filters_applied") or params,
            sample_size=data.get("sample_size") or 0,
        ),
    )


@app.post("/search", response_class=HTMLResponse)
async def search_cars(request: Request):
    user = current_user(request)
    if not user:
        return _login_redirect("/app")
    form = await request.form()
    data = {k: form.get(k) for k in form.keys()}
    sources = ["drom", "autoru"]
    if user.is_admin:
        picked = form.getlist("sources")
        if picked:
            sources = list(picked)
    params = _search_payload(data, sources)
    return await _run_and_render(request, params, user)


@app.post("/admin/search", response_class=HTMLResponse)
async def admin_search(request: Request):
    user = current_user(request)
    if not user or not user.is_admin:
        return _login_redirect("/admin")
    form = await request.form()
    data = {k: form.get(k) for k in form.keys()}
    sources = form.getlist("sources") or ["drom", "autoru"]
    params = _search_payload(data, list(sources))
    return await _run_and_render(request, params, user)


@app.post("/api/search/jobs")
async def create_search_job(request: Request):
    user = current_user(request)
    if not user:
        return JSONResponse({"error": "auth"}, status_code=401)
    form = await request.form()
    sources = ["drom", "autoru"]
    if user.is_admin:
        sources = form.getlist("sources") or ["drom", "autoru"]
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


@app.post("/searches/save")
async def searches_save(request: Request):
    user = current_user(request)
    if not user:
        return _login_redirect("/app")
    form = await request.form()
    params = _form_params(
        brand=form.get("brand"),
        model=form.get("model"),
        sources=["drom", "autoru"],
        year_min=form.get("year_min") or 2018,
        year_max=form.get("year_max") or 2026,
        mileage_min=form.get("mileage_min") or 0,
        mileage_max=form.get("mileage_max") or 300000,
        owners_min=form.get("owners_min") or 1,
        owners_max=form.get("owners_max") or 3,
        price_min=form.get("price_min") or 0,
        price_max=form.get("price_max") or 100000000,
        region=form.get("region") or "",
        limit=20,
    )
    prices = [r.get("price") or 0 for r in (LAST_RESULTS.get("results") or [])]
    min_price = min([p for p in prices if p], default=0)
    save_search(user.email, params, last_min_price=min_price, last_count=len(prices), user_id=user.id)
    return RedirectResponse("/searches", status_code=303)


@app.get("/searches", response_class=HTMLResponse)
async def searches_page(request: Request):
    user = current_user(request)
    if not user:
        return _login_redirect("/searches")
    rows = list_saved_searches(email=user.email, user_id=user.id)
    return templates.TemplateResponse("saved.html", _ctx(request, searches=rows, email=user.email))


@app.post("/searches/{search_id}/delete")
async def searches_delete(request: Request, search_id: int):
    user = current_user(request)
    if not user:
        return _login_redirect("/searches")
    delete_saved_search(search_id)
    return RedirectResponse("/searches", status_code=303)


@app.post("/searches/{search_id}/check")
async def searches_check(request: Request, search_id: int):
    user = current_user(request)
    if not user:
        return _login_redirect("/searches")
    report = await asyncio.to_thread(check_saved_search, search_id)
    return templates.TemplateResponse("monitor.html", _ctx(request, report=report))


@app.get("/export/csv")
async def export_csv(request: Request):
    if not current_user(request):
        return JSONResponse({"error": "auth"}, status_code=401)
    cars = LAST_RESULTS.get("results") or []
    if not cars:
        return JSONResponse({"error": "Нет результатов для экспорта"}, status_code=400)
    path = DataExporter.export_to_csv(cars)
    return FileResponse(path, filename="cars.csv", media_type="text/csv; charset=utf-8")
