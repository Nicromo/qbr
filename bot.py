import json
import logging
import os
import threading
import time

import requests

from main import build_report, build_mtuci_section, esc
from mtuci import solve_captcha, get_group_info as get_mtuci_group, CaptchaRequired
from telegram import send_to, send_photo, API
import storage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("bot")

SUBS_PATH = os.environ.get("SUBSCRIBERS_PATH", "subscribers.json")
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", "1800"))

captcha_state = {}


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
        text, old_data, new_data, captcha = build_report()
        send_to(chat_id, text)
        storage.save(new_data)

        if captcha:
            captcha_state[chat_id] = {
                "session": captcha.session,
                "url": captcha.url,
                "old_data": old_data,
                "new_data": new_data,
            }
            send_photo(
                chat_id,
                captcha.image_bytes,
                "🔐 МТУСИ требует капчу.\nВведи символы с картинки:",
            )
    except Exception:
        log.exception("Ошибка при проверке")
        send_to(chat_id, "❌ Ошибка при получении данных")


def handle_captcha_response(chat_id, text):
    state = captcha_state.pop(chat_id, None)
    if not state:
        return False

    send_to(chat_id, "🔄 Проверяю капчу...")

    if not solve_captcha(state["session"], state["url"], text):
        send_to(chat_id, "❌ Неверная капча. Нажми /check чтобы попробовать снова")
        return True

    try:
        result = get_mtuci_group(state["url"], session=state["session"])
    except CaptchaRequired:
        send_to(chat_id, "❌ Капча снова. Нажми /check чтобы попробовать снова")
        return True

    if not result["my"]:
        send_to(chat_id, "🏛 <b>МТУСИ</b>\n\n❌ Данные не найдены")
        return True

    me = result["my"]
    old_data = state["old_data"]
    new_data = state["new_data"]

    key = "mtuci_main"
    delta = storage.get_delta(key, me["place"], old_data)
    new_data[key] = {
        "uni": "МТУСИ",
        "name": result["direction"],
        "place": me["place"],
    }
    storage.save(new_data)

    msg = (
        f"<b>🏛 МТУСИ</b>\n\n"
        f"📚 <b>{esc(result['direction'])}</b>\n"
        f"   Место: <code>{me['place']}</code> {storage.delta_str(delta)}\n"
        f"   Приоритет: <code>{me['priority']}</code>  │  "
        f"ИД: <code>{me['id']}</code>\n"
        f"   Баллы: <code>{me['scores']}</code>\n"
    )
    send_to(chat_id, msg)
    return True


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
            text, old_data, new_data, _ = build_report()
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


BOT_COMMANDS = [
    {"command": "start", "description": "Начать работу с ботом"},
    {"command": "check", "description": "Проверить позиции сейчас"},
    {"command": "auto", "description": "Вкл/выкл автоуведомления"},
    {"command": "status", "description": "Текущие настройки"},
]


def set_commands():
    r = requests.post(
        f"{API}/setMyCommands",
        json={"commands": BOT_COMMANDS},
        timeout=10,
    )
    if r.ok:
        log.info("Команды бота зарегистрированы")
    else:
        log.warning("Не удалось зарегистрировать команды: %s", r.text)


def main():
    log.info("Бот запущен, интервал проверки: %d сек", CHECK_INTERVAL)

    set_commands()

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
                elif not text.startswith("/") and text.strip():
                    handle_captcha_response(chat_id, text)

        except requests.exceptions.Timeout:
            continue
        except Exception:
            log.exception("Ошибка polling")
            time.sleep(5)


if __name__ == "__main__":
    main()
