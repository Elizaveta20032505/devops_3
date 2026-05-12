# Лабораторная работа №2. Взаимодействие с источниками данных

Развитие сервиса из лабораторной работы №1: модель классификации опухоли (Breast
Cancer Wisconsin) дополнена взаимодействием с базой данных PostgreSQL.

## Что добавлено по сравнению с лабораторной №1

| Область | Изменение |
|---|---|
| Источник данных | Добавлен сервис PostgreSQL в `docker-compose.yml` |
| Запись результатов | Каждое предсказание API сохраняется в таблицу `predictions` |
| Чтение из БД | Эндпоинт `GET /predictions` возвращает последние записи |
| Наполнение БД | Скрипт `scripts/seed_db.py` загружает обучающий датасет в `training_data` |
| Аутентификация | Креды БД передаются только через переменные окружения; в коде их нет |
| CD pipeline | Поднимает связку `api + db`, выполняет функциональные сценарии, очищает окружение |

## Состав проекта

| Файл | Назначение |
|---|---|
| `src/api.py` | FastAPI: эндпоинты `/health`, `/predict`, `/predictions` |
| `src/db.py` | Подключение к PostgreSQL, создание схемы, запись/чтение предсказаний |
| `src/inference.py`, `src/train.py`, `src/prepare_data.py` | Обучение и инференс модели (без изменений) |
| `scripts/seed_db.py` | Загрузка `data/raw/data.csv` в таблицу `training_data` |
| `scripts/run_scenarios.py` | Прогон сценариев из `scenario.json` |
| `scenario.json` | Описание шагов функционального тестирования |
| `docker-compose.yml` | Сервисы `db` (PostgreSQL 16) и `api` |
| `Dockerfile` | Сборка образа сервиса `api` |
| `Jenkinsfile` | CI pipeline: сборка и публикация образа в Docker Hub |
| `CD/Jenkinsfile` | CD pipeline: запуск контейнеров и функциональное тестирование |
| `config.ini` | Параметры путей, обучения и имена таблиц БД |
| `.env.example` | Шаблон переменных окружения (реальный `.env` в `.gitignore`) |

## Архитектура

```
            ┌─────────────────────────┐
   client ──► FastAPI (контейнер api) │
            │  /predict, /predictions │
            └────────────┬────────────┘
                         │ psycopg2
                         ▼
                ┌────────────────────┐
                │ PostgreSQL (db)    │
                │  predictions       │
                │  training_data     │
                └────────────────────┘
```

## Переменные окружения

| Переменная | Назначение |
|---|---|
| `POSTGRES_HOST` | Хост БД (внутри compose — `db`) |
| `POSTGRES_PORT` | Порт БД (по умолчанию 5432) |
| `POSTGRES_DB` | Имя базы данных |
| `POSTGRES_USER` | Пользователь БД |
| `POSTGRES_PASSWORD` | Пароль пользователя |

Значения подставляются:

- **Локально** — из файла `.env` (создаётся вручную по `.env.example`).
- **В Jenkins** — из Jenkins Credentials `pg-creds` (Username with password),
  записываются во временный `.env` на стадии `compose_up` и удаляются по
  завершении пайплайна.


## CI / CD

### CI (`Jenkinsfile`)
1. Checkout репозитория.
2. `docker build` образа сервиса.
3. `docker login` через Credential `dockerhub-creds`.
4. `docker push` образа c тегами `build-<N>` и `latest`.
5. Запуск CD job `devops2-model-cd`.

### CD (`CD/Jenkinsfile`)
1. Pull образа с Docker Hub.
2. Создание `.env` из Credential `pg-creds`.
3. `docker compose up -d` (сервисы `db` и `api`).
4. Попытка наполнения БД скриптом `scripts/seed_db.py`.
5. Прогон сценариев `scripts/run_scenarios.py` по `scenario.json`.
6. Очистка: `docker compose down -v`, удаление `.env`, `docker logout`.
   Логи compose сохраняются как артефакт.

## Сценарии функционального тестирования

`scenario.json` описывает четыре шага:

1. `GET /health` — проверка готовности сервиса.
2. `GET /openapi.json` — доступность спецификации.
3. `POST /predict` — предсказание на нулевых признаках.
4. `GET /predictions` — выборка последних записей из БД.

## Безопасность

В исходном коде отсутствуют логины, пароли, адреса и порты сервера БД, а также
токены доступа. Все секреты управляются Jenkins Credentials и передаются через
переменные окружения.
