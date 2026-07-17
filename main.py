import logging
import re

from misis import get_group_info as get_misis_group
from rea import get_all_my_data, get_group_info
from telegram import send
from mtuci import get_group_info as get_mtuci_group

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("main")


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
    section = "🏛 РЭУ Плеханова\n\n"

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
            f"📚 {group_name}\n"
            f"📍 Место: {row['rating']}\n"
            f"🎯 Приоритет: {row['priority']}\n"
            f"🏅 ИД: {row['achievements_mark']}\n"
            f"📈 Сумма: {row['sum_mark']}\n"
            f"🎓 Мест: {places}\n"
            f"📉 До прохода: {to_pass}\n"
            "━━━━━━━━━━━━━━\n\n"
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
    section = "🏛 МИСИС\n\n"

    for group in MISIS_GROUPS:
        misis = get_misis_group(group["id"])

        if not misis["my"]:
            log.info("МИСИС %s: не найден в списке", group["id"])
            continue

        me = misis["my"]
        log.info("МИСИС %s: место %s", group["id"], me["place"])

        section += (
            f"📚 {misis['direction']} — {group['type']}\n"
            f"📍 Место: {me['place']}\n"
            f"🎯 Приоритет: {me['priority']}\n"
            f"🏅 ИД: {me['id']}\n"
            f"📈 Баллы: {me['scores']}\n"
            f"🎓 Мест: {misis['places']}\n"
            f"📉 До прохода: {me['to_pass']}\n"
            "━━━━━━━━━━━━━━\n\n"
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
    section = "🏛 МТУСИ\n\n"

    result = get_mtuci_group(MTUCI_URL)

    if result["my"]:
        me = result["my"]
        log.info("МТУСИ: место %s", me["place"])

        section += (
            f"📚 {result['direction']}\n"
            f"📍 Место: {me['place']}\n"
            f"🎯 Приоритет: {me['priority']}\n"
            f"🏅 ИД: {me['id']}\n"
            f"📈 Баллы: {me['scores']}\n"
            "━━━━━━━━━━━━━━\n\n"
        )
    else:
        log.warning("МТУСИ: данные не найдены")
        section += "❌ МТУСИ: данные не найдены\n\n"

    return section


def main():
    text = ""
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
            text += f"❌ {name}: ошибка получения данных\n\n"
            errors.append(name)

    if errors:
        log.warning("Ошибки в: %s", ", ".join(errors))

    send(text)
    log.info("Сообщение отправлено в Telegram")


if __name__ == "__main__":
    main()
