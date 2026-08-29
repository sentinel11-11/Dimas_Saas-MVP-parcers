"""
Modern FastAPI Application for Car Parser MVP
Completely rewritten with proper error handling, modern UI, and best practices
"""
import os
import sys
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from loguru import logger
import asyncio
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database.db import init_db, save_listing, get_all_listings
from app.parsers.drom.drom_parser import DromParser
from app.parsers.drom.drom_detail_parser import DromDetailParser
from app.parsers.autoru.autoru_parser import AutoRuParser
from app.parsers.avito.avito_parser import AvitoParser
from app.core.normalizer import DataNormalizer
from app.core.market import MarketEngine
from app.core.market_analyzer import MarketAnalyzer
from app.models.car_listing import CarListing, CarSearchConfig

# Configure logging
logger.remove()
logger.add("logs/app.log", rotation="10 MB", level="INFO")
logger.add(sys.stdout, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>")

app = FastAPI(
    title="Car Parser MVP - Modern Edition",
    description="Intelligent car listing aggregator with market analysis",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Global results cache
parsing_results: Dict[str, Dict[str, Any]] = {}


# ============================================================================
# Pydantic Models for API
# ============================================================================

class SearchRequestModel(BaseModel):
    """Modern search request model with validation"""
    brand: str = Field(..., min_length=1, max_length=50, description="Car brand")
    model: Optional[str] = Field(None, max_length=50, description="Car model")
    sources: List[str] = Field(default=["drom", "avito", "autoru"], description="Data sources")
    limit: int = Field(default=20, ge=1, le=100, description="Max results")
    
    # Filters
    year_min: int = Field(default=2015, ge=1990, le=2026)
    year_max: int = Field(default=2026, ge=1990, le=2026)
    mileage_min: int = Field(default=0, ge=0, le=1000000)
    mileage_max: int = Field(default=300000, ge=0, le=1000000)
    owners_min: int = Field(default=0, ge=0, le=10)
    owners_max: int = Field(default=5, ge=0, le=10)
    price_min: int = Field(default=0, ge=0)
    price_max: int = Field(default=50000000, ge=0)
    
    # Additional filters
    transmission: Optional[str] = Field(None, pattern="^(automatic|manual|robot|variator)?$")
    fuel: Optional[str] = Field(None, pattern="^(petrol|diesel|electric|hybrid|gas)?$")
    drive: Optional[str] = Field(None, pattern="^(front|rear|four_wheel)?$")
    body_type: Optional[str] = None
    region: Optional[str] = None
    
    @field_validator('year_max')
    @classmethod
    def validate_year_range(cls, v, info):
        if 'year_min' in info.data and v < info.data['year_min']:
            raise ValueError('year_max must be >= year_min')
        return v
    
    @field_validator('mileage_max')
    @classmethod
    def validate_mileage_range(cls, v, info):
        if 'mileage_min' in info.data and v < info.data['mileage_min']:
            raise ValueError('mileage_max must be >= mileage_min')
        return v


class SearchResultModel(BaseModel):
    """Search result model"""
    success: bool
    count: int
    data: List[Dict[str, Any]]
    errors: List[str] = []
    search_time: float = 0.0


class CarCardModel(BaseModel):
    """Simplified car card for UI"""
    title: str
    price: int
    year: Optional[int]
    mileage: Optional[int]
    region: Optional[str]
    url: str
    platform: str
    image_url: Optional[str]
    probability: float
    liquidity: float
    market_price: Optional[float]
    market_deviation: Optional[float]
    badge_class: str
    transmission: Optional[str]
    fuel: Optional[str]
    owners: Optional[int]


# ============================================================================
# Helper Functions
# ============================================================================

ALL_BRANDS = [
    "audi", "bmw", "chevrolet", "chrysler", "citroen", "dodge", "fiat", "ford",
    "geely", "genesis", "gmc", "honda", "hyundai", "infiniti", "jaguar", "jeep",
    "kia", "land rover", "lexus", "mazda", "mercedes", "mini", "mitsubishi",
    "nissan", "opel", "peugeot", "porsche", "renault", "skoda", "subaru",
    "suzuki", "toyota", "volkswagen", "volvo", "lada", "gaz", "uaz",
    "chery", "haval", "exeed", "tank", "omoda", "jaecoo", "dongfeng",
    "foton", "great wall", "lifan", "brilliance", "jac", "byd", "changan"
]

POPULAR_MODELS = {
    "bmw": ["1 серия", "3 серия", "5 серия", "X1", "X3", "X5", "X6"],
    "mercedes": ["A-Class", "C-Class", "E-Class", "G-Class", "GLC", "GLE", "S-Class"],
    "audi": ["A3", "A4", "A6", "Q3", "Q5", "Q7", "Q8"],
    "toyota": ["Camry", "Corolla", "RAV4", "Land Cruiser", "Highlander"],
    "honda": ["Accord", "Civic", "CR-V", "Pilot"],
    "nissan": ["Almera", "Juke", "Qashqai", "X-Trail"],
    "volkswagen": ["Golf", "Jetta", "Passat", "Polo", "Tiguan"],
    "ford": ["Focus", "Kuga", "Mondeo", "Mustang"],
    "hyundai": ["Elantra", "Santa Fe", "Sonata", "Tucson"],
    "kia": ["Ceed", "K5", "Rio", "Sorento", "Sportage"],
    "lexus": ["ES", "LX", "NX", "RX"],
    "mazda": ["3", "6", "CX-5", "CX-9"],
    "lada": ["Granta", "Vesta", "Niva"],
}


def get_badge_class(probability: float) -> str:
    """Get badge CSS class based on probability score"""
    if probability is None:
        return "bg-secondary"
    if probability >= 0.8:
        return "bg-success"
    elif probability >= 0.6:
        return "bg-primary"
    elif probability >= 0.4:
        return "bg-warning"
    else:
        return "bg-danger"


async def parse_all_sources(
    brand: str,
    model: Optional[str],
    sources: List[str],
    limit: int,
    region: Optional[str] = None
) -> tuple[List[CarListing], List[str]]:
    """Parse all selected sources concurrently"""
    enriched = []
    errors = []
    
    tasks = []
    
    # Drom parsing task
    if "drom" in sources:
        async def parse_drom():
            try:
                drom_parser = DromParser()
                drom_detail_parser = DromDetailParser()
                filters = {"brand": brand, "model": model} if model else {"brand": brand}
                drom_ads = drom_parser.search(filters)
                logger.info(f"DROM: Found {len(drom_ads)} listings")
                
                for ad in drom_ads[:limit]:
                    try:
                        details = drom_detail_parser.parse(ad.get("url", ""))
                        if details:
                            ad.update(details)
                        normalized = DataNormalizer.normalize(ad)
                        normalized["platform"] = "drom"
                        return CarListing(**normalized)
                    except Exception as e:
                        logger.error(f"DROM detail error: {e}")
                        errors.append(f"Drom: {str(e)}")
                return []
            except Exception as e:
                logger.error(f"DROM search error: {e}")
                errors.append(f"Drom search: {str(e)}")
                return []
        
        tasks.append(parse_drom())
    
    # Avito parsing task
    if "avito" in sources:
        async def parse_avito():
            try:
                proxy_list_str = os.getenv("AVITO_PROXIES", "")
                avito_proxy_list = [p.strip() for p in proxy_list_str.split(",") if p.strip()] if proxy_list_str else None
                
                avito_parser = AvitoParser(proxy_list=avito_proxy_list)
                avito_ads = avito_parser.search({
                    "brand": brand,
                    "model": model,
                    "limit": limit,
                    "target_region": region if region else "rossiya"
                })
                logger.info(f"AVITO: Found {len(avito_ads)} listings")
                
                results = []
                for ad in avito_ads:
                    try:
                        normalized = DataNormalizer.normalize(ad)
                        normalized["platform"] = "avito"
                        if normalized.get("url") and normalized.get("title"):
                            results.append(CarListing(**normalized))
                    except Exception as e:
                        logger.error(f"AVITO normalization error: {e}")
                        errors.append(f"Avito: {str(e)}")
                return results
            except Exception as e:
                logger.error(f"AVITO search error: {e}")
                errors.append(f"Avito search: {str(e)}")
                return []
        
        tasks.append(parse_avito())
    
    # Auto.ru parsing task
    if "autoru" in sources:
        async def parse_autoru():
            try:
                proxy_list_str = os.getenv("AUTORU_PROXIES", "")
                autoru_proxy_list = [p.strip() for p in proxy_list_str.split(",") if p.strip()] if proxy_list_str else None
                
                autoru_parser = AutoRuParser(headless=True, proxy_list=autoru_proxy_list)
                autoru_cars = await autoru_parser.search(
                    filters={"brand": brand, "model": model} if model else {"brand": brand},
                    limit=limit
                )
                logger.info(f"AUTO.RU: Found {len(autoru_cars)} listings")
                
                results = []
                for car_data in autoru_cars:
                    try:
                        if isinstance(car_data, CarListing):
                            results.append(car_data)
                        else:
                            normalized = DataNormalizer.normalize(car_data)
                            normalized["platform"] = "autoru"
                            results.append(CarListing(**normalized))
                    except Exception as e:
                        logger.error(f"AUTO.RU normalization error: {e}")
                        errors.append(f"Auto.ru: {str(e)}")
                return results
            except Exception as e:
                logger.error(f"AUTO.RU search error: {e}")
                errors.append(f"Auto.ru search: {str(e)}")
                return []
        
        tasks.append(parse_autoru())
    
    # Execute all parsing tasks concurrently
    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, list):
                enriched.extend(result)
            elif isinstance(result, Exception):
                errors.append(f"Task error: {str(result)}")
    
    return enriched, errors


def apply_filters(
    cars: List[CarListing],
    year_min: int,
    year_max: int,
    mileage_min: int,
    mileage_max: int,
    owners_min: int,
    owners_max: int,
    price_min: int,
    price_max: int,
    transmission: Optional[str],
    fuel: Optional[str],
    drive: Optional[str],
    body_type: Optional[str],
    region: Optional[str]
) -> List[CarListing]:
    """Apply filters to car listings"""
    filtered = []
    
    for car in cars:
        try:
            # Year filter
            if car.year and (car.year < year_min or car.year > year_max):
                continue
            
            # Mileage filter
            if car.mileage and (car.mileage < mileage_min or car.mileage > mileage_max):
                continue
            
            # Owners filter - handle both 'owners' and 'owners_count'
            owners_val = getattr(car, 'owners', None) or getattr(car, 'owners_count', None)
            if owners_val and (owners_val < owners_min or owners_val > owners_max):
                continue
            
            # Price filter
            if car.price and (car.price < price_min or car.price > price_max):
                continue
            
            # Transmission filter
            if transmission and car.transmission and car.transmission.lower() != transmission.lower():
                continue
            
            # Fuel filter
            if fuel and car.fuel and car.fuel.lower() != fuel.lower():
                continue
            
            # Drive filter
            if drive and car.drive and car.drive.lower() != drive.lower():
                continue
            
            # Body type filter
            if body_type and car.body_type and car.body_type.lower() != body_type.lower():
                continue
            
            # Region filter
            if region and car.region and region.lower() not in car.region.lower():
                continue
            
            filtered.append(car)
        except Exception as e:
            logger.error(f"Filter error: {e}")
            filtered.append(car)  # Include on error
    
    return filtered


def calculate_scores(cars: List[CarListing]) -> List[CarListing]:
    """Calculate market scores and probabilities for all cars"""
    if not cars:
        return cars
    
    try:
        market = MarketEngine([x.model_dump() for x in cars])
        
        for car in cars:
            car.market_score = market.price_score(car.model_dump())
            car.market_price = MarketAnalyzer.calculate_market_price(
                [x.model_dump() for x in cars], car
            )
            car.market_deviation = MarketAnalyzer.calculate_market_deviation(
                car.price, car.market_price
            )
            car.liquidity_score = MarketAnalyzer.calculate_liquidity_score(car)
            car.probability_good_deal = MarketAnalyzer.calculate_final_probability(car)
    except Exception as e:
        logger.error(f"Score calculation error: {e}")
    
    # Sort by probability (best deals first)
    cars.sort(key=lambda x: x.probability_good_deal or 0, reverse=True)
    return cars


# ============================================================================
# Event Handlers
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    init_db()
    logger.info("Application started successfully")


# ============================================================================
# Web Routes
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Modern home page with search form"""
    return templates.TemplateResponse(
        "modern_index.html",
        {
            "request": request,
            "title": "Поиск выгодных автомобилей",
            "brands": ALL_BRANDS,
            "models_json": str(POPULAR_MODELS).replace("'", '"'),
        }
    )


@app.post("/search", response_class=HTMLResponse)
async def search_cars(
    request: Request,
    brand: str = Form(...),
    model: Optional[str] = Form(None),
    sources: List[str] = Form(default=["drom"]),
    limit: int = Form(default=20),
    year_min: int = Form(default=2015),
    year_max: int = Form(default=2026),
    mileage_min: int = Form(default=0),
    mileage_max: int = Form(default=300000),
    owners_min: int = Form(default=0),
    owners_max: int = Form(default=5),
    price_min: int = Form(default=0),
    price_max: int = Form(default=50000000),
    transmission: Optional[str] = Form(None),
    fuel: Optional[str] = Form(None),
    drive: Optional[str] = Form(None),
    body_type: Optional[str] = Form(None),
    region: Optional[str] = Form(None)
):
    """Handle car search with modern UI"""
    start_time = datetime.now()
    logger.info(f"Search request: {brand} {model}, sources={sources}")
    
    # Parse all sources
    enriched, errors = await parse_all_sources(
        brand=brand,
        model=model,
        sources=sources,
        limit=limit,
        region=region
    )
    
    logger.info(f"Total listings before filters: {len(enriched)}")
    
    # Apply filters
    filtered = apply_filters(
        enriched, year_min, year_max, mileage_min, mileage_max,
        owners_min, owners_max, price_min, price_max,
        transmission, fuel, drive, body_type, region
    )
    
    logger.info(f"Total listings after filters: {len(filtered)}")
    
    # Calculate scores
    scored_cars = calculate_scores(filtered)
    
    # Save to DB and prepare for display
    results_data = []
    for car in scored_cars:
        try:
            save_listing(car)
        except Exception as e:
            logger.error(f"DB save error: {e}")
        
        results_data.append({
            "title": car.title,
            "price": car.price,
            "year": car.year,
            "mileage": car.mileage,
            "region": car.region,
            "url": car.url,
            "platform": car.platform,
            "image_url": car.image_url or "/static/images/no-car-image.png",
            "market_price": car.market_price,
            "market_deviation": car.market_deviation,
            "probability": car.probability_good_deal,
            "liquidity": car.liquidity_score,
            "badge_class": get_badge_class(car.probability_good_deal),
            "owners": getattr(car, 'owners', None) or getattr(car, 'owners_count', None),
            "transmission": car.transmission,
            "fuel": car.fuel,
            "drive": car.drive,
            "body_type": car.body_type
        })
    
    # Cache results
    session_key = f"{brand}_{model}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    parsing_results[session_key] = {
        "data": results_data,
        "filters": {
            "brand": brand,
            "model": model,
            "year_range": f"{year_min}-{year_max}",
            "sources": sources
        }
    }
    
    search_time = (datetime.now() - start_time).total_seconds()
    
    return templates.TemplateResponse(
        "modern_results.html",
        {
            "request": request,
            "results": results_data,
            "brand": brand.capitalize(),
            "model": model.capitalize() if model else "Все модели",
            "total": len(results_data),
            "errors": errors,
            "sources_used": sources,
            "search_time": search_time
        }
    )


# ============================================================================
# API Routes
# ============================================================================

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0"
    }


@app.post("/api/search", response_model=SearchResultModel)
async def api_search_cars(search_request: SearchRequestModel):
    """API endpoint for car search"""
    start_time = datetime.now()
    logger.info(f"API search request: {search_request.brand} {search_request.model}")
    
    try:
        # Parse sources
        enriched, errors = await parse_all_sources(
            brand=search_request.brand,
            model=search_request.model,
            sources=search_request.sources,
            limit=search_request.limit,
            region=search_request.region
        )
        
        # Apply filters
        filtered = apply_filters(
            enriched,
            search_request.year_min, search_request.year_max,
            search_request.mileage_min, search_request.mileage_max,
            search_request.owners_min, search_request.owners_max,
            search_request.price_min, search_request.price_max,
            search_request.transmission, search_request.fuel,
            search_request.drive, search_request.body_type,
            search_request.region
        )
        
        # Calculate scores
        scored_cars = calculate_scores(filtered)
        
        # Convert to dict
        results = [car.model_dump() for car in scored_cars]
        
        search_time = (datetime.now() - start_time).total_seconds()
        
        return SearchResultModel(
            success=True,
            count=len(results),
            data=results,
            errors=errors,
            search_time=search_time
        )
        
    except Exception as e:
        logger.error(f"API search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/brands")
async def get_brands():
    """Get list of all supported brands"""
    return {"brands": ALL_BRANDS}


@app.get("/api/models/{brand}")
async def get_models(brand: str):
    """Get popular models for a brand"""
    brand_lower = brand.lower()
    models = POPULAR_MODELS.get(brand_lower, [])
    return {"brand": brand, "models": models}


@app.get("/api/results/{session_key}")
async def get_cached_results(session_key: str):
    """Get cached search results"""
    if session_key in parsing_results:
        return parsing_results[session_key]
    raise HTTPException(status_code=404, detail="Results not found")


# ============================================================================
# Error Handlers
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error": exc.detail}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": "Internal server error"}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
