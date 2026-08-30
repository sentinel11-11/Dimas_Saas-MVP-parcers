import os
import sqlite3
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from typing import List, Optional
from loguru import logger

from datetime import datetime
import json
from app.database.models import Base, CarListingORM, SavedSearchORM

os.makedirs("data", exist_ok=True)
DB_PATH = "data/cars.db"

# SQLite connection for legacy compatibility
sqlite_conn = sqlite3.connect(DB_PATH, check_same_thread=False)

# SQLAlchemy setup
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db():
    """Инициализация базы данных через SQLAlchemy"""
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized with SQLAlchemy")


def save_listing(car):
    """Сохранение объявления через SQLAlchemy ORM"""
    session = SessionLocal()
    try:
        listing = CarListingORM(
            title=car.title,
            price=car.price,
            year=car.year,
            mileage=car.mileage,
            owners=car.owners,
            engine_volume=car.engine_volume,
            horsepower=car.horsepower,
            transmission=car.transmission,
            drive=car.drive,
            body_type=car.body_type,
            fuel_type=getattr(car, "fuel", None),
            region=car.region,
            accidents=car.accidents,
            pts=car.pts,
            market_score=car.market_score,
            final_score=car.probability_good_deal,
            url=car.url,
            source=car.platform
        )
        
        # Проверка на дубликаты
        existing = session.query(CarListingORM).filter(CarListingORM.url == car.url).first()
        if existing:
            # Обновление существующей записи
            for key in (
                "title", "price", "year", "mileage", "owners", "engine_volume",
                "horsepower", "transmission", "drive", "body_type", "fuel_type",
                "region", "accidents", "pts", "market_score", "final_score", "source",
            ):
                setattr(existing, key, getattr(listing, key))
            session.commit()
            logger.debug(f"Updated listing: {car.url}")
        else:
            session.add(listing)
            session.commit()
            logger.debug(f"Saved new listing: {car.url}")
            
    except Exception as e:
        session.rollback()
        logger.error(f"Error saving listing: {e}")
        raise
    finally:
        session.close()


def get_all_listings() -> List[CarListingORM]:
    """Получить все объявления из БД"""
    session = SessionLocal()
    try:
        listings = session.query(CarListingORM).all()
        return listings
    finally:
        session.close()


def get_listing_by_url(url: str) -> Optional[CarListingORM]:
    """Получить объявление по URL"""
    session = SessionLocal()
    try:
        listing = session.query(CarListingORM).filter(CarListingORM.url == url).first()
        return listing
    finally:
        session.close()


def delete_listing(url: str):
    """Удалить объявление по URL"""
    session = SessionLocal()
    try:
        session.query(CarListingORM).filter(CarListingORM.url == url).delete()
        session.commit()
        logger.info(f"Deleted listing: {url}")
    except Exception as e:
        session.rollback()
        logger.error(f"Error deleting listing: {e}")
        raise
    finally:
        session.close()


MAX_SAVED_SEARCHES = 3


def save_search(email: str, params: dict, last_min_price: int = 0, last_count: int = 0):
    session = SessionLocal()
    try:
        email = (email or "").strip().lower()
        q = session.query(SavedSearchORM)
        if email:
            q = q.filter(SavedSearchORM.email == email)
        if q.count() >= MAX_SAVED_SEARCHES:
            oldest = q.order_by(SavedSearchORM.id.asc()).first()
            if oldest:
                session.delete(oldest)
        row = SavedSearchORM(
            email=email,
            brand=params.get("brand") or "",
            model=params.get("model") or "",
            params_json=json.dumps(params, ensure_ascii=False),
            last_min_price=last_min_price,
            last_count=last_count,
            created_at=datetime.utcnow().isoformat(),
        )
        session.add(row)
        session.commit()
        return row.id
    except Exception as e:
        session.rollback()
        logger.error(f"save_search error: {e}")
        raise
    finally:
        session.close()


def list_saved_searches(email: str = "") -> List[SavedSearchORM]:
    session = SessionLocal()
    try:
        q = session.query(SavedSearchORM)
        if email:
            q = q.filter(SavedSearchORM.email == email.strip().lower())
        return q.order_by(SavedSearchORM.id.desc()).all()
    finally:
        session.close()


def get_saved_search(search_id: int) -> Optional[SavedSearchORM]:
    session = SessionLocal()
    try:
        return session.query(SavedSearchORM).filter(SavedSearchORM.id == search_id).first()
    finally:
        session.close()


def update_saved_search_stats(search_id: int, last_min_price: int, last_count: int):
    session = SessionLocal()
    try:
        row = session.query(SavedSearchORM).filter(SavedSearchORM.id == search_id).first()
        if not row:
            return
        row.last_min_price = last_min_price
        row.last_count = last_count
        session.commit()
    finally:
        session.close()


def delete_saved_search(search_id: int):
    session = SessionLocal()
    try:
        session.query(SavedSearchORM).filter(SavedSearchORM.id == search_id).delete()
        session.commit()
    finally:
        session.close()
