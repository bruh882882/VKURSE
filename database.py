"""Сохранение и чтение подписок и обращений в простую базу SQLite."""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "instance" / "vkurse.db"


def get_connection():
    """Открывает SQLite-файл и возвращает соединение с ним."""
    # Папка instance создаётся автоматически при первом запуске.
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
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
    """Сохраняет обращение студента. Возвращает False при повторной отправке подряд."""
    normalized_name = name.strip()
    normalized_email = email.strip().lower()
    normalized_message = message.strip()
    now = datetime.now()
    recent_cutoff = (now - timedelta(minutes=5)).isoformat(timespec="seconds")

    connection = get_connection()
    try:
        duplicate = connection.execute(
            """
            SELECT id FROM consultations
            WHERE email = ? AND message = ? AND created_at >= ?
            LIMIT 1
            """,
            (normalized_email, normalized_message, recent_cutoff),
        ).fetchone()
        if duplicate is not None:
            return False

        connection.execute(
            """
            INSERT INTO consultations (name, email, message, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                normalized_name,
                normalized_email,
                normalized_message,
                now.isoformat(timespec="seconds"),
            ),
        )
        connection.commit()
        return True
    finally:
        connection.close()


def get_subscribers():
    """Возвращает список всех подписчиков от новых к старым."""
    connection = get_connection()
    try:
        rows = connection.execute(
            "SELECT id, email, created_at FROM subscribers ORDER BY id DESC"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def get_consultations():
    """Возвращает список всех обращений от новых к старым."""
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT id, name, email, message, created_at
            FROM consultations
            ORDER BY id DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


if __name__ == "__main__":
    # Удобный просмотр заявок из терминала, если не настроен SMTP: python database.py
    create_tables()
    subscribers = get_subscribers()
    consultations = get_consultations()
    print(f"Подписчиков в базе: {len(subscribers)}")
    for item in subscribers[:20]:
        print(f"  [{item['created_at']}] {item['email']}")
    print(f"\nОбращений в базе: {len(consultations)}")
    for item in consultations[:20]:
        print(f"  [{item['created_at']}] {item['name']} <{item['email']}>: {item['message']}")

