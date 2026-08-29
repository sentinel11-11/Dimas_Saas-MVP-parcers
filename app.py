"""
Streamlit интерфейс для парсинга автомобилей
Запуск: streamlit run app.py --server.headless true
"""
import streamlit as st
import asyncio
from loguru import logger
import time
from datetime import datetime

# Импорт модулей
from app.config import config
from app.database.db import init_db, save_listing, get_all_listings
from app.parsers.drom.drom_parser import DromParser
from app.parsers.drom.drom_detail_parser import DromDetailParser
from app.parsers.autoru.autoru_parser import AutoRuParser
from app.parsers.avito.avito_parser import AvitoParser
from app.core.normalizer import DataNormalizer
from app.core.market import MarketEngine
from app.core.market_analyzer import MarketAnalyzer
from app.models.car_listing import CarListing

# Настройка страницы
st.set_page_config(
    page_title="Car Parser MVP",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Список всех марок автомобилей (расширенный - поддерживает любые марки)
ALL_BRANDS = [
    "audi", "bmw", "chevrolet", "chrysler", "citroen", "dodge", "fiat", "ford",
    "geely", "genesis", "gmc", "honda", "hyundai", "infiniti", "jaguar", "jeep",
    "kia", "land rover", "lexus", "mazda", "mercedes", "mini", "mitsubishi",
    "nissan", "opel", "peugeot", "porsche", "renault", "skoda", "subaru",
    "suzuki", "toyota", "volkswagen", "volvo", "lada", "gaz", "uaz",
    "chery", "haval", "exeed", "tank", "omoda", "jaecoo", "dongfeng", 
    "foton", "great wall", "lifan", "brilliance", "zx auto", "jac", "byd",
    "changan", "faaw", "hawtai", "zotye", "soueast", "qoros", "wey", "lynk & co",
    "polestar", "lixiang", "nio", "xpeng", "seres", "voyah", "hongqi", "maxus",
    "acura", "alfa romeo", "aston martin", "bentley", "bugatti", "cadillac",
    "dacia", "ds", "ferrari", "hummer", "isuzu", "koenigsegg", "lamborghini",
    "maserati", "mclaren", "pagani", "rolls-royce", "tesla", "lotus", "smart",
    "ssangyong", "daewoo", "proton", "tata", "mahindra", "maruti", "holden",
    "datsun", "ravon", "tagaz", "doninvest", "bogdan", "zaz"
]

# Популярные модели для быстрого выбора (можно добавлять любые)
POPULAR_MODELS = {
    "bmw": ["1 серия", "2 серия", "3 серия", "4 серия", "5 серия", "X1", "X3", "X5", "X6"],
    "mercedes": ["A-Class", "C-Class", "E-Class", "G-Class", "GLA", "GLC", "GLE", "S-Class"],
    "audi": ["A3", "A4", "A6", "Q3", "Q5", "Q7", "Q8"],
    "toyota": ["Camry", "Corolla", "RAV4", "Land Cruiser", "Highlander"],
    "honda": ["Accord", "Civic", "CR-V", "Pilot"],
    "nissan": ["Almera", "Juke", "Kashqai", "Qashqai", "X-Trail"],
    "volkswagen": ["Golf", "Jetta", "Passat", "Polo", "Tiguan"],
    "ford": ["Focus", "Kuga", "Mondeo", "Mustang"],
    "hyundai": ["Elantra", "Santa Fe", "Sonata", "Tucson"],
    "kia": ["Ceed", "K5", "Rio", "Sorento", "Sportage"],
    "lexus": ["ES", "LX", "NX", "RX"],
    "mazda": ["3", "6", "CX-5", "CX-9"],
    "lada": ["Granta", "Vesta", "Niva"],
}

def get_badge_color(probability):
    """Определение цвета бейджа"""
    if probability >= 0.8:
        return "🟢"
    elif probability >= 0.6:
        return "🔵"
    elif probability >= 0.4:
        return "🟡"
    else:
        return "🔴"

def parse_cars(brand, model, sources, limit, year_min, year_max, mileage_min, mileage_max, 
               owners_min, owners_max, price_min, price_max, transmission, fuel, drive, body_type, region):
    """Функция парсинга с применением фильтров"""
    enriched = []
    errors = []
    
    # 1. Парсинг Drom
    if "drom" in sources:
        try:
            drom_parser = DromParser()
            drom_detail_parser = DromDetailParser()
            filters = {"brand": brand, "model": model}
            drom_ads = drom_parser.search(filters)
            logger.info(f"DROM FOUND: {len(drom_ads)}")
            
            for ad in drom_ads[:limit]:
                try:
                    details = drom_detail_parser.parse(ad["url"])
                    if details:
                        ad.update(details)
                    normalized = DataNormalizer.normalize(ad)
                    normalized["platform"] = "drom"
                    car = CarListing(**normalized)
                    enriched.append(car)
                except Exception as e:
                    logger.error(f"DROM DETAIL ERROR: {e}")
                    errors.append(f"Drom: {str(e)}")
        except Exception as e:
            logger.error(f"DROM SEARCH ERROR: {e}")
            errors.append(f"Drom поиск: {str(e)}")
    
    # 2. Парсинг Avito
    if "avito" in sources:
        try:
            import os
            proxy_list_str = os.getenv("AVITO_PROXIES", "")
            avito_proxy_list = [p.strip() for p in proxy_list_str.split(",") if p.strip()] if proxy_list_str else None
            
            avito_parser = AvitoParser(proxy_list=avito_proxy_list)
            avito_ads = avito_parser.search({
                "brand": brand, 
                "model": model, 
                "limit": limit, 
                "target_region": region if region else "rossiya"
            })
            logger.info(f"AVITO FOUND: {len(avito_ads)}")
            
            for ad in avito_ads:
                try:
                    normalized = DataNormalizer.normalize(ad)
                    normalized["platform"] = "avito"
                    if not normalized.get("url") or not normalized.get("title"):
                        continue
                    car = CarListing(**normalized)
                    enriched.append(car)
                except Exception as e:
                    logger.error(f"AVITO NORMALIZATION ERROR: {e}")
                    errors.append(f"Avito: {str(e)}")
        except Exception as e:
            logger.error(f"AVITO SEARCH ERROR: {e}")
            errors.append(f"Avito поиск: {str(e)}")
    
    # 3. Парсинг Auto.ru
    if "autoru" in sources:
        try:
            import os
            autoru_proxy_list_str = os.getenv("AUTORU_PROXIES", "")
            autoru_proxy_list = [p.strip() for p in autoru_proxy_list_str.split(",") if p.strip()] if autoru_proxy_list_str else None
            
            autoru_parser = AutoRuParser(headless=True, proxy_list=autoru_proxy_list)
            
            async def run_autoru():
                return await autoru_parser.search(
                    filters={"brand": brand, "model": model},
                    limit=limit
                )
            
            autoru_cars = asyncio.run(run_autoru())
            logger.info(f"AUTO.RU FOUND: {len(autoru_cars)}")
            
            for car_data in autoru_cars:
                try:
                    if isinstance(car_data, CarListing):
                        enriched.append(car_data)
                    else:
                        normalized = DataNormalizer.normalize(car_data)
                        normalized["platform"] = "autoru"
                        car = CarListing(**normalized)
                        enriched.append(car)
                except Exception as e:
                    logger.error(f"AUTORU NORMALIZATION ERROR: {e}")
                    errors.append(f"Auto.ru: {str(e)}")
        except Exception as e:
            logger.error(f"AUTORU SEARCH ERROR: {e}")
            errors.append(f"Auto.ru поиск: {str(e)}")
    
    # Применение фильтров
    filtered_enriched = []
    for car in enriched:
        try:
            if car.year and (car.year < year_min or car.year > year_max):
                continue
            if car.mileage and (car.mileage < mileage_min or car.mileage > mileage_max):
                continue
            if car.owners_count and (car.owners_count < owners_min or car.owners_count > owners_max):
                continue
            if car.price and (car.price < price_min or car.price > price_max):
                continue
            if transmission and car.transmission and car.transmission.lower() != transmission.lower():
                continue
            if fuel and car.fuel and car.fuel.lower() != fuel.lower():
                continue
            if drive and car.drive and car.drive.lower() != drive.lower():
                continue
            if body_type and car.body_type and car.body_type.lower() != body_type.lower():
                continue
            if region and car.region and region.lower() not in car.region.lower():
                continue
            
            filtered_enriched.append(car)
        except Exception as e:
            logger.error(f"FILTER ERROR: {e}")
            filtered_enriched.append(car)
    
    enriched = filtered_enriched
    
    # Расчет скоринга
    if enriched:
        market = MarketEngine([x.model_dump() for x in enriched])
        
        for car in enriched:
            car.market_score = market.price_score(car.model_dump())
            car.market_price = MarketAnalyzer.calculate_market_price(
                [x.model_dump() for x in enriched], car
            )
            car.market_deviation = MarketAnalyzer.calculate_market_deviation(
                car.price, car.market_price
            )
            car.liquidity_score = MarketAnalyzer.calculate_liquidity_score(car)
            car.probability_good_deal = MarketAnalyzer.calculate_final_probability(car)
    
    # Сортировка
    enriched.sort(key=lambda x: x.probability_good_deal or 0, reverse=True)
    
    # Сохранение в БД
    for car in enriched:
        try:
            save_listing(car)
        except Exception as e:
            logger.error(f"DB SAVE ERROR: {e}")
    
    return enriched, errors

def main():
    st.title("🚗 Car Parser MVP")
    st.markdown("**Автоматический анализ автомобильных объявлений**")
    
    # Инициализация сессии
    if 'results' not in st.session_state:
        st.session_state.results = []
    if 'errors' not in st.session_state:
        st.session_state.errors = []
    if 'search_performed' not in st.session_state:
        st.session_state.search_performed = False
    
    # Боковая панель с фильтрами
    with st.sidebar:
        st.header("🔍 Параметры поиска")
        
        # Выбор марки и модели (без жесткого значения по умолчанию)
        brand_index = 0
        if config.BRAND and config.BRAND.lower() in ALL_BRANDS:
            brand_index = ALL_BRANDS.index(config.BRAND.lower())
        brand = st.selectbox("Марка", ALL_BRANDS, index=brand_index)
        
        # Динамический список моделей + возможность ввода своей модели
        models_list = POPULAR_MODELS.get(brand, [])
        model_input = st.text_input("Модель", placeholder="Введите модель или выберите из списка", value="")
        if not model_input and models_list:
            selected_model = st.selectbox("Или выберите из популярных", [""] + models_list, index=0)
            model = selected_model if selected_model else ""
        else:
            model = model_input.strip().lower() if model_input else ""
        
        # Источники
        sources = st.multiselect(
            "Источники",
            ["drom", "avito", "autoru"],
            default=["drom"]
        )
        
        # Лимит
        limit = st.slider("Максимум объявлений", 5, 50, 20)
        
        st.divider()
        st.subheader("📊 Фильтры")
        
        # Год
        col1, col2 = st.columns(2)
        with col1:
            year_min = st.number_input("Год от", min_value=2000, max_value=2026, value=2018)
        with col2:
            year_max = st.number_input("Год до", min_value=2000, max_value=2026, value=2026)
        
        # Пробег
        col3, col4 = st.columns(2)
        with col3:
            mileage_min = st.number_input("Пробег от (км)", min_value=0, max_value=500000, value=0)
        with col4:
            mileage_max = st.number_input("Пробег до (км)", min_value=0, max_value=500000, value=300000)
        
        # Владельцы
        col5, col6 = st.columns(2)
        with col5:
            owners_min = st.number_input("Владельцы от", min_value=0, max_value=10, value=0)
        with col6:
            owners_max = st.number_input("Владельцы до", min_value=0, max_value=10, value=3)
        
        # Цена
        col7, col8 = st.columns(2)
        with col7:
            price_min = st.number_input("Цена от (₽)", min_value=0, max_value=100000000, value=0, step=100000)
        with col8:
            price_max = st.number_input("Цена до (₽)", min_value=0, max_value=100000000, value=10000000, step=100000)
        
        st.divider()
        st.subheader("⚙️ Дополнительные фильтры")
        
        # Трансмиссия
        transmission = st.selectbox("Коробка", ["", "автомат", "механика", "робот", "вариатор"])
        
        # Топливо
        fuel = st.selectbox("Топливо", ["", "бензин", "дизель", "гибрид", "электро"])
        
        # Привод
        drive = st.selectbox("Привод", ["", "передний", "задний", "полный"])
        
        # Кузов
        body_type = st.selectbox("Кузов", ["", "седан", "внедорожник", "хэтчбек", "универсал", "купе", "кабриолет"])
        
        # Регион
        region = st.text_input("Регион", placeholder="например: Москва")
        
        # Кнопка поиска
        st.divider()
        search_button = st.button("🚀 Начать поиск", type="primary", use_container_width=True)
    
    # Основная область
    if search_button:
        if not sources:
            st.error("Выберите хотя бы один источник!")
        else:
            # Окно загрузки с таймером
            progress_bar = st.progress(0)
            status_text = st.empty()
            timer_placeholder = st.empty()
            details_placeholder = st.empty()
            
            start_time = time.time()
            
            # Этапы парсинга
            stages = [
                ("Подготовка...", 0.1),
                ("Парсинг Drom...", 0.3),
                ("Парсинг Avito...", 0.5),
                ("Парсинг Auto.ru...", 0.7),
                ("Анализ рынка...", 0.85),
                ("Расчет ликвидности...", 0.95),
                ("Готово!", 1.0)
            ]
            
            for stage_name, progress in stages:
                elapsed = time.time() - start_time
                timer_placeholder.metric("⏱️ Время выполнения", f"{elapsed:.1f} сек")
                status_text.text(stage_name)
                progress_bar.progress(progress)
                
                if progress < 1.0:
                    time.sleep(0.5)  # Имитация работы
            
            # Запуск парсинга
            status_text.text("Выполняется парсинг...")
            enriched, errors = parse_cars(
                brand, model, sources, limit,
                year_min, year_max, mileage_min, mileage_max,
                owners_min, owners_max, price_min, price_max,
                transmission, fuel, drive, body_type, region
            )
            
            # Сохранение результатов
            st.session_state.results = enriched
            st.session_state.errors = errors
            st.session_state.search_performed = True
            st.session_state.filters = {
                "brand": brand,
                "model": model,
                "year_range": f"{year_min}-{year_max}",
                "mileage_range": f"{mileage_min}-{mileage_max}",
                "owners_range": f"{owners_min}-{owners_max}",
                "price_range": f"{price_min:,}-{price_max:,}",
                "transmission": transmission or "Любая",
                "fuel": fuel or "Любое",
                "drive": drive or "Любой",
                "body_type": body_type or "Любой",
                "region": region or "Все регионы"
            }
            
            progress_bar.empty()
            status_text.empty()
            timer_placeholder.empty()
            details_placeholder.empty()
            
            st.success(f"Найдено {len(enriched)} объявлений!")
    
    # Отображение результатов
    if st.session_state.search_performed and st.session_state.results:
        # Отображение примененных фильтров
        with st.expander("📋 Примененные фильтры", expanded=False):
            filters = st.session_state.filters
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Марка", filters["brand"].capitalize())
                st.metric("Модель", filters["model"].capitalize() if filters["model"] else "Любая")
                st.metric("Годы", filters["year_range"])
            with col2:
                st.metric("Пробег", filters["mileage_range"])
                st.metric("Владельцы", filters["owners_range"])
                st.metric("Цена", f"{filters['price_range']} ₽")
            with col3:
                st.metric("Коробка", filters["transmission"])
                st.metric("Топливо", filters["fuel"])
                st.metric("Привод", filters["drive"])
                st.metric("Кузов", filters["body_type"])
                st.metric("Регион", filters["region"])
        
        if st.session_state.errors:
            with st.warning("⚠️ Ошибки при парсинге"):
                for error in st.session_state.errors:
                    st.write(f"- {error}")
        
        # Таблица результатов
        st.subheader(f"🏆 Топ-{len(st.session_state.results)} выгодных предложений")
        
        results_data = []
        for i, car in enumerate(st.session_state.results, 1):
            results_data.append({
                "№": i,
                "Авто": car.title,
                "Цена": f"{car.price:,} ₽" if car.price else "N/A",
                "Год": car.year,
                "Пробег": f"{car.mileage:,} км" if car.mileage else "N/A",
                "Владельцы": car.owners_count,
                "Регион": car.region,
                "Рыночная цена": f"{car.market_price:,} ₽" if car.market_price else "N/A",
                "Отклонение": f"{car.market_deviation:.1f}%" if car.market_deviation else "N/A",
                "Ликвидность": f"{car.liquidity_score:.2f}" if car.liquidity_score else "N/A",
                "Вероятность": f"{car.probability_good_deal:.0%}" if car.probability_good_deal else "N/A",
                "Оценка": get_badge_color(car.probability_good_deal),
                "Ссылка": car.url
            })
        
        st.dataframe(
            results_data,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Оценка": st.column_config.TextColumn("Оценка"),
                "Ссылка": st.column_config.LinkColumn("Ссылка")
            }
        )
        
        # Детальная информация по лучшим предложениям
        if len(st.session_state.results) > 0:
            st.subheader("📌 Детальный разбор топ-3")
            for i, car in enumerate(st.session_state.results[:3], 1):
                with st.container():
                    col1, col2, col3 = st.columns([2, 1, 1])
                    with col1:
                        st.markdown(f"**{i}. {car.title}**")
                        st.write(f"💰 Цена: **{car.price:,} ₽**")
                        st.write(f"📅 Год: {car.year} | 🛣️ Пробег: {car.mileage:,} км" if car.mileage else "")
                        st.write(f"👥 Владельцев: {car.owners_count}" if car.owners_count else "")
                        st.write(f"📍 {car.region}" if car.region else "")
                    with col2:
                        st.metric("Рыночная цена", f"{car.market_price:,} ₽" if car.market_price else "N/A")
                        st.metric("Отклонение", f"{car.market_deviation:.1f}%" if car.market_deviation else "N/A")
                    with col3:
                        st.metric("Ликвидность", f"{car.liquidity_score:.2f}" if car.liquidity_score else "N/A")
                        st.metric("Вероятность", f"{car.probability_good_deal:.0%}" if car.probability_good_deal else "N/A")
                    st.divider()
    
    elif st.session_state.search_performed and not st.session_state.results:
        st.warning("По вашему запросу ничего не найдено. Попробуйте расширить фильтры.")
    
    elif not st.session_state.search_performed:
        st.info("👈 Выберите параметры поиска в боковой панели и нажмите «Начать поиск»")

if __name__ == "__main__":
    init_db()
    main()
