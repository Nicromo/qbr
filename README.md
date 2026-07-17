# Admission Monitor

Локальный Telegram-бот, который показывает позиции абитуриента в РЭА, МИСИС и
МТУСИ. Он работает, пока запущен `bot.py`: по команде `/check` и автоматически
раз в шесть часов. Внешний хостинг не требуется.

## Быстрый запуск

1. Установи Python 3.12+ и зависимости:
   ```powershell
   python -m pip install -r requirements.txt
   ```
2. Скопируй `.env.example` в `.env` и укажи `TELEGRAM_BOT_TOKEN`.
   РЭА необязателен: для него добавь `REA_JWT` и `REA_PROFILE`.
3. Запусти бота:
   ```powershell
   python bot.py
   ```
4. Открой своего бота в Telegram и отправь `/start`. Затем `/check` для первой
проверки. Автоуведомления включены по умолчанию.

Если МТУСИ покажет капчу, бот пришлёт её картинкой. Отправь ему текст с
символами, и он передаст ответ в ту же сессию МТУСИ, после чего пришлёт
обновлённую позицию. При неверной капче бот сразу выдаст новую картинку.

`CHECK_INTERVAL=21600` означает 6 часов. Чтобы ботом не мог пользоваться
никто кроме владельца, добавь свой числовой Telegram chat ID в
`ALLOWED_CHAT_IDS`.

Файлы `storage.json` и `subscribers.json` создаются рядом с программой и хранят
последние позиции и настройки подписки.

## Бесплатная работа без сервера на один месяц

Для мгновенных команд и капчи используй Render Free Web Service. Он даёт 750
часов работы на календарный месяц; для одного сервиса этого хватает на месяц.
Рядом Blueprint создаёт бесплатную Postgres-базу, которая хранит позиции,
подписки и сессию капчи. База истекает через 30 дней, поэтому этот вариант
подходит как временный.

1. Подключи GitHub-репозиторий в Render и создай сервис из `render.yaml`.
2. В Render задай `TELEGRAM_BOT_TOKEN`; для РЭА также укажи `REA_JWT` и
   `REA_PROFILE`.
3. После первого деплоя скопируй адрес сервиса вида `https://qbr-bot.onrender.com`
   и создай бесплатный HTTP(s) monitor в UptimeRobot для
   `https://qbr-bot.onrender.com/health` с интервалом 5 минут.

UptimeRobot не даёт сервису простаивать 15 минут, поэтому Telegram-поллинг
остаётся активным: `/check` и ответ на капчу обрабатываются сразу.

## Постоянная работа при выключенном ПК

Для интерактивной капчи нужна постоянно запущенная программа. Бесплатный
вариант - одна VM `e2-micro` в Google Cloud: бесплатный лимит покрывает её
непрерывную работу, 30 ГБ стандартного диска и 1 ГБ исходящего трафика в месяц.
При создании VM выбери одну из зон `us-west1`, `us-central1` или `us-east1`,
тип `e2-micro`, Ubuntu и стандартный диск не больше 30 ГБ. Для регистрации
Google всё равно потребует платёжный профиль, но при этих лимитах списаний нет.
Сначала закоммить и отправь изменения этого проекта в GitHub, чтобы VM получила
версию с обработкой капчи и файлом сервиса.

В SSH-консоли созданной VM выполни:

```bash
sudo apt update
sudo apt install -y git python3-venv
sudo useradd --system --create-home --shell /usr/sbin/nologin qbr
sudo git clone https://github.com/Nicromo/qbr.git /opt/qbr
sudo chown -R qbr:qbr /opt/qbr
sudo -u qbr python3 -m venv /opt/qbr/.venv
sudo -u qbr /opt/qbr/.venv/bin/pip install -r /opt/qbr/requirements.txt
sudo -u qbr cp /opt/qbr/.env.example /opt/qbr/.env
sudo nano /opt/qbr/.env
```

В открытом `.env` заполни `TELEGRAM_BOT_TOKEN`; при необходимости добавь
`REA_JWT` и `REA_PROFILE`. Затем установи сервис:

```bash
sudo cp /opt/qbr/deploy/qbr-bot.service /etc/systemd/system/qbr-bot.service
sudo systemctl daemon-reload
sudo systemctl enable --now qbr-bot
sudo systemctl status qbr-bot
```

После этого бот переживает перезагрузку VM и работает независимо от домашнего
ПК. Логи: `sudo journalctl -u qbr-bot -f`.
