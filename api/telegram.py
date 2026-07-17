import hmac
import os

from flask import Flask, jsonify, request

import bot

app = Flask(__name__)


@app.post("/")
def telegram_webhook():
    expected_secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
    received_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not expected_secret or not hmac.compare_digest(expected_secret, received_secret):
        return jsonify({"ok": False}), 401

    update = request.get_json(silent=True)
    if not update:
        return jsonify({"ok": False, "error": "invalid update"}), 400

    bot.process_update(update)
    return jsonify({"ok": True})
