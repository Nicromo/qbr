import json
import logging
import os

log = logging.getLogger("storage")

STORAGE_PATH = os.environ.get("STORAGE_PATH", "storage.json")


def load():
    try:
        with open(STORAGE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            log.info("Загружено из %s: %d записей", STORAGE_PATH, len(data))
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        log.info("Хранилище пустое или не найдено, начинаем с нуля")
        return {}


def save(data):
    with open(STORAGE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    log.info("Сохранено в %s: %d записей", STORAGE_PATH, len(data))


def get_delta(key, new_place, data):
    if key not in data:
        return None
    old_place = data[key].get("place")
    if old_place is None:
        return None
    try:
        return int(old_place) - int(new_place)
    except (ValueError, TypeError):
        return None


def delta_str(delta):
    if delta is None:
        return "🆕"
    if delta > 0:
        return f"⬆️+{delta}"
    if delta < 0:
        return f"⬇️{delta}"
    return "➖"


def has_changes(old_data, new_data):
    if not old_data:
        return True
    for key, new_entry in new_data.items():
        old_entry = old_data.get(key, {})
        if old_entry.get("place") != new_entry.get("place"):
            return True
    for key in old_data:
        if key not in new_data:
            return True
    return False
