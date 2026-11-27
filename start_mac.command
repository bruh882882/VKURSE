#!/bin/bash
# Перейти в папку, где лежит этот файл.
cd "$(dirname "$0")"

# Создать отдельное окружение при первом запуске.
if [ ! -x ".venv/bin/python" ]; then
  python3 -m venv .venv
fi

# Установить Flask и запустить сайт.
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py
