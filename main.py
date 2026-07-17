import logging
import os
import re
from datetime import datetime, timezone, timedelta

from misis import get_group_info as get_misis_group
from rea import get_all_my_data, get_group_info
from telegram import send
from mtuci import get_group_info as get_mtuci_group, CaptchaRequired
import storage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("main")

MSK = timezone(timedelta(hours=3))

FORCE_SEND = os.environ.get("FORCE_SEND", "").lower() in ("1", "true", "yes")


def esc(text):
    for ch in ("&", "<", ">"):
        text = str(text).replace(ch, {"&": "&amp;", "<": "&lt;", ">": "&gt;"}[ch])
    return text


def pass_indicator(to_pass):
    if isinstance(to_pass, str):
        return to_pass
    if to_pass <= 0:
        return f"✅ Проходишь ({to_pass})"
    if to_pass <= 5:
        return f"🟡 Почти ({to_pass})"
    return f"🔴 {to_pass}"


def clean_name(name):
    for word in [
        "Только", "только РФ", "РФ", "Очная", "очная",
        "ВШКМиС", "РЭУ им. Г.В. Плеханова", "РЭУ", "Москва",
    ]:
        name = name.replace(word, "")

    name = re.sub(r"(,\s*)+", ", ", name)
    name = " ".join(name.split()).strip(" ,-()")
    return name


def build_rea_section(old_data, new_data):
    section = "<b>🏛 РЭУ Плеханова</b>\n\n"

    rows = get_all_my_data()
    log.info("РЭУ: получено %d записей", len(rows))

    for row in rows:
        group = get_group_info(row["competitive_group_id"])
        log.info("РЭУ группа: %s", group)

        if group:
            group_name = group.get(
                "competitive_group_name",
                group.get("speciality_name", "Неизвестное направление"),
            )
            group_name = clean_name(group_name)
            places = group.get("admission_volume", 0)
        else:
            group_name = "Неизвестное направление"
            places = 0

        to_pass = row["rating"] - places if places else "-"
        key = f"rea_{row['competitive_group_id']}"
        delta = storage.get_delta(key, row["rating"], old_data)

        new_data[key] = {
            "uni": "РЭУ",
            "name": group_name,
            "place": row["rating"],
            "places": places,
        }

        section += (
            f"📚 <b>{esc(group_name)}</b>\n"
            f"   Место: <code>{row['rating']}</code> {storage.delta_str(delta)}  │  "
            f"Мест: <code>{places}</code>\n"
            f"   Приоритет: <code>{row['priority']}</code>  │  "
            f"ИД: <code>{row['achievements_mark']}</code>\n"
            f"   Сумма: <code>{row['sum_mark']}</code>\n"
            f"   ➜ {pass_indicator(to_pass)}\n\n"
        )

    return section


MISIS_GROUPS = [
    {"id": "BVO-BUDJ-O-010304-NITU_MISIS-OKM-000006850", "type": "Бюджет"},
    {"id": "BVO-BUDJ-O-090000-NITU_MISIS-OKM-000006867", "type": "Бюджет"},
    {"id": "BVO-BUDJ-O-270303-NITU_MISIS-OKM-000007070", "type": "Бюджет"},
    {"id": "BVO-BUDJ-O-380305-NITU_MISIS-OKM-000007050", "type": "Бюджет"},
    {"id": "BVO-COMM-O-010304-NITU_MISIS-OKM-000006848", "type": "Контракт"},
    {"id": "BVO-COMM-O-090000-NITU_MISIS-OKM-000006865", "type": "Контракт"},
    {"id": "BVO-COMM-O-270303-NITU_MISIS-OKM-000007068", "type": "Контракт"},
    {"id": "BVO-COMM-O-380305-NITU_MISIS-OKM-000007048", "type": "Контракт"},
]


def build_misis_section(old_data, new_data):
    section = "<b>🏛 МИСИС</b>\n\n"

    for group in MISIS_GROUPS:
        misis = get_misis_group(group["id"])

        if not misis["my"]:
            log.info("МИСИС %s: не найден в списке", group["id"])
            continue

        me = misis["my"]
        log.info("МИСИС %s: место %s", group["id"], me["place"])

        key = f"misis_{group['id']}"
        delta = storage.get_delta(key, me["place"], old_data)

        new_data[key] = {
            "uni": "МИСИС",
            "name": misis["direction"],
            "type": group["type"],
            "place": me["place"],
            "places": misis["places"],
        }

        badge = "🆓" if group["type"] == "Бюджет" else "💰"

        section += (
            f"📚 <b>{esc(misis['direction'])}</b>  {badge} {esc(group['type'])}\n"
            f"   Место: <code>{me['place']}</code> {storage.delta_str(delta)}  │  "
            f"Мест: <code>{misis['places']}</code>\n"
            f"   Приоритет: <code>{me['priority']}</code>  │  "
            f"ИД: <code>{me['id']}</code>\n"
            f"   Баллы: <code>{me['scores']}</code>\n"
            f"   ➜ {pass_indicator(me['to_pass'])}\n\n"
        )

    return section


