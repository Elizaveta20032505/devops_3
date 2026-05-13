# Лабораторная работа №3. Размещение секретов в хранилище

Развитие сервиса из лабораторной №2: креды PostgreSQL вынесены из переменных
окружения сервиса в **хранилище секретов HashiCorp Vault**, поднимаемое
отдельным контейнером. API получает секреты в рантайме по HTTP.

## Что изменилось относительно лабы №2

| Область | Лаба 2 | Лаба 3 |
|---|---|---|
| Где живут креды БД | `.env` (локально) / Jenkins Credentials → ENV контейнера `api` | KV v2 в Vault по пути `secret/postgres` |
| Как `api` получает креды | `os.environ[...]` | HTTP `GET /v1/secret/data/postgres` в Vault |
| Локальный конфиг с секретами | `.env.example` (с плейсхолдером) | удалён; есть только `secrets.env.example` |
| Контейнеры | `db` + `api` | `vault` + `db` + `api` |
| Инициализация хранилища | — | сам контейнер `vault` на старте кладёт креды в `secret/postgres` |

## Архитектура

```
                                ┌─────────────────────────────────┐
                       ┌────────► HashiCorp Vault (dev)           │
                       │ HTTP   │  KV v2: secret/postgres         │
   client              │ secret │  (значения записаны самим       │
     │                 │        │   контейнером на старте)        │
     ▼                 │        └─────────────────────────────────┘
┌────────────────┐     │
│ FastAPI (api)  │─────┘
│ /predict, ...  │
└────────┬───────┘
         │ psycopg2 (host/user/password из Vault)
         ▼
   ┌────────────────────┐
   │ PostgreSQL (db)    │
   │  predictions       │
   │  training_data     │
   └────────────────────┘
```

## Состав проекта

| Файл | Назначение |
|---|---|
| `src/api.py` | FastAPI: `/health`, `/predict`, `/predictions` |
| `src/secrets.py` | Клиент Vault: HTTP-запрос секретов из KV v2 с ретраями |
| `src/db.py` | Подключение к Postgres, креды берутся ТОЛЬКО из Vault |
| `src/inference.py`, `src/train.py`, `src/prepare_data.py` | Обучение и инференс модели |
| `scripts/seed_db.py` | Загрузка `data/raw/data.csv` в `training_data` |
| `scripts/run_scenarios.py` | Прогон сценариев из `scenario.json` |
| `docker-compose.yml` | Сервисы `vault`, `db`, `api` |
| `Dockerfile` | Сборка образа сервиса `api` |
| `Jenkinsfile` | CI: сборка образа и публикация в Docker Hub |
| `CD/Jenkinsfile` | CD: поднятие vault+db+api, инициализация секретов, функциональные сценарии |
| `config.ini` | Только нечувствительные параметры (пути, имена таблиц) |
| `secrets.env.example` | Шаблон bootstrap-файла для Vault и Postgres; реальный `secrets.env` в `.gitignore` |


## Vault

Запускается образом `hashicorp/vault:1.17`.

- Адрес внутри docker-сети: `http://vault:8200`.
- Адрес с хоста: `http://localhost:8200`.
- KV v2 включён по умолчанию на mount `secret/`.
- Путь записи: `secret/postgres`.
- Путь чтения через HTTP (KV v2 ставит `/data/` между mount и path):
  `secret/data/postgres`.
- Аутентификация — единственный root-токен из `VAULT_TOKEN` (хардкод в
  `secrets.env`, файл в `.gitignore`).

Содержимое секрета:

```
host=db
port=5432
dbname=<POSTGRES_DB>
username=<POSTGRES_USER>
password=<POSTGRES_PASSWORD>
```

Инициализация выполняется самим контейнером `vault`: его `command` —
маленький shell-скрипт, который запускает `vault server -dev` в фоне,
ждёт `vault status`, делает `vault kv put secret/postgres ...` и затем
`wait` на pid процесса vault (чтобы контейнер не завершился сразу после
записи). Healthcheck контейнера специально проверяет не просто статус
сервера, а наличие самого секрета — `vault kv get -mount=secret postgres`.
Поэтому `api` через `depends_on: condition: service_healthy` гарантированно
стартует только после того, как креды реально лежат в Vault.

