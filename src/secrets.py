"""Клиент HashiCorp Vault. Получает секреты по HTTP через KV v2 API.

Локальные конфиг-файлы с секретами не используются: сервис ходит в Vault
по адресу VAULT_ADDR с токеном VAULT_TOKEN.
"""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger("vault")


class VaultError(RuntimeError):
    """Не удалось получить секреты из Vault."""


def _required_env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise VaultError(f"Не задана переменная окружения {name} для доступа к Vault")
    return val


def fetch_secret(path: str | None = None, retries: int = 30, delay_sec: float = 1.0) -> dict[str, Any]:
    """Читает KV v2 секрет из Vault. С повторами на случай, что Vault ещё не готов.

    path: KV v2 read path, например 'secret/data/postgres'.
    """
    addr = _required_env("VAULT_ADDR").rstrip("/")
    token = _required_env("VAULT_TOKEN")
    secret_path = path or os.environ.get("VAULT_SECRET_PATH", "secret/data/postgres")
    url = f"{addr}/v1/{secret_path}"
    req = urllib.request.Request(url, headers={"X-Vault-Token": token})

    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            data = payload.get("data", {}).get("data")
            if not isinstance(data, dict):
                raise VaultError(f"Ответ Vault без data.data: {payload!r}")
            logger.info("Получены секреты из Vault: %s (ключей: %d)", secret_path, len(data))
            return data
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:200]
            raise VaultError(f"Vault HTTP {e.code} на {url}: {body}") from e
        except urllib.error.URLError as e:
            last_err = e
            logger.warning("Vault недоступен (попытка %d/%d): %s", attempt, retries, e)
            time.sleep(delay_sec)

    raise VaultError(f"Vault недоступен по адресу {url}: {last_err}")
