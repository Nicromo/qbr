import json
import logging
import os
import threading
import time

import requests

from main import build_report, esc
from mtuci import submit_captcha, CaptchaRequired
from telegram import send_to, send_photo, API, is_configured
import storage
import state_store

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("bot")

SUBS_PATH = os.environ.get("SUBSCRIBERS_PATH", "subscribers.json")
CAPTCHA_STATE_PATH = os.environ.get("CAPTCHA_STATE_PATH", "captcha_state.json")
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", "21600"))
ALLOWED_CHAT_IDS = {
    chat_id.strip()
    for chat_id in os.environ.get("ALLOWED_CHAT_IDS", "").split(",")
    if chat_id.strip()
}

captcha_state = {}


def load_subs():
    if state_store.enabled():
        return state_store.load("subscribers", {})
    try:
        with open(SUBS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_subs(subs):
    if state_store.enabled():
        state_store.save("subscribers", subs)
        return
    directory = os.path.dirname(SUBS_PATH)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(SUBS_PATH, "w", encoding="utf-8") as f:
        json.dump(subs, f, ensure_ascii=False, indent=2)


def _load_captcha_state():
    if state_store.enabled():
        return state_store.load("captcha", {})
    try:
        with open(CAPTCHA_STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_captcha_state(states):
    if state_store.enabled():
        state_store.save("captcha", states)
        return
    directory = os.path.dirname(CAPTCHA_STATE_PATH)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(CAPTCHA_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(states, f, ensure_ascii=False, indent=2)


def _state_for(chat_id):
    key = str(chat_id)
    if chat_id in captcha_state:
        return captcha_state[chat_id]

    saved = _load_captcha_state().get(key)
    if not saved:
        return None

    session = requests.Session()
    session.cookies = requests.utils.cookiejar_from_dict(saved.pop("cookies", {}))
    saved["session"] = session
    captcha_state[chat_id] = saved
    return saved


def _clear_captcha_state(chat_id):
    captcha_state.pop(chat_id, None)
    states = _load_captcha_state()
    states.pop(str(chat_id), None)
    _save_captcha_state(states)


def cmd_start(chat_id, user):
    subs = load_subs()
    if ALLOWED_CHAT_IDS and str(chat_id) not in ALLOWED_CHAT_IDS:
        send_to(chat_id, "⛔ Этот бот доступен только владельцу.")
        return
    name = user.get("first_name", "")
    subs[str(chat_id)] = {"name": name, "auto": True}
    save_subs(subs)
    send_to(chat_id, f"👋 Привет, {name}!\n\nЯ слежу за позициями в списках поступления.")
    cmd_help(chat_id)


def cmd_help(chat_id):
    send_to(
        chat_id,
        "📋 <b>Команды:</b>\n"
        "/check — проверить сейчас\n"
        "/auto — вкл/выкл автоуведомления\n"
        "/status — текущие настройки\n"
        "/help — показать команды\n\n"
        "Если МТУСИ пришлёт капчу, просто отправь боту символы с картинки.",
    )


def cmd_check(chat_id):
    send_to(chat_id, "⏳ Собираю данные...")
    try:
        text, old_data, new_data, captcha = build_report()
        send_to(chat_id, text)
        storage.save(new_data)

        if captcha:
            _request_captcha(chat_id, captcha, old_data, new_data)
    except Exception:
        log.exception("Ошибка при проверке")
        send_to(chat_id, "❌ Ошибка при получении данных")


def handle_captcha_response(chat_id, text):
    state = _state_for(chat_id)
    if not state:
        return False

    send_to(chat_id, "🔄 Проверяю капчу...")

    try:
        result = submit_captcha(state["session"], state["url"], text)
    except CaptchaRequired as captcha:
        _request_captcha(chat_id, captcha, state["old_data"], state["new_data"], refreshed=True)
        return True
    except requests.RequestException:
        log.exception("Ошибка отправки капчи в МТУСИ")
        send_to(chat_id, "❌ МТУСИ временно не отвечает. Попробуй ввести капчу ещё раз.")
        return True

    if not result["my"]:
        _clear_captcha_state(chat_id)
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
    _clear_captcha_state(chat_id)

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


def _request_captcha(chat_id, captcha, old_data, new_data, refreshed=False):
    state = {
        "session": captcha.session,
        "url": captcha.url,
        "old_data": old_data,
        "new_data": new_data,
    }
    captcha_state[chat_id] = state
    saved = _load_captcha_state()
    saved[str(chat_id)] = {
        "cookies": requests.utils.dict_from_cookiejar(captcha.session.cookies),
        "url": captcha.url,
        "old_data": old_data,
        "new_data": new_data,
    }
    _save_captcha_state(saved)
    caption = (
        "🔐 Капча не подошла, вот новая картинка.\nВведи символы с неё:"
        if refreshed
        else "🔐 МТУСИ требует капчу.\nВведи символы с картинки:"
    )
    send_photo(chat_id, captcha.image_bytes, caption)


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
    "/help": lambda cid, user: cmd_help(cid),
}


def auto_check_once():
    try:
        text, old_data, new_data, captcha = build_report()
        changed = storage.has_changes(old_data, new_data)
        storage.save(new_data)

        subs = load_subs()
        if captcha:
            for cid, info in subs.items():
                if info.get("auto", True):
                    _request_captcha(int(cid), captcha, old_data, new_data)

        if not changed:
            log.info("Автопроверка: без изменений")
            return True

        sent = 0
        for cid, info in subs.items():
            if info.get("auto", True):
                try:
                    send_to(int(cid), text)
                    sent += 1
                except Exception:
                    log.exception("Ошибка отправки %s", cid)
        log.info("Автопроверка: отправлено %d подписчикам", sent)
        return True
    except Exception:
        log.exception("Ошибка автопроверки")
        return False


def auto_check_loop():
    while True:
        time.sleep(CHECK_INTERVAL)
        auto_check_once()


BOT_COMMANDS = [
    {"command": "start", "description": "Начать работу с ботом"},
    {"command": "check", "description": "Проверить позиции сейчас"},
    {"command": "auto", "description": "Вкл/выкл автоуведомления"},
    {"command": "status", "description": "Текущие настройки"},
    {"command": "help", "description": "Показать команды"},
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


def start_health_server():
    port = os.environ.get("PORT")
    if not port:
        return

    from flask import Flask

    app = Flask(__name__)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=int(port), threaded=True),
        daemon=True,
    ).start()
    log.info("HTTP health endpoint started on port %s", port)


def process_updates(offset=None, timeout=30):
    params = {"timeout": timeout, "allowed_updates": ["message"]}
    if offset:
        params["offset"] = offset
    r = requests.get(f"{API}/getUpdates", params=params, timeout=timeout + 5)
    r.raise_for_status()

    for update in r.json().get("result", []):
        offset = update["update_id"] + 1
        process_update(update)

    return offset


def process_update(update):
    msg = update.get("message")
    if not msg:
        return

    text = msg.get("text", "")
    chat_id = msg["chat"]["id"]
    user = msg.get("from", {})
    cmd = text.split("@")[0] if "@" in text else text
    handler = COMMANDS.get(cmd)
    if handler:
        handler(chat_id, user)
    elif not text.startswith("/") and text.strip():
        handle_captcha_response(chat_id, text)


def main():
    if not is_configured():
        raise RuntimeError("Укажи TELEGRAM_BOT_TOKEN в .env перед запуском бота")
    if CHECK_INTERVAL <= 0:
        raise RuntimeError("CHECK_INTERVAL должен быть положительным числом")
    log.info("Бот запущен, интервал проверки: %d сек", CHECK_INTERVAL)

    set_commands()
    start_health_server()

    t = threading.Thread(target=auto_check_loop, daemon=True)
    t.start()

    offset = None
    while True:
        try:
            offset = process_updates(offset)

        except requests.exceptions.Timeout:
            continue
        except Exception:
            log.exception("Ошибка polling")
            time.sleep(5)


if __name__ == "__main__":
    main()
