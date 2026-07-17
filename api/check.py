import hmac
import os
import time

from flask import Flask, jsonify, request

import bot
import state_store

app = Flask(__name__)


@app.get("/")
def scheduled_check():
    expected_secret = os.environ.get("CHECK_SECRET", "")
    received_secret = request.args.get("token", "")
    if not expected_secret or not hmac.compare_digest(expected_secret, received_secret):
        return jsonify({"ok": False}), 401

    runtime = state_store.load("runtime", {})
    now = time.time()
    if now - runtime.get("last_auto_check", 0) < bot.CHECK_INTERVAL:
        return jsonify({"ok": True, "checked": False})

    if bot.auto_check_once():
        runtime["last_auto_check"] = now
        state_store.save("runtime", runtime)
        return jsonify({"ok": True, "checked": True})
    return jsonify({"ok": False, "checked": False}), 502
