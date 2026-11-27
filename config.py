"""Настройки сайта и необязательной отправки писем."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


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


# Сначала читаем локальный .env, затем берём настройки из окружения сервера.
load_env_file()

# На публичном сервере обязательно замените это значение в файле .env.
SECRET_KEY = os.getenv("SECRET_KEY", "change-this-key-before-public-launch")

# Почтовые параметры можно оставить пустыми для локальной демонстрации.
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
MAIL_FROM = os.getenv("MAIL_FROM", SMTP_USER)
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
