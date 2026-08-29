import sqlite3
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from typing import List, Optional
from loguru import logger

from app.database.models import Base, CarListingORM

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
            for key, value in vars(listing).items():
                if not key.startswith('_'):
                    setattr(existing, key, value)
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
