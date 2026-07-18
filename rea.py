import json
import logging
import os

import requests

import settings  # noqa: F401

log = logging.getLogger("rea")

REA_SITE_URL = "https://abitrating.rea.ru/"
REA_STATUS_AVAILABLE = "available"
REA_STATUS_MAINTENANCE = "maintenance"


class ReaNotConfigured(RuntimeError):
    pass


class ReaAuthError(RuntimeError):
    pass


def _load_config():
    jwt = os.environ.get("REA_JWT", "")
    profile = os.environ.get("REA_PROFILE", "")
    if jwt and profile:
        return {"jwt": jwt, "profile": profile}

    path = os.environ.get("REA_CONFIG_PATH", "config.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)["rea"]
    except FileNotFoundError as exc:
        raise ReaNotConfigured(
            "РЭА не настроен: укажи REA_JWT и REA_PROFILE в .env"
        ) from exc


def _get_config():
    cfg = _load_config()
    if not cfg.get("jwt") or not cfg.get("profile"):
        raise ReaNotConfigured("РЭА не настроен: проверь REA_JWT и REA_PROFILE")
    return cfg


def _headers(cfg):
    return {
        "apikey": cfg["jwt"],
        "Authorization": f"Bearer {cfg['jwt']}",
    }


def _raise_for_status(response):
    if response.status_code in (401, 403):
        raise ReaAuthError("РЭУ отклонил ключ доступа")
    response.raise_for_status()


def get_service_status():
    """Return the public availability status before querying protected lists."""
    response = requests.get(REA_SITE_URL, timeout=20)
    response.raise_for_status()
    page_text = response.text.lower()
    if "техническ" in page_text and "обслуживан" in page_text:
        return REA_STATUS_MAINTENANCE
    return REA_STATUS_AVAILABLE


def get_all_my_data():
    cfg = _get_config()
    log.info("Запрос списка абитуриентов для профиля %s", cfg["profile"])

    r = requests.get(
        "https://abitrating.rea.ru/rest/v1/entrants",
        headers=_headers(cfg),
        params={
            "select": "*",
            "unique_code_profile": f"eq.{cfg['profile']}",
            "limit": 100,
        },
        timeout=30,
    )
    _raise_for_status(r)

    data = r.json()
    log.info("Получено %d записей", len(data))
    return data


def get_group_info(group_id):
    cfg = _get_config()
    log.info("Запрос группы %s", group_id)

    r = requests.get(
        "https://abitrating.rea.ru/rest/v1/competitive_groups",
        headers=_headers(cfg),
        params={
            "select": "*",
            "competitive_group_id": f"eq.{group_id}",
        },
        timeout=30,
    )
    _raise_for_status(r)

    data = r.json()

    if data:
        log.info("Группа найдена: %s", data[0].get("competitive_group_name", "?"))
        return data[0]

    log.warning("Группа %s не найдена", group_id)
    return None
