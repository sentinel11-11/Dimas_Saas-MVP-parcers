#!/usr/bin/env python3
"""
Запуск веб-приложения Car Parser MVP
Для локального тестирования: python run_web.py
Для production: gunicorn app.web.main:app -w 4 -k uvicorn.workers.UvicornWorker --host 0.0.0.0 --port 8000
"""

import sys
import os

# Добавляем корневую директорию в path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.web.main import app
import uvicorn

if __name__ == "__main__":
    print("=" * 60)
    print("🚗 Car Parser MVP - Веб-интерфейс")
    print("=" * 60)
    print("📍 Откройте в браузере: http://localhost:8000")
    print("🛑 Для остановки нажмите Ctrl+C")
    print("=" * 60)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=False,  # В production установить False
        log_level="info"
    )
