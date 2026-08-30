from statistics import median
import math


class MarketAnalyzer:

    @staticmethod
    def calculate_market_price(cars, target):

        scored = []

        for car in cars:

            # защита
            if not car.get("price"):
                continue

            if (
                car.get("brand") != target.brand
                or car.get("model") != target.model
            ):
                continue

            score = 0

            # -------------------------
            # YEAR
            # -------------------------
            year_diff = abs(
                car.get("year", 0) - target.year
            )

            if year_diff <= 1:
                score += 35

            elif year_diff <= 2:
                score += 20

            elif year_diff <= 3:
                score += 10

            # -------------------------
            # MILEAGE
            # -------------------------
            mileage = car.get("mileage") or 0

            mileage_diff = abs(
                mileage - target.mileage
            )

            if mileage_diff <= 30000:
                score += 25

            elif mileage_diff <= 60000:
                score += 15

            elif mileage_diff <= 100000:
                score += 7

            # -------------------------
            # ENGINE
            # -------------------------
            engine_diff = abs(
                (car.get("engine_volume") or 0)
                - (target.engine_volume or 0)
            )

            if engine_diff <= 0.3:
                score += 15

            elif engine_diff <= 0.7:
                score += 8

            # -------------------------
            # REGION BONUS
            # -------------------------
            if (
                car.get("region")
                == target.region
            ):
                score += 10

            # -------------------------
            # OWNERS
            # -------------------------
            owners = car.get("owners") or 0

            if owners <= 2:
                score += 10

            elif owners <= 4:
                score += 5

            scored.append({
                "price": car["price"],
                "score": score
            })

        # нет похожих
        if not scored:
            return target.price

        # сортируем по похожести
        scored.sort(
            key=lambda x: x["score"],
            reverse=True
        )

        # берем TOP похожих
        top_similar = scored[:15]

        prices = [
            x["price"]
            for x in top_similar
        ]

        return median(prices)

    @staticmethod
    def calculate_market_deviation(
        real_price,
        market_price
    ):

        if market_price <= 0:
            return 0

        return round(
            (
                market_price - real_price
            ) / market_price,
            4
        )

    @staticmethod
    def calculate_liquidity_score(car):
        """
        Расчет ликвидности автомобиля на основе множества факторов
        
        Факторы:
        - Возраст автомобиля
        - Пробег
        - Количество владельцев
        - ДТП
        - Регион продажи
        - Ликвидность марки (по списку популярных брендов)
        - Ликвидность модели
        """
        score = 0.5  # Базовая ликвидность
        
        current_year = 2025  # Актуальный год для расчета
        
        # === Фактор 1: Возраст автомобиля (макс +0.20) ===
        if car.year >= 2023:
            score += 0.20  # Очень свежий (1-2 года)
        elif car.year >= 2020:
            score += 0.15  # Свежий (3-5 лет)
        elif car.year >= 2018:
            score += 0.10  # Средний возраст (6-7 лет)
        elif car.year >= 2015:
            score += 0.05  # Подержанный (8-10 лет)
        elif car.year >= 2010:
            score += 0.0   # Старый (11-15 лет)
        else:
            score -= 0.10  # Очень старый (>15 лет)
        
        # === Фактор 2: Пробег (макс +0.20) ===
        mileage = car.mileage or 0
        year = car.year or 2025
        age = max(current_year - year, 1)
        yearly_mileage = mileage / age
        
        if yearly_mileage < 8000:
            score += 0.20  # Малый пробег (<8к км/год)
        elif yearly_mileage < 15000:
            score += 0.15  # Средний пробег (8-15к км/год)
        elif yearly_mileage < 25000:
            score += 0.08  # Повышенный пробег (15-25к км/год)
        elif yearly_mileage < 40000:
            score += 0.0   # Большой пробег (25-40к км/год)
        else:
            score -= 0.10  # Очень большой пробег (>40к км/год)
        
        # Абсолютный пробег тоже важен
        if mileage > 250000:
            score -= 0.10  # Критический пробег
        elif mileage > 180000:
            score -= 0.05
        
        # === Фактор 3: Количество владельцев (макс +0.15) ===
        owners = car.owners or 0
        if owners == 1:
            score += 0.15  # Один владелец - отлично
        elif owners == 2:
            score += 0.10  # Два владельца - нормально
        elif owners == 3:
            score += 0.05  # Три владельца - средне
        elif owners <= 5:
            score -= 0.05  # Много владельцев
        else:
            score -= 0.15  # Очень много владельцев
        
        # === Фактор 4: ДТП (макс +0.15) ===
        accidents = car.accidents or 0
        if accidents == 0:
            score += 0.15  # Без ДТП - отлично
        elif accidents == 1:
            score += 0.05  # Одно ДТП - допустимо
        elif accidents == 2:
            score -= 0.05  # Два ДТП - плохо
        else:
            score -= 0.15  # Много ДТП
        
        # === Фактор 5: Регион продажи (макс +0.15) ===
        high_liquidity_regions = [
            "moscow", "spb", "ekaterinburg", "novosibirsk",
            "казань", "нижний новгород", "челябинск", "самара",
            "омск", "ростов-на-дону", "уфа", "краснодар"
        ]
        region_lower = (car.region or "").lower()
        if any(r in region_lower for r in high_liquidity_regions):
            score += 0.15  # Крупный город с высоким спросом
        elif car.region and len(car.region) > 2:
            score += 0.05  # Региональный центр
        
        # === Фактор 6: Ликвидность марки (макс +0.20) ===
        # Динамическая система оценки ликвидности для ЛЮБОЙ марки
        brand = (car.brand or "").lower()
        
        # Высоколиквидные марки (всегда в спросе) - расширенный список
        high_liquidity_brands = {
            # Японские премиум и масс-маркет
            'toyota': 0.20, 'lexus': 0.20, 'honda': 0.18, 'mazda': 0.16,
            'nissan': 0.12, 'infiniti': 0.08, 'acura': 0.07, 'mitsubishi': 0.11,
            'subaru': 0.13, 'suzuki': 0.10, 'isuzu': 0.06,
            
            # Корейские
            'kia': 0.17, 'hyundai': 0.16, 'genesis': 0.12,
            
            # Немецкие премиум и масс-маркет
            'bmw': 0.14, 'mercedes': 0.14, 'audi': 0.13,
            'volkswagen': 0.15, 'skoda': 0.15, 'porsche': 0.11,
            'opel': 0.09,
            
            # Китайские (набирают популярность)
            'geely': 0.12, 'chery': 0.11, 'haval': 0.12, 'exeed': 0.10,
            'tank': 0.10, 'omoda': 0.09, 'jaecoo': 0.09, 'lixiang': 0.08,
            'zeekr': 0.08, 'voyah': 0.08, 'hongqi': 0.07, 'byd': 0.09,
            'changan': 0.10, 'jac': 0.07, 'faaw': 0.06, 'dongfeng': 0.07,
            'gac': 0.08, 'greatwall': 0.09, 'wey': 0.08, 'polestar': 0.07,
            
            # Европейские
            'volvo': 0.13, 'land rover': 0.11, 'range rover': 0.12,
            'jaguar': 0.09, 'mini': 0.10, 'fiat': 0.07, 'alfa romeo': 0.06,
            'peugeot': 0.09, 'citroen': 0.08, 'renault': 0.10,
            'seat': 0.08, 'ford': 0.10, 'chevrolet': 0.09, 'cadillac': 0.08,
            
            # Российские
            'lada': 0.15, 'ua': 0.08, 'gaz': 0.06,
            
            # Американские
            'ford': 0.10, 'chevrolet': 0.09, 'cadillac': 0.08,
            'jeep': 0.08, 'dodge': 0.07, 'chrysler': 0.06,
            'tesla': 0.14, 'lincoln': 0.07, 'buick': 0.06,
            
            # Другие
            'daewoo': 0.08, 'ssangyong': 0.07, 'ravon': 0.06,
            'datsun': 0.07, 'smart': 0.06, 'bentley': 0.05,
            'rolls-royce': 0.04, 'maserati': 0.05, 'ferrari': 0.04,
            'lamborghini': 0.04, 'mclaren': 0.04, 'aston martin': 0.04
        }
        
        if brand in high_liquidity_brands:
            score += high_liquidity_brands[brand]
        else:
            # Для ЛЮБОЙ другой марки - базовая ликвидность 0.05
            # Это позволяет работать с неизвестными/редкими марками
            score += 0.05
            
            # Бонус за длину названия (косвенный признак известности)
            if len(brand) > 4:
                score += 0.02
        
        # === Фактор 7: Тип кузова (макс +0.10) ===
        body_type = (car.body_type or "").lower()
        if 'суф' in body_type or 'внедорожник' in body_type or 'suv' in body_type:
            score += 0.10  # Внедорожники и кроссоверы очень ликвидны
        elif 'седан' in body_type or 'sedan' in body_type:
            score += 0.08  # Седаны популярны
        elif 'лифтбек' in body_type or 'хэтчбек' in body_type:
            score += 0.06  # Хэтчбеки средне ликвидны
        elif 'универсал' in body_type or 'wagon' in body_type:
            score += 0.05  # Универсалы нишевые
        
        # === Фактор 8: Трансмиссия (макс +0.05) ===
        transmission = (car.transmission or "").lower()
        if 'автомат' in transmission or 'at' in transmission or 'amt' in transmission:
            score += 0.05  # Автомат более ликвиден
        elif 'вариатор' in transmission or 'cvt' in transmission:
            score += 0.04
        elif 'робот' in transmission or 'dct' in transmission:
            score += 0.02
        elif 'механика' in transmission or 'mt' in transmission:
            score += 0.0   # Механика менее ликвидна
        
        # Нормализация scores в диапазон [0.0, 1.0]
        return max(0.0, min(1.0, round(score, 4)))

    @staticmethod
    def calculate_confidence(car):

        fields = [
            car.year,
            car.price,
            car.mileage,
            car.engine_volume,
            car.owners,
            car.transmission,
            car.drive,
            car.body_type
        ]

        filled = sum(
            1 for x in fields
            if x not in [None, "", 0]
        )

        return round(
            filled / len(fields),
            4
        )

    @staticmethod
    def sigmoid(x):

        return 1 / (
            1 + math.exp(-x)
        )

    @staticmethod
    def calculate_final_probability(car, search_config=None):
        """
        Расчет вероятности выгодной сделки с учетом конфигурации поиска пользователя
        
        Если передана search_config, учитываем соответствие параметров поиска
        """
        z = 0

        # рынок - вычисляем market_deviation на лету
        market_deviation = 0
        if car.market_price > 0:
            market_deviation = (car.market_price - car.price) / car.market_price
        z += market_deviation * 3.5

        # ликвидность
        z += car.liquidity_score * 2.0

        # confidence
        z += car.data_confidence * 1.5

        # market score
        z += car.market_score * 2.0
        
        # === Бонус за соответствие параметрам поиска пользователя ===
        if search_config:
            match_bonus = 0
            
            # Год выпуска в диапазоне
            if search_config.year_min <= car.year <= search_config.year_max:
                match_bonus += 0.3
            else:
                # Штраф за выход за пределы диапазона
                year_dist = max(
                    abs(car.year - search_config.year_min),
                    abs(car.year - search_config.year_max)
                )
                z -= min(year_dist / 10, 0.5)  # Макс штраф 0.5
            
            # Пробег в диапазоне
            mileage = car.mileage or 0
            if search_config.mileage_min <= mileage <= search_config.mileage_max:
                match_bonus += 0.3
            else:
                mileage_dist = max(
                    abs(mileage - search_config.mileage_min),
                    abs(mileage - search_config.mileage_max)
                )
                z -= min(mileage_dist / 50000, 0.5)
            
            # Количество владельцев в диапазоне
            owners = car.owners or 0
            if search_config.owners_min <= owners <= search_config.owners_max:
                match_bonus += 0.2
            else:
                z -= 0.3  # Штраф за несоответствие
            
            # Трансмиссия (если указана в поиске)
            if search_config.transmission:
                car_trans = (car.transmission or "").lower()
                if search_config.transmission.lower() in car_trans:
                    match_bonus += 0.15
                else:
                    z -= 0.2  # Штраф за несоответствие
            
            # Тип топлива (если указан в поиске)
            if search_config.fuel:
                car_fuel = (car.fuel or "").lower()
                if search_config.fuel.lower() in car_fuel:
                    match_bonus += 0.1
                else:
                    z -= 0.15
            
            # Привод (если указан в поиске)
            if search_config.drive:
                car_drive = (car.drive or "").lower()
                if search_config.drive.lower() in car_drive:
                    match_bonus += 0.1
                else:
                    z -= 0.15
            
            # Регион (если указан в поиске)
            if search_config.region:
                car_region = (car.region or "").lower()
                if search_config.region.lower() in car_region:
                    match_bonus += 0.15
                else:
                    z -= 0.2
            
            # Добавляем бонус за совпадения
            z += match_bonus

        return round(
            MarketAnalyzer.sigmoid(z),
            4
        )