# Dimas SaaS MVP — быстрый подбор автомобилей

Веб-сервис ищет объявления (основной источник — **Drom**), нормализует карточки и ранжирует по выгодности **относительно текущей выдачи**.

## Запуск

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env       # при необходимости прокси
python run_web.py
```

Откройте http://localhost:8000  
Проверка: `GET /health` → `{"status":"ok"}`

## Как пользоваться

1. Марка и модель (например Audi / Q3).
2. Источник по умолчанию — только **Drom**. Avito и Auto.ru опциональны и часто блокируются.
3. Фильтры года/цены уходят в URL Drom; детальные страницы качаются только для топ-N.
4. В выдаче: цена, год, пробег, топливо, ссылка «Открыть на площадке», оценка по выборке.

## Прокси

В `.env` (файл не в git):

```
PROXY_HOST=185.81.147.98
PROXY_HTTP_PORT=1206
PROXY_SOCKS_PORT=11206
PROXY_USER=...
PROXY_PASSWORD=...
PROXY_PROTOCOL=http
```

HTTP используется Drom/Avito (`requests`). Playwright (auto.ru) получает `server` + `username`/`password` отдельно. Для SOCKS5: `PROXY_PROTOCOL=socks5` (нужен пакет `pysocks`).

## Сохранённые поиски и CSV

- После выдачи: «Сохранить поиск» (до 3 на email) → `/searches`
- «Проверить дешевле» перезапускает парсинг и сравнивает с прошлой мин. ценой
- `/export/csv` — последняя выдача
- `/import/csv` — ручной фид объявлений

## Ограничения

- Парсинг площадок может нарушать их ToS; для продакшена нужен легальный фид.
- Avito часто отвечает 403. Auto.ru требует Playwright и может таймаутиться.
- Оценка — не рынок РФ, а сравнение лотов **этого** поиска.

Единственная точка входа MVP: `python run_web.py` (`app.web.main:app`).
