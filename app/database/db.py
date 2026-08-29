import sqlite3


DB_PATH = "data/cars.db"

conn = sqlite3.connect(
    DB_PATH,
    check_same_thread=False
)


def init_db():

    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS listings (

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        url TEXT UNIQUE,
        title TEXT,
        platform TEXT,

        brand TEXT,
        model TEXT,

        price INTEGER,
        year INTEGER,
        mileage INTEGER,

        engine_volume REAL,
        horsepower INTEGER,

        transmission TEXT,
        drive TEXT,
        body_type TEXT,

        owners INTEGER,
        accidents INTEGER,

        pts TEXT,
        region TEXT,

        market_score REAL,
        probability_good_deal REAL,

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()


def save_listing(car):

    cursor = conn.cursor()

    cursor.execute("""
    INSERT OR REPLACE INTO listings (

        url,
        title,
        platform,

        brand,
        model,

        price,
        year,
        mileage,

        engine_volume,
        horsepower,

        transmission,
        drive,
        body_type,

        owners,
        accidents,

        pts,
        region,

        market_score,
        probability_good_deal

    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (

        car.url,
        car.title,
        car.platform,

        car.brand,
        car.model,

        car.price,
        car.year,
        car.mileage,

        car.engine_volume,
        car.horsepower,

        car.transmission,
        car.drive,
        car.body_type,

        car.owners,
        car.accidents,

        car.pts,
        car.region,

        car.market_score,
        car.probability_good_deal
    ))

    conn.commit()