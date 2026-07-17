import logging
import os

import requests

import settings  # noqa: F401

log = logging.getLogger("telegram")

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
API = f"https://api.telegram.org/bot{TOKEN}"

MAX_LENGTH = 4096


def is_configured():
    return bool(TOKEN)


def send(text, parse_mode="HTML"):
    chunks = _split(text)
    log.info("Отправка: %d символов, %d частей", len(text), len(chunks))

    for i, chunk in enumerate(chunks):
        payload = {"chat_id": CHAT_ID, "text": chunk}
        if parse_mode:
            payload["parse_mode"] = parse_mode

        r = requests.post(
            f"{API}/sendMessage",
            data=payload,
            timeout=30,
        )

        if not r.ok:
            log.error("Telegram ошибка [%d]: %s", r.status_code, r.text)
            r.raise_for_status()

        log.info("Часть %d/%d отправлена (код %d)", i + 1, len(chunks), r.status_code)


def send_to(chat_id, text, parse_mode="HTML"):
    chunks = _split(text)
    for chunk in chunks:
        payload = {"chat_id": chat_id, "text": chunk}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        r = requests.post(f"{API}/sendMessage", data=payload, timeout=30)
        if not r.ok:
            log.warning("Telegram %s: %s", r.status_code, r.text)


def send_photo(chat_id, photo_bytes, caption=""):
    r = requests.post(
        f"{API}/sendPhoto",
        data={"chat_id": chat_id, "caption": caption},
        files={"photo": ("captcha.png", photo_bytes, "image/png")},
        timeout=30,
    )
    if not r.ok:
        log.warning("Telegram photo %s: %s", r.status_code, r.text)


def _split(text):
    if len(text) <= MAX_LENGTH:
        return [text]

    chunks = []
    while text:
        if len(text) <= MAX_LENGTH:
            chunks.append(text)
            break

        cut = text.rfind("\n", 0, MAX_LENGTH)
        if cut <= 0:
            cut = MAX_LENGTH

        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")

    return chunks
