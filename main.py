import logging
import re
from datetime import datetime, timezone, timedelta

from misis import get_group_info as get_misis_group
from rea import get_all_my_data, get_group_info
from telegram import send
from mtuci import get_group_info as get_mtuci_group

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("main")

MSK = timezone(timedelta(hours=3))


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


def build_rea_section():
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

        section += (
            f"📚 <b>{esc(group_name)}</b>\n"
            f"   Место: <code>{row['rating']}</code>  │  "
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


def build_misis_section():
    section = "<b>🏛 МИСИС</b>\n\n"

    for group in MISIS_GROUPS:
        misis = get_misis_group(group["id"])

        if not misis["my"]:
            log.info("МИСИС %s: не найден в списке", group["id"])
            continue

        me = misis["my"]
        log.info("МИСИС %s: место %s", group["id"], me["place"])

        badge = "🆓" if group["type"] == "Бюджет" else "💰"

        section += (
            f"📚 <b>{esc(misis['direction'])}</b>  {badge} {esc(group['type'])}\n"
            f"   Место: <code>{me['place']}</code>  │  "
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


def build_mtuci_section():
    section = "<b>🏛 МТУСИ</b>\n\n"

    result = get_mtuci_group(MTUCI_URL)

    if result["my"]:
        me = result["my"]
        log.info("МТУСИ: место %s", me["place"])

        section += (
            f"📚 <b>{esc(result['direction'])}</b>\n"
            f"   Место: <code>{me['place']}</code>\n"
            f"   Приоритет: <code>{me['priority']}</code>  │  "
            f"ИД: <code>{me['id']}</code>\n"
            f"   Баллы: <code>{me['scores']}</code>\n\n"
        )
    else:
        log.warning("МТУСИ: данные не найдены")
        section += "❌ Данные не найдены\n\n"

    return section


def main():
    now = datetime.now(MSK).strftime("%d.%m.%Y %H:%M")
    text = f"📊 <b>Мониторинг поступления</b>\n🕐 {now} МСК\n\n"

    errors = []

    builders = [
        ("РЭУ", build_rea_section),
        ("МИСИС", build_misis_section),
        ("МТУСИ", build_mtuci_section),
    ]

    for name, builder in builders:
        try:
            text += builder()
        except Exception:
            log.exception("Ошибка при получении данных %s", name)
            text += f"❌ <b>{name}</b>: ошибка получения данных\n\n"
            errors.append(name)

    if errors:
        log.warning("Ошибки в: %s", ", ".join(errors))

    send(text)
    log.info("Сообщение отправлено в Telegram")


if __name__ == "__main__":
    main()
