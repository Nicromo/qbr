import json
import logging
import os

import requests

log = logging.getLogger("rea")


def _load_config():
    path = os.environ.get("REA_CONFIG_PATH", "config.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)["rea"]


cfg = _load_config()

headers = {
    "apikey": cfg["jwt"],
    "Authorization": f"Bearer {cfg['jwt']}",
}


def get_all_my_data():
    log.info("Запрос списка абитуриентов для профиля %s", cfg["profile"])

    r = requests.get(
        "https://abitrating.rea.ru/rest/v1/entrants",
        headers=headers,
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
    log.info("Запрос группы %s", group_id)

    r = requests.get(
        "https://abitrating.rea.ru/rest/v1/competitive_groups",
        headers=headers,
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
