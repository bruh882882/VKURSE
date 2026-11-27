"""Сохранение подписок и обращений в простую базу SQLite."""

import sqlite3
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "instance" / "vkurse.db"


def get_connection():
    """Открывает SQLite-файл и возвращает соединение с ним."""
    # Папка instance создаётся автоматически при первом запуске.
    DATABASE_PATH.parent.mkdir(exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def create_tables():
    """Создаёт таблицы подписчиков и обращений, если их ещё нет."""
    connection = get_connection()
    try:
        # IF NOT EXISTS не даёт создать одну и ту же таблицу повторно.
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS subscribers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS consultations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.commit()
    finally:
        connection.close()


def save_subscriber(email):
    """Сохраняет email. Возвращает False, если адрес уже подписан."""
    connection = get_connection()
    try:
        connection.execute(
            "INSERT INTO subscribers (email, created_at) VALUES (?, ?)",
            (email.strip().lower(), datetime.now().isoformat(timespec="seconds")),
        )
        connection.commit()
        return True
    except sqlite3.IntegrityError:
        # У email есть ограничение UNIQUE: повторная подписка не создаётся.
        connection.rollback()
        return False
    finally:
        connection.close()


def save_consultation(name, email, message):
    """Сохраняет обращение студента в отдельную таблицу."""
    connection = get_connection()
    try:
        connection.execute(
            """
            INSERT INTO consultations (name, email, message, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                name.strip(),
                email.strip().lower(),
                message.strip(),
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        connection.commit()
    finally:
        connection.close()
