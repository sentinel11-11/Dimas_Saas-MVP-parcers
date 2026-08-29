# 🚗 Car Parser MVP - Веб-приложение

Автоматизированная система парсинга и анализа автомобильных объявлений с веб-интерфейсом.

## 🎯 Возможности

- **Три источника**: Drom, Auto.ru, Avito
- **Умный скоринг**: Расчет вероятности выгодной сделки
- **Анализ рынка**: Сравнение с средними ценами
- **Веб-интерфейс**: Красивый и удобный интерфейс на Bootstrap 5
- **Локальный запуск**: Для тестирования
- **Production-ready**: Для развертывания на сервере

## 📋 Требования

- Python 3.8+
- Playwright (для Auto.ru)
- FastAPI + Uvicorn

## 🚀 Установка

```bash
# Установка зависимостей
pip install -r requirements.txt

# Установка браузеров для Playwright
playwright install chromium
```

## 🖥️ Локальный запуск

### Вариант 1: Через скрипт запуска
```bash
python run_web.py
```

### Вариант 2: Прямой запуск uvicorn
```bash
uvicorn app.web.main:app --reload --host 0.0.0.0 --port 8000
```

После запуска откройте в браузере: **http://localhost:8000**

## 🌐 Production запуск

### С Gunicorn (рекомендуется)
```bash
gunicorn app.web.main:app \
    -w 4 \
    -k uvicorn.workers.UvicornWorker \
    --host 0.0.0.0 \
    --port 8000 \
    --timeout 120
```

### С Docker (пример)
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium

COPY . .

EXPOSE 8000

CMD ["gunicorn", "app.web.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--host", "0.0.0.0", "--port", "8000"]
```

## 📁 Структура проекта

```
/workspace/
├── app/
│   ├── web/              # Веб-приложение FastAPI
│   │   └── main.py       # Основной файл приложения
│   ├── parsers/          # Парсеры
│   │   ├── drom/         # Парсер Drom
│   │   ├── avito/        # Парсер Avito
│   │   └── autoru/       # Парсер Auto.ru (Playwright)
│   ├── core/             # Бизнес-логика
│   │   ├── market.py     # Движок анализа рынка
│   │   ├── market_analyzer.py  # Аналитика
│   │   └── normalizer.py # Нормализация данных
│   ├── database/         # Работа с БД
│   │   ├── db.py         # Функции БД
│   │   └── models.py     # SQLAlchemy модели
│   └── models/           # Pydantic модели
├── templates/            # HTML шаблоны
│   ├── index.html        # Главная страница
│   └── results.html      # Страница результатов
├── static/               # Статические файлы
├── data/                 # Данные (БД, кэш)
├── logs/                 # Логи
├── run_web.py            # Скрипт запуска
├── main.py               # Консольная версия
└── requirements.txt      # Зависимости
```

## 🔧 Конфигурация

Парсеры можно настроить через параметры:

```python
# Auto.ru
AutoRuParser(headless=True, use_proxy=False, limit=10)

# Avito
AvitoParser().search({"brand": "bmw", "model": "x5", "limit": 10})

# Drom
DromParser().search({"brand": "bmw", "model": "x5"})
```

## 🎨 Веб-интерфейс

### Главная страница
- Выбор марки и модели
- Выбор источников поиска (Drom, Avito, Auto.ru)
- Настройка количества результатов
- Быстрый выбор популярных марок

### Страница результатов
- Карточки автомобилей с детальной информацией
- Цветовая индикация вероятности выгодной сделки:
  - 🟢 Зеленый (≥80%): Отличная сделка
  - 🔵 Синий (60-79%): Хорошая сделка
  - 🟡 Желтый (40-59%): Средняя сделка
  - 🔴 Красный (<40%): Низкая вероятность
- Рыночная цена и отклонение
- Прямые ссылки на объявления
- Информация о ликвидности

## 📊 API Endpoints

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/` | Главная страница с формой поиска |
| POST | `/search` | Обработка поиска автомобилей |
| GET | `/results/{brand}/{model}` | Просмотр результатов |

## ⚠️ Важные замечания

1. **Avito блокировки**: Avito активно борется с парсингом. При частых запросах может возвращать HTTP 429. Решение:
   - Увеличены задержки между запросами
   - Ротация User-Agent
   - Рекомендуется использовать прокси

2. **Auto.ru**: Использует JavaScript, поэтому требуется Playwright. Первый запуск может быть медленным (загрузка браузера).

3. **Drom**: Наиболее стабильный источник, работает без дополнительных зависимостей.

## 🐛 Решение проблем

### Ошибка "Browser executable missing"
```bash
playwright install chromium
```

### Ошибка импорта Session из SQLAlchemy
Убедитесь, что используется правильный импорт:
```python
from sqlalchemy.orm import Session
```

### Avito возвращает 429
- Увеличьте задержку в `app/parsers/avito/http/client.py`
- Используйте прокси
- Ограничьте количество запросов

## 📝 Лицензия

MIT License

## 👥 Контакты

Для вопросов и предложений создавайте Issues в репозитории.
