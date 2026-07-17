import logging
import os

import requests

log = logging.getLogger("telegram")

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

MAX_LENGTH = 4096


def send(text):
    chunks = _split(text)
    log.info("Отправка: %d символов, %d частей", len(text), len(chunks))

    for i, chunk in enumerate(chunks):
        r = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": chunk},
            timeout=30,
        )

        if not r.ok:
            log.error("Telegram ошибка [%d]: %s", r.status_code, r.text)
            r.raise_for_status()

        log.info("Часть %d/%d отправлена (код %d)", i + 1, len(chunks), r.status_code)


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