MTUCI_URL = (
    "https://abitur.mtuci.ru/ranked_lists/spisok.php?"
    "valueSearch=2164745&"
    "priznakViev=budg&"
    "levelTarget=bak_main&"
    "form=%D0%9E%D1%87%D0%BD%D0%B0%D1%8F&"
    "originalFilter=&"
    "search_type=uniqueID&"
    "originalView=all"
)


def build_mtuci_section(old_data, new_data):
    section = "<b>🏛 МТУСИ</b>\n\n"

    result = get_mtuci_group(MTUCI_URL)

    if result["my"]:
        me = result["my"]
        log.info("МТУСИ: место %s", me["place"])

        key = "mtuci_main"
        delta = storage.get_delta(key, me["place"], old_data)

        new_data[key] = {
            "uni": "МТУСИ",
            "name": result["direction"],
            "place": me["place"],
        }

        section += (
            f"📚 <b>{esc(result['direction'])}</b>\n"
            f"   Место: <code>{me['place']}</code> {storage.delta_str(delta)}\n"
            f"   Приоритет: <code>{me['priority']}</code>  │  "
            f"ИД: <code>{me['id']}</code>\n"
            f"   Баллы: <code>{me['scores']}</code>\n\n"
        )
    else:
        log.warning("МТУСИ: данные не найдены")
        section += "❌ Данные не найдены\n\n"

    return section


def build_summary(new_data):
    passing = 0
    almost = 0
    total = 0

    for entry in new_data.values():
        places = entry.get("places")
        place = entry.get("place")
        if places is None or place is None:
            continue
        try:
            diff = int(place) - int(places)
        except (ValueError, TypeError):
            continue
        total += 1
        if diff <= 0:
            passing += 1
        elif diff <= 5:
            almost += 1

    parts = []
    if passing:
        parts.append(f"✅ {passing}")
    if almost:
        parts.append(f"🟡 {almost}")
    not_passing = total - passing - almost
    if not_passing:
        parts.append(f"🔴 {not_passing}")

    if parts:
        return "  │  ".join(parts)
    return ""


def build_report():
    old_data = storage.load()
    new_data = {}

    now = datetime.now(MSK).strftime("%d.%m.%Y %H:%M")
    text = f"📊 <b>Мониторинг поступления</b>\n🕐 {now} МСК\n"

    errors = []
    captcha = None

    builders = [
        ("РЭУ", build_rea_section),
        ("МИСИС", build_misis_section),
        ("МТУСИ", build_mtuci_section),
    ]

    for name, builder in builders:
        try:
            text += "\n" + builder(old_data, new_data)
        except CaptchaRequired as e:
            log.warning("Капча требуется для %s", name)
            text += f"\n🔐 <b>{name}</b>: требуется капча\n\n"
            _keep_previous_source(name, old_data, new_data)
            captcha = e
        except Exception:
            log.exception("Ошибка при получении данных %s", name)
            text += f"\n❌ <b>{name}</b>: ошибка получения данных\n\n"
            _keep_previous_source(name, old_data, new_data)
            errors.append(name)

    summary = build_summary(new_data)
    if summary:
        text = text.replace(
            f"🕐 {now} МСК\n",
            f"🕐 {now} МСК\n{summary}\n",
        )

    if errors:
        log.warning("Ошибки в: %s", ", ".join(errors))

    return text, old_data, new_data, captcha


def _keep_previous_source(source, old_data, new_data):
    """Do not turn a temporary source outage into a fake position change."""
    for key, entry in old_data.items():
        if entry.get("uni") == source and key not in new_data:
            new_data[key] = entry


def main():
    text, old_data, new_data, _ = build_report()

    changed = storage.has_changes(old_data, new_data)

    if changed or FORCE_SEND:
        if not changed:
            log.info("Нет изменений, но FORCE_SEND=true")
        send(text)
        log.info("Сообщение отправлено в Telegram")
    else:
        log.info("Нет изменений — сообщение не отправлено")

    storage.save(new_data)
    log.info("Данные сохранены")


if __name__ == "__main__":
    main()
