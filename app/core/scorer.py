from datetime import datetime
from typing import Optional, Dict, Any
from loguru import logger


class CarScorer:
    """
    Улучшенная система скоринга автомобилей с учетом множества факторов
    """

    @staticmethod
    def calculate(car) -> float:
        """
        Расчет итоговой оценки автомобиля на основе всех доступных данных
        
        Факторы:
        - Возраст автомобиля
        - Пробег и его соответствие возрасту
        - Цена относительно рынка
        - Количество владельцев
        - ДТП в истории
        - Тип ПТС
        - Регион продажи
        """
        score = 50.0  # Базовая оценка
        
        current_year = datetime.now().year
        
        # === Фактор 1: Возраст автомобиля (макс +20/-20) ===
        year = car.year if hasattr(car, 'year') else None
        if year:
            age = current_year - year
            
            if age <= 3:
                score += 20  # Очень свежий
            elif age <= 5:
                score += 15  # Свежий
            elif age <= 7:
                score += 10  # Средний возраст
            elif age <= 10:
                score += 5   # Подержанный
            elif age <= 15:
                score -= 5   # Старый
            else:
                score -= 15  # Очень старый
        
        # === Фактор 2: Пробег (макс +25/-25) ===
        mileage = car.mileage if hasattr(car, 'mileage') else None
        if mileage and year:
            age = max(current_year - year, 1)
            yearly_mileage = mileage / age
            
            if yearly_mileage < 8000:
                score += 25  # Малый пробег
            elif yearly_mileage < 15000:
                score += 15  # Средний пробег
            elif yearly_mileage < 25000:
                score += 5   # Повышенный пробег
            elif yearly_mileage < 40000:
                score -= 10  # Большой пробег
            else:
                score -= 25  # Очень большой пробег
        
        # === Фактор 3: Цена (макс +20/-30) ===
        price = car.price if hasattr(car, 'price') else None
        market_price = car.market_price if hasattr(car, 'market_price') and car.market_price else None
        
        if price:
            if market_price and market_price > 0:
                # Сравнение с рыночной ценой
                deviation = (price - market_price) / market_price * 100
                
                if deviation < -20:
                    score += 20  # Очень выгодная цена (подозрительно?)
                elif deviation < -10:
                    score += 15  # Выгодная цена
                elif deviation < 0:
                    score += 10  # Чуть ниже рынка
                elif deviation < 5:
                    score += 5   # Рыночная цена
                elif deviation < 15:
                    score -= 5   # Выше рынка
                else:
                    score -= 20  # Завышенная цена
            else:
                # Эвристическая оценка без рыночной цены
                if year:
                    base_price = (current_year - year) * 250000 + 600000
                    
                    if price < base_price * 0.4:
                        score -= 30  # Подозрительно дешево
                    elif price < base_price * 0.7:
                        score += 15  # Хорошая цена
                    elif price < base_price * 1.2:
                        score += 5   # Нормальная цена
                    else:
                        score -= 15  # Дорого
        
        # === Фактор 4: Количество владельцев (макс +15/-20) ===
        owners = car.owners if hasattr(car, 'owners') else None
        if owners is not None:
            if owners == 1:
                score += 15  # Один владелец - отлично
            elif owners == 2:
                score += 10  # Два владельца - нормально
            elif owners == 3:
                score += 0   # Три владельца - средне
            elif owners == 4:
                score -= 10  # Четыре владельца - много
            else:
                score -= 20  # Пять+ владельцев - очень много
        
        # === Фактор 5: ДТП (макс +10/-30) ===
        accidents = car.accidents if hasattr(car, 'accidents') else None
        if accidents is not None:
            if accidents == 0:
                score += 10  # Без ДТП - отлично
            elif accidents == 1:
                score -= 5   # Одно ДТП - допустимо
            elif accidents == 2:
                score -= 15  # Два ДТП - плохо
            else:
                score -= 30  # Три+ ДТП - очень плохо
        
        # === Фактор 6: Тип ПТС (макс +10/-10) ===
        pts = car.pts if hasattr(car, 'pts') else None
        if pts:
            pts_lower = pts.lower()
            if 'оригинал' in pts_lower or 'original' in pts_lower:
                score += 10  # Оригинальный ПТС
            elif 'дубликат' in pts_lower or 'duplicate' in pts_lower:
                score -= 5   # Дубликат ПТС
            elif 'электронный' in pts_lower or 'electronic' in pts_lower:
                score += 5   # Электронный ПТС (современно)
        
        # === Фактор 7: Трансмиссия (макс +5/-5) ===
        transmission = car.transmission if hasattr(car, 'transmission') else None
        if transmission:
            trans_lower = transmission.lower()
            if 'автомат' in trans_lower or 'at' in trans_lower or 'amt' in trans_lower:
                score += 5   # Автомат более популярен
            elif 'механика' in trans_lower or 'mt' in trans_lower:
                score -= 2   # Механика менее популярна
            elif 'робот' in trans_lower or 'amt' in trans_lower:
                score += 0   # Робот нейтрально
            elif 'вариатор' in trans_lower or 'cvt' in trans_lower:
                score += 3   # Вариатор хорошо
        
        # === Фактор 8: Привод (макс +5/-5) ===
        drive = car.drive if hasattr(car, 'drive') else None
        if drive:
            drive_lower = drive.lower()
            if 'полный' in drive_lower or '4wd' in drive_lower or 'awd' in drive_lower:
                score += 5   # Полный привод ценится
            elif 'задний' in drive_lower or 'rwd' in drive_lower:
                score += 2   # Задний привод нейтрально-положительно
            elif 'передний' in drive_lower or 'fwd' in drive_lower:
                score += 0   # Передний привод стандарт
        
        # === Фактор 9: Ликвидность марки/модели (макс +10) ===
        # Расширенная система оценки ликвидности для ЛЮБОЙ марки
        brand = car.brand if hasattr(car, 'brand') else None
        
        # Высоколиквидные марки с весами - расширенный список
        high_liquidity_brands = {
            # Японские
            'toyota': 10, 'lexus': 10, 'honda': 9, 'mazda': 8,
            'nissan': 6, 'infiniti': 4, 'acura': 3, 'mitsubishi': 5,
            'subaru': 6, 'suzuki': 5, 'isuzu': 3,
            
            # Корейские
            'kia': 8, 'hyundai': 8, 'genesis': 6,
            
            # Немецкие
            'bmw': 7, 'mercedes': 7, 'audi': 6,
            'volkswagen': 7, 'skoda': 7, 'porsche': 5,
            'opel': 4,
            
            # Китайские
            'geely': 6, 'chery': 5, 'haval': 6, 'exeed': 5,
            'tank': 5, 'omoda': 4, 'jaecoo': 4, 'lixiang': 4,
            'zeekr': 4, 'voyah': 4, 'hongqi': 3, 'byd': 4,
            'changan': 5, 'jac': 3, 'faaw': 3, 'dongfeng': 3,
            'gac': 4, 'greatwall': 4, 'wey': 4, 'polestar': 3,
            
            # Европейские
            'volvo': 6, 'land rover': 5, 'range rover': 6,
            'jaguar': 4, 'mini': 5, 'fiat': 3, 'alfa romeo': 3,
            'peugeot': 4, 'citroen': 4, 'renault': 5,
            'seat': 4, 'ford': 5, 'chevrolet': 4, 'cadillac': 4,
            
            # Российские
            'lada': 7, 'uaz': 4, 'gaz': 3,
            
            # Американские
            'tesla': 7, 'jeep': 4, 'dodge': 3, 'chrysler': 3,
            'lincoln': 3, 'buick': 3,
            
            # Другие
            'daewoo': 4, 'ssangyong': 3, 'ravon': 3,
            'datsun': 3, 'smart': 3, 'bentley': 2,
            'rolls-royce': 2, 'maserati': 2, 'ferrari': 2,
            'lamborghini': 2, 'mclaren': 2, 'aston martin': 2
        }
        
        if brand:
            brand_lower = brand.lower()
            if brand_lower in high_liquidity_brands:
                score += high_liquidity_brands[brand_lower]
            else:
                # Для ЛЮБОЙ другой марки - базовые 2 балла
                score += 2
                # Бонус за длину названия
                if len(brand_lower) > 4:
                    score += 1
        
        # Ограничиваем оценку диапазоном [0, 100]
        final_score = max(0, min(100, score))
        
        logger.debug(f"Car scoring: {brand} {getattr(car, 'model', '')} {year} - Score: {final_score:.1f}")
        
        return final_score
    
    @staticmethod
    def get_score_description(score: float) -> str:
        """Возвращает текстовое описание оценки"""
        if score >= 85:
            return "Отличная сделка"
        elif score >= 70:
            return "Хорошая сделка"
        elif score >= 55:
            return "Средняя сделка"
        elif score >= 40:
            return "Подозрительная сделка"
        else:
            return "Плохая сделка"
    
    @staticmethod
    def calculate_probability_good_deal(score: float) -> float:
        """
        Конвертирует оценку в вероятность выгодной сделки (0.0 - 1.0)
        """
        # S-образная кривая для более плавного перехода
        normalized = score / 100.0
        probability = 1 / (1 + 2.71828 ** (-5 * (normalized - 0.5)))
        return round(probability, 3)