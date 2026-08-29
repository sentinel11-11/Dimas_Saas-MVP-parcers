import streamlit as st
import pandas as pd
import asyncio
import os
from dotenv import load_dotenv
from loguru import logger
from datetime import datetime
import time

# Загрузка переменных окружения
load_dotenv()

# Импорт наших модулей
from app.parsers.drom.drom_parser import DromParser
from app.parsers.avito.avito_parser import AvitoParser
from app.parsers.autoru.autoru_parser import AutoRuParser
from app.models.car_listing import CarSearchConfig
from app.core.market_analyzer import MarketAnalyzer
from app.core.normalizer import DataNormalizer

# Настройка страницы
st.set_page_config(
    page_title="Car Parser MVP - Анализ рынка авто",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Стили CSS
st.markdown("""
    <style>
    .main-header {font-size: 2.5rem; font-weight: bold; color: #1E3A8A; text-align: center;}
    .sub-header {font-size: 1.2rem; color: #6B7280; text-align: center; margin-bottom: 2rem;}
    .metric-card {background: white; padding: 1rem; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);}
    .stButton>button {width: 100%; background-color: #1E3A8A; color: white; font-weight: bold;}
    .stButton>button:hover {background-color: #1E40AF;}
    </style>
""", unsafe_allow_html=True)

# Инициализация сессионных переменных
if 'search_started' not in st.session_state:
    st.session_state.search_started = False
if 'search_results' not in st.session_state:
    st.session_state.search_results = []
if 'search_completed' not in st.session_state:
    st.session_state.search_completed = False

def main():
    # Заголовок
    st.markdown('<div class="main-header">🚗 Car Parser MVP</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Интеллектуальный поиск выгодных автомобилей на Drom, Avito и Auto.ru</div>', unsafe_allow_html=True)

    # Боковая панель с фильтрами
    with st.sidebar:
        st.header("🔍 Параметры поиска")
        
        # Основные параметры - БЕЗ значений по умолчанию для марки/модели
        brand = st.text_input("Марка автомобиля", placeholder="Например: Audi, BMW, Toyota", value="").strip()
        model = st.text_input("Модель автомобиля", placeholder="Например: Q3, X5, Camry", value="").strip()
        
        col1, col2 = st.columns(2)
        with col1:
            year_min = st.number_input("Год от", min_value=1990, max_value=2026, value=2015, step=1)
        with col2:
            year_max = st.number_input("Год до", min_value=1990, max_value=2026, value=2026, step=1)
            
        col3, col4 = st.columns(2)
        with col3:
            price_min = st.number_input("Цена от (₽)", min_value=0, value=500000, step=50000)
        with col4:
            price_max = st.number_input("Цена до (₽)", min_value=0, value=10000000, step=500000)
            
        col5, col6 = st.columns(2)
        with col5:
            mileage_min = st.number_input("Пробег от (км)", min_value=0, value=0, step=1000)
        with col6:
            mileage_max = st.number_input("Пробег до (км)", min_value=0, value=300000, step=1000)
            
        owners_min = st.number_input("Владельцев от", min_value=0, max_value=10, value=0, step=1)
        owners_max = st.number_input("Владельцев до", min_value=0, max_value=10, value=4, step=1)
        
        st.divider()
        st.subheader("Детальные настройки")
        
        transmission = st.selectbox("Коробка передач", ["Любая", "Автомат", "Механика", "Робот", "Вариатор"], index=0)
        fuel = st.selectbox("Тип топлива", ["Любое", "Бензин", "Дизель", "Электро", "Гибрид", "Газ"], index=0)
        drive = st.selectbox("Привод", ["Любой", "Передний", "Задний", "Полный"], index=0)
        body_type = st.selectbox("Кузов", ["Любой", "Седан", "Внедорожник", "Кроссовер", "Хэтчбек", "Универсал", "Купе", "Кабриолет"], index=0)
        
        region = st.text_input("Регион поиска", placeholder="Например: Москва, СПб", value="").strip()
        has_accidents = st.checkbox("Только без ДТП", value=False)
        
        st.divider()
        
        # Кнопка запуска
        start_button = st.button("🚀 Начать поиск", type="primary", use_container_width=True)
        
        if start_button:
            if not brand:
                st.error("⚠️ Пожалуйста, укажите марку автомобиля")
            else:
                st.session_state.search_started = True
                st.session_state.search_completed = False
                st.rerun()

    # Основная область
    if st.session_state.search_started and not st.session_state.search_completed:
        # Экран загрузки с прогрессом
        st.markdown("### ⏳ Идет поиск и анализ объявлений...")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        details_text = st.empty()
        
        # Конфигурация поиска
        search_config = CarSearchConfig(
            brand=brand,
            model=model,
            year_min=year_min,
            year_max=year_max,
            price_min=price_min,
            price_max=price_max,
            mileage_min=mileage_min,
            mileage_max=mileage_max,
            owners_min=owners_min,
            owners_max=owners_max,
            transmission=transmission if transmission != "Любая" else None,
            fuel=fuel if fuel != "Любое" else None,
            drive=drive if drive != "Любой" else None,
            body_type=body_type if body_type != "Любой" else None,
            region=region if region else None,
            exclude_accidents=has_accidents
        )
        
        all_cars = []
        sources = [
            ("Drom", DromParser()),
            ("Avito", AvitoParser()),
            ("Auto.ru", AutoRuParser())
        ]
        
        total_steps = len(sources) * 2  # Поиск + Детали
        
        try:
            for i, (source_name, parser) in enumerate(sources):
                status_text.text(f"📡 Сканирование источника: {source_name}...")
                details_text.text(f"Подключение к {source_name}...")
                
                # Асинхронный запуск парсинга
                cars = asyncio.run(parser.search(search_config))
                
                if cars:
                    details_text.text(f"✅ Найдено {len(cars)} объявлений на {source_name}")
                    all_cars.extend(cars)
                else:
                    details_text.text(f"⚠️ На {source_name} объявлений не найдено или ошибка доступа")
                
                progress_bar.progress((i + 1) / total_steps)
                time.sleep(0.5) # Небольшая задержка между источниками
            
            # Обработка результатов
            if all_cars:
                status_text.text("🧮 Расчет ликвидности и вероятности сделки...")
                processed_cars = []
                normalizer = DataNormalizer()
                analyzer = MarketAnalyzer()
                
                for idx, car in enumerate(all_cars):
                    # Нормализация данных
                    normalized_car = normalizer.normalize(car, search_config)
                    
                    # Расчет ликвидности через MarketAnalyzer
                    liquidity_data = analyzer.calculate_liquidity(normalized_car)
                    normalized_car['liquidity_score'] = liquidity_data.get('score', 50)
                    
                    # Расчет вероятности сделки
                    deal_prob = liquidity_data.get('deal_probability', 75)
                    normalized_car['deal_probability'] = deal_prob
                    
                    processed_cars.append(normalized_car)
                    progress_bar.progress(0.7 + (idx / len(all_cars)) * 0.3)
                
                st.session_state.search_results = processed_cars
                st.session_state.search_completed = True
                st.rerun()
            else:
                st.warning("😕 По вашим параметрам ничего не найдено. Попробуйте расширить фильтры.")
                st.session_state.search_started = False
                st.rerun()
                
        except Exception as e:
            st.error(f"❌ Произошла ошибка при парсинге: {str(e)}")
            logger.error(f"Parsing error: {e}")
            st.session_state.search_started = False
            st.rerun()

    elif st.session_state.search_completed and st.session_state.search_results:
        # Отображение результатов
        st.success(f"✅ Поиск завершен! Найдено {len(st.session_state.search_results)} автомобилей.")
        
        # Фильтры результатов (дополнительно)
        res_col1, res_col2 = st.columns([3, 1])
        with res_col1:
            st.subheader("📊 Результаты анализа")
        
        # Преобразование в DataFrame
        df = pd.DataFrame(st.session_state.search_results)
        
        # Сортировка по умолчанию (лучшая сделка)
        if 'deal_probability' in df.columns:
            df = df.sort_values(by='deal_probability', ascending=False)
        
        # Проверка наличия колонки image_url
        has_images = 'image_url' in df.columns and not df['image_url'].isna().all()
        
        # Отображение таблицы с настройками колонок
        column_config = {
            "price": st.column_config.NumberColumn("Цена (₽)", format="%d ₽"),
            "year": st.column_config.NumberColumn("Год"),
            "mileage": st.column_config.NumberColumn("Пробег (км)", format="%d км"),
            "liquidity_score": st.column_config.ProgressColumn(
                "Ликвидность",
                format="%d%%",
                min_value=0,
                max_value=100,
            ),
            "deal_probability": st.column_config.ProgressColumn(
                "Вероятность сделки",
                format="%d%%",
                min_value=0,
                max_value=100,
            ),
            "link": st.column_config.LinkColumn("Ссылка", display_text="Открыть объявление"),
        }
        
        if has_images:
            column_config["image_url"] = st.column_config.ImageColumn("Фото", width="small")
        
        st.dataframe(
            df,
            column_config=column_config,
            hide_index=True,
            use_container_width=True,
            height=600
        )
        
        # Кнопка сброса
        if st.button("🔄 Новый поиск", type="secondary"):
            st.session_state.search_started = False
            st.session_state.search_completed = False
            st.session_state.search_results = []
            st.rerun()
            
    else:
        # Стартовый экран
        st.info("👈 Выберите параметры автомобиля в меню слева и нажмите «Начать поиск»")
        
        # Примеры популярных запросов
        st.markdown("### 💡 Популярные запросы:")
        cols = st.columns(3)
        with cols[0]:
            st.markdown("**Кроссоверы до 3 млн**\n- Год: 2018+\n- Пробег: до 100к\n- Ликвидность: Высокая")
        with cols[1]:
            st.markdown("**Премиум седаны**\n- Марки: BMW, Mercedes\n- Без ДТП\n- 1 владелец")
        with cols[2]:
            st.markdown("**Электрокары**\n- Запас хода: 300+ км\n- Гарантия активна\n- Быстрая зарядка")

if __name__ == "__main__":
    main()
