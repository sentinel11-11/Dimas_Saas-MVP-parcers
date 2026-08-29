"""
Ядро парсера Auto.ru - основные движки и утилиты
"""

import asyncio
import random
from typing import List, Dict, Any, Optional
from loguru import logger


class DelayManager:
    """Менеджер умных задержек между запросами"""
    
    def __init__(
        self, 
        base_delay: float = 2.0, 
        randomize: bool = True,
        min_delay: float = 1.0,
        max_delay: float = 5.0
    ):
        self.base_delay = base_delay
        self.randomize = randomize
        self.min_delay = min_delay
        self.max_delay = max_delay
        self._request_count = 0
    
    def calculate_delay(self) -> float:
        """
        Расчет задержки с учетом количества запросов
        
        Returns:
            Задержка в секундах
        """
        if not self.randomize:
            return self.base_delay
        
        # Увеличиваем задержку после каждых 10 запросов
        multiplier = 1 + (self._request_count // 10) * 0.2
        
        # Случайная задержка в диапазоне
        delay = random.uniform(self.min_delay, self.max_delay) * multiplier
        
        # Ограничение максимального значения
        delay = min(delay, self.max_delay * 2)
        
        logger.debug(f"Calculated delay: {delay:.2f}s (request #{self._request_count})")
        return delay
    
    def increment_request(self):
        """Увеличить счетчик запросов"""
        self._request_count += 1
    
    def reset(self):
        """Сбросить счетчик запросов"""
        self._request_count = 0
        logger.debug("Delay manager reset")
    
    async def wait(self):
        """Асинхронное ожидание рассчитанной задержки"""
        delay = self.calculate_delay()
        await asyncio.sleep(delay)
        self.increment_request()


class SessionManager:
    """Менеджер сессий браузера"""
    
    def __init__(self, max_requests_per_session: int = 50):
        self.max_requests = max_requests_per_session
        self._request_count = 0
    
    def should_rotate(self) -> bool:
        """Проверить, нужно ли ротировать сессию"""
        return self._request_count >= self.max_requests
    
    def increment_request(self):
        """Увеличить счетчик запросов"""
        self._request_count += 1
    
    def reset(self):
        """Сбросить счетчик запросов"""
        self._request_count = 0
        logger.info("Session rotated - request count reset")
    
    @property
    def request_count(self) -> int:
        """Получить текущее количество запросов"""
        return self._request_count
    
    @property
    def remaining_requests(self) -> int:
        """Получить оставшееся количество запросов до ротации"""
        return max(0, self.max_requests - self._request_count)


class DataCleaner:
    """Утилиты для очистки данных"""
    
    @staticmethod
    def clean_price(price_str: str) -> int:
        """
        Очистка строки цены до целого числа
        
        Args:
            price_str: Строка с ценой (например, "1 234 567 ₽")
            
        Returns:
            Цена как целое число
        """
        if not price_str:
            return 0
        
        try:
            # Удаление всех нецифровых символов кроме минуса
            cleaned = ''.join(c for c in str(price_str) if c.isdigit() or c == '-')
            return int(cleaned) if cleaned else 0
        except (ValueError, TypeError):
            return 0
    
    @staticmethod
    def clean_number(number_str: str) -> int:
        """
        Очистка строки числа до целого
        
        Args:
            number_str: Строка с числом
            
        Returns:
            Число как int
        """
        if not number_str:
            return 0
        
        try:
            cleaned = ''.join(c for c in str(number_str) if c.isdigit() or c == '-')
            return int(cleaned) if cleaned else 0
        except (ValueError, TypeError):
            return 0
    
    @staticmethod
    def clean_volume(volume_str: str) -> float:
        """
        Очистка строки объема двигателя
        
        Args:
            volume_str: Строка с объемом (например, "2.0 л")
            
        Returns:
            Объем как float
        """
        if not volume_str:
            return 0.0
        
        try:
            # Извлечение первого числа (целого или дробного)
            import re
            match = re.search(r'[\d]+[.,]?[\d]*', str(volume_str))
            if match:
                return float(match.group().replace(',', '.'))
            return 0.0
        except (ValueError, TypeError):
            return 0.0
    
    @staticmethod
    def clean_horsepower(hp_str: str) -> int:
        """
        Очистка строки мощности двигателя
        
        Args:
            hp_str: Строка с мощностью (например, "150 л.с.")
            
        Returns:
            Мощность как int
        """
        return DataCleaner.clean_number(hp_str)
    
    @staticmethod
    def normalize_text(text: Optional[str]) -> str:
        """
        Нормализация текста
        
        Args:
            text: Исходный текст
            
        Returns:
            Нормализованный текст
        """
        if not text:
            return ""
        
        # Удаление лишних пробелов и переносов строк
        normalized = ' '.join(str(text).split())
        return normalized.strip()
