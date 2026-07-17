import base64
import logging
import re

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


class CaptchaRequired(Exception):
    def __init__(self, image_bytes, session, url):
        self.image_bytes = image_bytes
        self.session = session
        self.url = url


def _is_captcha_page(html):
    return "sendF()" in html and "Captcha-Code" in html


def _extract_captcha_image(html):
    match = re.search(
        r"<img class=capture src=data:image/png;base64,([A-Za-z0-9+/=]+)>", html
    )
    if match:
        return base64.b64decode(match.group(1))
    return None


def _parse_group_info(html, group_id):
    result = {
        "direction": "МТУСИ",
        "my": None,
    }

    soup = BeautifulSoup(html, "html.parser")
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


def submit_captcha(session, url, captcha_text):
    """Submit a Telegram user's answer and return the refreshed MTUCI result."""
    headers = {**HEADERS, "Captcha-Code": captcha_text.upper().strip()}
    response = session.post(url, headers=headers, timeout=30)
    response.raise_for_status()
    r = session.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    if _is_captcha_page(r.text):
        image_bytes = _extract_captcha_image(r.text)
        if image_bytes:
            raise CaptchaRequired(image_bytes, session, url)
        raise RuntimeError("МТУСИ вернул страницу капчи без изображения")
    return _parse_group_info(r.text, url)


def get_group_info(url, session=None):
    if session is None:
        session = requests.Session()

    log.info("Запрос %s", url)
    r = session.get(url, headers=HEADERS, timeout=30)
    log.info("HTTP %d, URL: %s, длина: %d", r.status_code, r.url, len(r.text))
    r.raise_for_status()

    if _is_captcha_page(r.text):
        log.warning("МТУСИ: обнаружена капча")
        image_bytes = _extract_captcha_image(r.text)
        if image_bytes:
            raise CaptchaRequired(image_bytes, session, url)
        log.error("МТУСИ: капча без изображения")
        return {"direction": "МТУСИ", "my": None}

    return _parse_group_info(r.text, url)
