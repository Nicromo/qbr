"""Persistent JSON state, backed by Render Postgres when DATABASE_URL is set."""

import json
import logging
import os

import psycopg
from psycopg.types.json import Jsonb

log = logging.getLogger("state_store")

DATABASE_URL = os.environ.get("DATABASE_URL", "")


def enabled():
    return bool(DATABASE_URL)


def load(name, fallback):
    if not enabled():
        return fallback

    try:
        with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS bot_state (
                    name TEXT PRIMARY KEY,
                    value JSONB NOT NULL
                )
                """
            )
            row = conn.execute(
                "SELECT value FROM bot_state WHERE name = %s", (name,)
            ).fetchone()
            return row[0] if row else fallback
    except psycopg.Error:
        log.exception("Не удалось загрузить состояние %s из Postgres", name)
        return fallback


def save(name, value):
    if not enabled():
        return False

    try:
        with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS bot_state (
                    name TEXT PRIMARY KEY,
                    value JSONB NOT NULL
                )
                """
            )
            conn.execute(
                """
                INSERT INTO bot_state (name, value) VALUES (%s, %s)
                ON CONFLICT (name) DO UPDATE SET value = EXCLUDED.value
                """,
                (name, Jsonb(value)),
            )
            return True
    except psycopg.Error:
        log.exception("Не удалось сохранить состояние %s в Postgres", name)
        return False
