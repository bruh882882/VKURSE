"""Настройки сайта и необязательной отправки писем."""

import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SECRET_FILE_PATH = BASE_DIR / "instance" / ".secret_key"
PLACEHOLDER_KEYS = {
    "",
    "change-this-key-before-public-launch",
    "replace-with-a-long-random-key",
}


def load_env_file():
    """Читает пары ИМЯ=ЗНАЧЕНИЕ из файла .env без дополнительных библиотек."""
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))


def get_secret_key():
    """Возвращает SECRET_KEY из окружения или создаёт локальный ключ в instance/."""
    configured_key = os.getenv("SECRET_KEY", "").strip()
    if configured_key not in PLACEHOLDER_KEYS:
        return configured_key

    try:
        SECRET_FILE_PATH.parent.mkdir(exist_ok=True)
        if SECRET_FILE_PATH.exists():
            saved_key = SECRET_FILE_PATH.read_text(encoding="utf-8").strip()
            if saved_key:
                return saved_key

        generated_key = secrets.token_hex(32)
        SECRET_FILE_PATH.write_text(generated_key, encoding="utf-8")
        return generated_key
    except OSError:
        return secrets.token_hex(32)


def get_int_env(name, default):
    """Безопасно преобразует числовую переменную окружения."""
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


# Сначала читаем локальный .env, затем берём настройки из окружения сервера.
load_env_file()

SECRET_KEY = get_secret_key()

# Почтовые параметры можно оставить пустыми для локальной демонстрации.
SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = get_int_env("SMTP_PORT", 587)
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").strip()
MAIL_FROM = os.getenv("MAIL_FROM", "").strip() or SMTP_USER
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "").strip()
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").strip().lower() == "true"

