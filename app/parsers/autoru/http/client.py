"""
HTTP клиент для парсера Auto.ru с поддержкой прокси и ротации
"""

import random
from typing import List, Optional
from loguru import logger


class ProxyManager:
    """Менеджер прокси для ротации"""
    
    def __init__(self, proxy_list: Optional[List[str]] = None):
        self.proxy_list = proxy_list or []
        self._current_index = 0
    
    def get_next_proxy(self) -> Optional[str]:
        """Получить следующий прокси из списка"""
        if not self.proxy_list:
            return None
        
        # Случайный выбор прокси
        proxy = random.choice(self.proxy_list)
        logger.debug(f"Selected proxy: {proxy}")
        return proxy
    
    def get_all_proxies(self) -> List[str]:
        """Получить весь список прокси"""
        return self.proxy_list.copy()
    
    def add_proxy(self, proxy: str):
        """Добавить прокси в список"""
        if proxy not in self.proxy_list:
            self.proxy_list.append(proxy)
            logger.info(f"Added proxy: {proxy}")
    
    def remove_proxy(self, proxy: str):
        """Удалить прокси из списка"""
        if proxy in self.proxy_list:
            self.proxy_list.remove(proxy)
            logger.warning(f"Removed proxy: {proxy}")
    
    def is_empty(self) -> bool:
        """Проверить, пуст ли список прокси"""
        return len(self.proxy_list) == 0


class UserAgentRotator:
    """Ротатор User-Agent строк"""
    
    def __init__(self, user_agents: Optional[List[str]] = None):
        self.user_agents = user_agents or []
    
    def get_user_agent(self) -> Optional[str]:
        """Получить случайный User-Agent"""
        if not self.user_agents:
            return None
        
        ua = random.choice(self.user_agents)
        logger.debug(f"Selected User-Agent: {ua[:50]}...")
        return ua
    
    def get_all_user_agents(self) -> List[str]:
        """Получить все User-Agent строки"""
        return self.user_agents.copy()
