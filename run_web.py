#!/usr/bin/env python3
"""
Запуск веб-приложения Car Parser MVP
Для локального тестирования: python run_web.py
Для production: gunicorn app.web.main:app -w 4 -k uvicorn.workers.UvicornWorker --host 0.0.0.0 --port 8000
"""

import sys
import os

import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from app.core.proxy import ProxySettings
from app.web.main import app
import uvicorn

if __name__ == "__main__":
    print("=" * 60)
    print("DIMAS — быстрый подбор авто")
    print("=" * 60)
    print("Браузер: http://localhost:8000")
    print(ProxySettings.status_line())
    print("Стоп: Ctrl+C")
    print("=" * 60)
    if not ProxySettings.enabled():
        print("Нет .env — Avito/auto.ru пойдут с вашего IP и почти всегда 403.")
        print("Скопируйте .env.example в .env и пропишите прокси.")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False, log_level="info")