```yaml
entrypoint: ["/bin/sh", "-c"]
command:
  - |
    vault server -dev -dev-root-token-id="$$VAULT_TOKEN" &
    VAULT_PID=$$!
    until vault status >/dev/null 2>&1; do sleep 1; done
    vault kv put secret/postgres host=db port=5432 \
      dbname=$$POSTGRES_DB username=$$POSTGRES_USER password=$$POSTGRES_PASSWORD
    wait $$VAULT_PID
```


## Bootstrap-параметры (хардкод, в `.gitignore`)

Compose интерполирует `${...}` из файла, заданного флагом `--env-file`.

```bash
cp secrets.env.example secrets.env
docker compose --env-file secrets.env up -d --build
```

`secrets.env` содержит:

```
VAULT_TOKEN=devops3-root-token
POSTGRES_DB=devops
POSTGRES_USER=devops
POSTGRES_PASSWORD=change_me
```

Эти значения используются только для:

1. инициализации Postgres (Postgres ENV API),
2. одноразовой записи в Vault на старте контейнера `vault`.

Само приложение `api` эти переменные не читает — оно знает только
`VAULT_ADDR` и `VAULT_TOKEN`.

## CI / CD

### CI (`Jenkinsfile`)

1. Checkout.
2. `docker build -t <user>/devops3-api`.
3. Логин в Docker Hub через `dockerhub-creds`.
4. `docker push` с тегами `build-<N>` и `latest`.
5. Триггер CD-job `devops3-model-cd`.


### CD (`CD/Jenkinsfile`)

Нужны Jenkins Credentials:

| ID | Тип | Назначение |
|---|---|---|
| `dockerhub-creds` | Username with password | логин в Docker Hub |
| `pg-creds` | Username with password | `POSTGRES_USER` / `POSTGRES_PASSWORD` |
| `vault-token-creds` | Username with password | **Password** = root-токен Vault dev-mode; **Username** — любая метка (не используется пайплайном) |

Шаги:

1. Checkout.
2. Stop/remove старых контейнеров `devops3-*`.
3. Login + pull `IMAGE_TAG` с Docker Hub.
4. Из credentials формируется временный `secrets.env`.
5. `docker compose --env-file secrets.env up -d` — поднимаются `vault`,
   `db`, `api` (vault сам себя инициализирует на старте).
6. Проверка, что секрет лежит в Vault: `vault kv get -mount=secret postgres`.
7. (опционально) seed таблицы `training_data`.
8. Прогон сценариев `scripts/run_scenarios.py` по `scenario.json`.
9. Always-блок: сохранение логов compose, `compose down -v`,
   удаление `secrets.env`, `docker logout`.

## Безопасность

- В коде и в git нет ни одной кред-строки. Образ `devops3-api` не содержит
  паролей и адреса БД.
- Бутстрап-файл `secrets.env` существует только локально и на агенте Jenkins
  в момент пайплайна; после `post { always }` он удаляется.
- В рантайме `api` знает только `VAULT_ADDR` и `VAULT_TOKEN`. Реальные
  креды Postgres получает по HTTP при инициализации схемы и при каждом
  подключении.
- Для production вместо dev-mode и root-токена используют unseal-ключи,
  AppRole/Kubernetes-auth, политики доступа и постоянное хранилище (Raft,
  Consul, S3 и т.п.).

## Эндпоинты и сценарии

`scenario.json` описывает четыре шага:

1. `GET /health` — проверка готовности сервиса.
2. `GET /openapi.json` — доступность спецификации.
3. `POST /predict` — предсказание на нулевых признаках.
4. `GET /predictions` — выборка последних записей из БД (читает Postgres,
   используя креды, полученные из Vault).
