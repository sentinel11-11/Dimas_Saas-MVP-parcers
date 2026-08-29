# Руководство по деплою Car Parser MVP

## Требования для сервера
- Ubuntu 20.04+ или аналогичный Linux
- Python 3.10+
- 2GB+ RAM
- 10GB+ свободного места

## Шаг 1: Установка зависимостей на сервере
```bash
sudo apt update && sudo apt install -y python3-pip python3-venv chromium-driver
pip3 install playwright
playwright install chromium
```

## Шаг 2: Клонирование проекта
```bash
git clone <your-repo-url>
cd CarParserMVP
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Шаг 3: Настройка .env
Скопируйте `.env.example` в `.env` и заполните:
- Прокси для Avito и Auto.ru
- Параметры поиска (BRAND, MODEL и т.д.)

## Шаг 4: Запуск приложения
### Вариант A: Streamlit (рекомендуется для демонстрации)
```bash
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

### Вариант B: Gunicorn + Nginx (production)
```bash
gunicorn -w 4 -k uvicorn.workers.UvicornWorker run_web:app -b 0.0.0.0:8000
```

## Шаг 5: Настройка Nginx (опционально)
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8501;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Локальный запуск (Windows/Mac/Linux)
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
streamlit run app.py --server.headless true
```

## Проверка работоспособности
1. Откройте http://localhost:8501 (локально) или http://your-server-ip:8501
2. Выберите марку, модель и параметры поиска
3. Нажмите "Начать поиск"
4. Проверьте результаты с колонками "Ликвидность" и "Вероятность выгодной сделки"

## Troubleshooting
- Ошибка прокси: проверьте формат в .env (user:pass@ip:port)
- Блокировка парсинга: увеличьте задержки в конфиге парсеров
- Ошибка Playwright: `playwright install chromium --force`
