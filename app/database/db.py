import os
import sqlite3
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from typing import List, Optional
from loguru import logger

from datetime import datetime
import json
from sqlalchemy import text

from app.database.models import Base, CarListingORM, SavedSearchORM, UserORM, SearchLogORM

os.makedirs("data", exist_ok=True)
DB_PATH = "data/cars.db"

# SQLite connection for legacy compatibility
sqlite_conn = sqlite3.connect(DB_PATH, check_same_thread=False)

# SQLAlchemy setup
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def _migrate():
    with engine.connect() as conn:
        try:
            cols = [r[1] for r in conn.execute(text("PRAGMA table_info(saved_searches)"))]
            if cols and "user_id" not in cols:
                conn.execute(text("ALTER TABLE saved_searches ADD COLUMN user_id INTEGER DEFAULT 0"))
                conn.commit()
        except Exception as e:
            logger.warning(f"migrate skip: {e}")


def seed_admin():
    import os
    from datetime import datetime
    from app.web.auth import hash_password

    email = (os.getenv("ADMIN_EMAIL") or "admin@dimas.local").strip().lower()
    password = os.getenv("ADMIN_PASSWORD") or "dimas-admin"
    session = SessionLocal()
    try:
        existing = session.query(UserORM).filter(UserORM.email == email).first()
        if existing:
            if not existing.is_admin:
                existing.is_admin = 1
                session.commit()
            return
        if session.query(UserORM).filter(UserORM.is_admin == 1).first():
            return
        user = UserORM(
            email=email,
            password_hash=hash_password(password),
            name="Админ",
            is_admin=1,
            created_at=datetime.utcnow().isoformat(),
        )
        session.add(user)
        session.commit()
        logger.info(f"Seeded admin {email}")
    except Exception as e:
        session.rollback()
        logger.error(f"seed_admin: {e}")
    finally:
        session.close()


def init_db():
    Base.metadata.create_all(bind=engine)
    _migrate()
    seed_admin()
    logger.info("Database initialized with SQLAlchemy")


def create_user(email: str, password: str, name: str = "") -> UserORM:
    from datetime import datetime
    from app.web.auth import hash_password

    session = SessionLocal()
    try:
        email = email.strip().lower()
        if session.query(UserORM).filter(UserORM.email == email).first():
            raise ValueError("email_taken")
        user = UserORM(
            email=email,
            password_hash=hash_password(password),
            name=(name or "").strip()[:80],
            is_admin=0,
            created_at=datetime.utcnow().isoformat(),
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def find_user_by_email(email: str) -> Optional[UserORM]:
    session = SessionLocal()
    try:
        return session.query(UserORM).filter(UserORM.email == (email or "").strip().lower()).first()
    finally:
        session.close()


def list_users(limit: int = 100) -> List[UserORM]:
    session = SessionLocal()
    try:
        return session.query(UserORM).order_by(UserORM.id.desc()).limit(limit).all()
    finally:
        session.close()


def touch_login(user_id: int):
    from datetime import datetime
    session = SessionLocal()
    try:
        row = session.query(UserORM).filter(UserORM.id == user_id).first()
        if row:
            row.last_login = datetime.utcnow().isoformat()
            session.commit()
    finally:
        session.close()


def log_search(user_id: int, email: str, brand: str, model: str, sources, total: int):
    from datetime import datetime
    session = SessionLocal()
    try:
        src = ",".join(sources) if isinstance(sources, list) else str(sources or "drom")
        session.add(SearchLogORM(
            user_id=user_id or 0,
            email=email or "",
            brand=brand or "",
            model=model or "",
            sources=src,
            total=int(total or 0),
            created_at=datetime.utcnow().isoformat(),
        ))
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"log_search: {e}")
    finally:
        session.close()


def list_search_logs(limit: int = 40) -> List[SearchLogORM]:
    session = SessionLocal()
    try:
        return session.query(SearchLogORM).order_by(SearchLogORM.id.desc()).limit(limit).all()
    finally:
        session.close()


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


def save_search(email: str, params: dict, last_min_price: int = 0, last_count: int = 0, user_id: int = 0):
    session = SessionLocal()
    try:
        email = (email or "").strip().lower()
        q = session.query(SavedSearchORM)
        if user_id:
            q = q.filter(SavedSearchORM.user_id == user_id)
        elif email:
            q = q.filter(SavedSearchORM.email == email)
        if q.count() >= MAX_SAVED_SEARCHES:
            oldest = q.order_by(SavedSearchORM.id.asc()).first()
            if oldest:
                session.delete(oldest)
        row = SavedSearchORM(
            email=email,
            user_id=user_id or 0,
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


def list_saved_searches(email: str = "", user_id: int = 0) -> List[SavedSearchORM]:
    session = SessionLocal()
    try:
        q = session.query(SavedSearchORM)
        if user_id:
            q = q.filter(SavedSearchORM.user_id == user_id)
        elif email:
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
