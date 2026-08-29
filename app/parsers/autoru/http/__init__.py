"""
Модуль HTTP клиента для парсера Auto.ru
"""

from .client import ProxyManager, UserAgentRotator

__all__ = ['ProxyManager', 'UserAgentRotator']
