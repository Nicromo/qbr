import logging

import requests
from bs4 import BeautifulSoup

log = logging.getLogger("mtuci")

MY_CODE = "2164745"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/138.0 Safari/537.36"
    )
}


def get_group_info(url):
    result = {
        "direction": "МТУСИ",
        "my": None,
    }

    log.info("Запрос %s", url)
    r = requests.get(url, headers=HEADERS, timeout=30)
    log.info("HTTP %d, URL: %s, длина: %d", r.status_code, r.url, len(r.text))
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    tables = soup.find_all("table")
    log.info("Найдено таблиц: %d", len(tables))

    if not tables:
        log.warning("Таблицы не найдены на странице МТУСИ")
        return result

    for table in tables:
        for row in table.find_all("tr"):
            cols = [td.get_text(strip=True) for td in row.find_all("td")]

            if MY_CODE not in cols:
                continue

            log.info("Найден в МТУСИ: %s", cols)

            if len(cols) < 10:
                log.error(
                    "Недостаточно колонок: %d (нужно >= 10), строка: %s",
                    len(cols), cols,
                )
                return result

            result["my"] = {
                "place": cols[0],
                "id": cols[7],
                "scores": cols[3],
                "priority": cols[9],
            }
            return result

    log.info("Не найден в МТУСИ (код %s)", MY_CODE)
    return result
