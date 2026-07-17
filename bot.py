import json
import logging
import os
import threading
import time

import requests

from main import build_report
from telegram import send_to, _split, API
import storage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("bot")

SUBS_PATH = os.environ.get("SUBSCRIBERS_PATH", "subscribers.json")
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", "1800"))


def load_subs():
    try:
        with open(SUBS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_subs(subs):
    with open(SUBS_PATH, "w", encoding="utf-8") as f:
        json.dump(subs, f, ensure_ascii=False, indent=2)


def cmd_start(chat_id, user):
    subs = load_subs()
    name = user.get("first_name", "")
    subs[str(chat_id)] = {"name": name, "auto": True}
    save_subs(subs)
    send_to(chat_id,
        f"👋 Привет, {name}!\n\n"
        "Я слежу за позициями в списках поступления.\n\n"
        "📋 <b>Команды:</b>\n"
        "/check — проверить сейчас\n"
        "/auto — вкл/выкл автоуведомления\n"
        "/status — текущие настройки"
    )


def cmd_check(chat_id):
    send_to(chat_id, "⏳ Собираю данные...")
    try:
        text, _, new_data = build_report()
        send_to(chat_id, text)
        storage.save(new_data)
    except Exception:
        log.exception("Ошибка при проверке")
        send_to(chat_id, "❌ Ошибка при получении данных")


def cmd_auto(chat_id):
    subs = load_subs()
    key = str(chat_id)
    if key not in subs:
        send_to(chat_id, "Сначала нажми /start")
        return
    current = subs[key].get("auto", True)
    subs[key]["auto"] = not current
    save_subs(subs)
    state = "включены ✅" if not current else "выключены ❌"
    send_to(chat_id, f"Автоуведомления {state}")


def cmd_status(chat_id):
    subs = load_subs()
    key = str(chat_id)
    if key not in subs:
        send_to(chat_id, "Сначала нажми /start")
        return
    auto = "✅ Вкл" if subs[key].get("auto", True) else "❌ Выкл"
    send_to(chat_id,
        f"⚙️ <b>Настройки</b>\n"
        f"Автоуведомления: {auto}\n"
        f"Интервал: каждые {CHECK_INTERVAL // 60} мин"
    )


COMMANDS = {
    "/start": lambda cid, user: cmd_start(cid, user),
    "/check": lambda cid, user: cmd_check(cid),
    "/auto": lambda cid, user: cmd_auto(cid),
    "/status": lambda cid, user: cmd_status(cid),
}


def auto_check_loop():
    while True:
        time.sleep(CHECK_INTERVAL)
        try:
            text, old_data, new_data = build_report()
            changed = storage.has_changes(old_data, new_data)
            storage.save(new_data)

            if not changed:
                log.info("Автопроверка: без изменений")
                continue

            subs = load_subs()
            sent = 0
            for cid, info in subs.items():
                if info.get("auto", True):
                    try:
                        send_to(int(cid), text)
                        sent += 1
                    except Exception:
                        log.exception("Ошибка отправки %s", cid)
            log.info("Автопроверка: отправлено %d подписчикам", sent)
        except Exception:
            log.exception("Ошибка автопроверки")


def main():
    log.info("Бот запущен, интервал проверки: %d сек", CHECK_INTERVAL)

    t = threading.Thread(target=auto_check_loop, daemon=True)
    t.start()

    offset = None
    while True:
        try:
            params = {"timeout": 30}
            if offset:
                params["offset"] = offset
            r = requests.get(f"{API}/getUpdates", params=params, timeout=35)
            updates = r.json().get("result", [])

            for update in updates:
                offset = update["update_id"] + 1
                msg = update.get("message")
                if not msg:
                    continue

                text = msg.get("text", "")
                chat_id = msg["chat"]["id"]
                user = msg.get("from", {})

                cmd = text.split("@")[0] if "@" in text else text
                handler = COMMANDS.get(cmd)
                if handler:
                    handler(chat_id, user)

        except requests.exceptions.Timeout:
            continue
        except Exception:
            log.exception("Ошибка polling")
            time.sleep(5)


if __name__ == "__main__":
    main()
