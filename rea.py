import json
import logging
import os

import requests

import settings  # noqa: F401

log = logging.getLogger("rea")


class ReaNotConfigured(RuntimeError):
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
    r.raise_for_status()

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
    r.raise_for_status()

    data = r.json()

    if data:
        log.info("Группа найдена: %s", data[0].get("competitive_group_name", "?"))
        return data[0]

    log.warning("Группа %s не найдена", group_id)
    return None
