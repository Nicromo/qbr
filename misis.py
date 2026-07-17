import logging

import requests
from bs4 import BeautifulSoup

log = logging.getLogger("misis")

BASE_URL = (
    "https://misis.ru/applicants/admission/progress/"
    "baccalaureate-and-specialties/"
    "spiskipodavshihzayavleniya/list-p/"
)

MY_CODE = "2164745"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/138.0 Safari/537.36"
    )
}


def get_group_info(group_id: str):
    log.info("Запрос группы %s", group_id)

    r = requests.get(
        BASE_URL,
        params={"id": group_id},
        headers=HEADERS,
        timeout=30,
    )
    r.raise_for_status()
    log.info("HTTP %d, длина ответа %d", r.status_code, len(r.text))

    soup = BeautifulSoup(r.text, "html.parser")

    table = soup.find("table")
    if table is None:
        raise RuntimeError(f"Таблица не найдена для {group_id}")

    tbody = table.find("tbody")
    if tbody is None:
        raise RuntimeError(f"tbody не найден для {group_id}")

    rows = tbody.find_all("tr")

    date_tag = soup.find("date")
    direction_tag = soup.find("direction")
    itog_tag = soup.find("itog")

    result = {
        "update_time": date_tag.get_text(strip=True) if date_tag else "?",
        "direction": direction_tag.get_text(strip=True) if direction_tag else group_id,
        "places": int(itog_tag.get_text(strip=True)) if itog_tag else 0,
        "my": None,
    }

    if not direction_tag:
        log.warning("Тег <direction> не найден для %s", group_id)
    if not itog_tag:
        log.warning("Тег <itog> не найден для %s — мест = 0", group_id)

    for row in rows:
        cols = [td.get_text(" ", strip=True) for td in row.find_all("td")]

        if not cols or MY_CODE not in cols:
            continue

        log.info("Найден в МИСИС: %s", cols)

        result["my"] = {
            "place": int(cols[0]),
            "priority": cols[3],
            "scores": 0,
            "id": 0,
            "to_pass": int(cols[0]) - result["places"],
        }

        for i, value in enumerate(cols):
            if i < 4:
                continue

            try:
                num = int(value)
            except ValueError:
                continue

            if num >= 100 and result["my"]["scores"] == 0:
                result["my"]["scores"] = num
                continue

            if (
                result["my"]["scores"] > 0
                and 0 <= num <= 10
                and result["my"]["id"] == 0
            ):
                result["my"]["id"] = num

        break

    if not result["my"]:
        log.info("Не найден в списке %s", group_id)

    return result
