"""Главный файл сайта «В КУРСЕ».

Здесь находятся адреса страниц и обработка пользовательских форм.
Сам подбор выплат находится в recommendations.py, а работа с SQLite —
в database.py. Так каждому блоку проще найти своё место и объяснить его.
"""

import json
import os
import re
import secrets
import smtplib
from email.message import EmailMessage
from pathlib import Path

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

import config
from database import create_tables, save_consultation, save_subscriber
from recommendations import make_recommendations

# Папки проекта. Все JSON-файлы с данными лежат внутри data/.
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

# Создаём Flask-приложение.
app = Flask(__name__)
app.secret_key = config.SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024  # Ограничение размера формы: 1 МБ.

# Подписи, которые видит студент вместо коротких кодов из JSON.
STATUS_LABELS = {
    "open": "Приём открыт",
    "review": "Идёт отбор",
    "regular": "Постоянная выплата",
    "seasonal": "По конкурсу",
    "closed": "Приём завершён",
    "check": "Нужно уточнить",
    "historical": "Архивная информация",
}

KIND_LABELS = {
    "scholarship": "Стипендия",
    "support": "Материальная помощь",
    "grant": "Грант или конкурс",
}


def read_json(filename):
    """Открывает JSON-файл и возвращает данные из него."""
    path = DATA_DIR / filename
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def get_all_programs():
    """Собирает три раздела базы в один список для каталога и теста."""
    programs = []
    for filename in ("scholarships.json", "support.json", "grants.json"):
        programs.extend(read_json(filename))
    return programs


def check_csrf_token():
    """Проверяет, что форма отправлена со страницы, открытой в этой сессии."""
    sent_token = request.form.get("csrf_token", "")
    saved_token = session.get("csrf_token", "")
    return bool(
        sent_token
        and saved_token
        and secrets.compare_digest(sent_token, saved_token)
    )


def valid_email(email):
    """Проверяет базовый формат адреса электронной почты."""
    pattern = r"[^\s@]+@[^\s@]+\.[^\s@]+"
    return bool(re.fullmatch(pattern, email or ""))


def send_admin_notification(subject, text):
    """Отправляет команде письмо, если в .env настроен SMTP.

    Почтовые настройки необязательны: даже без них подписка или обращение
    сохраняются в SQLite. SMTP нужен только для уведомления команды.
    """
    required_settings = [
        config.SMTP_HOST,
        config.SMTP_USER,
        config.SMTP_PASSWORD,
        config.MAIL_FROM,
        config.ADMIN_EMAIL,
    ]
    if not all(required_settings):
        return False

    email = EmailMessage()
    email["Subject"] = subject
    email["From"] = config.MAIL_FROM
    email["To"] = config.ADMIN_EMAIL
    email.set_content(text)

    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=10) as server:
            if config.SMTP_USE_TLS:
                server.starttls()
            server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.send_message(email)
        return True
    except (OSError, smtplib.SMTPException):
        # Ошибка почты не должна удалять уже сохранённую заявку.
        return False


@app.before_request
def prepare_form_token():
    """Создаёт защитный токен для форм при первом открытии страницы."""
    session.setdefault("csrf_token", secrets.token_hex(24))


@app.context_processor
def add_common_values():
    """Передаёт общие подписи и токен во все HTML-шаблоны."""
    return {
        "csrf_token": session.get("csrf_token", ""),
        "status_labels": STATUS_LABELS,
        "kind_labels": KIND_LABELS,
    }


@app.get("/")
def home():
    """Показывает главную страницу и несколько конкурсов с открытым приёмом."""
    open_programs = [
        item for item in get_all_programs() if item.get("status") == "open"
    ]
    return render_template("home.html", featured=open_programs[:3])


@app.get("/catalog")
def catalog():
    """Показывает базу и применяет поиск и фильтры."""
    programs = get_all_programs()
    query = request.args.get("q", "").strip().lower()
    kind = request.args.get("kind", "all")
    status = request.args.get("status", "all")

    filtered_programs = []
    for program in programs:
        # Ищем по названию, сумме, кому подходит и основным условиям.
        searchable_text = " ".join(
            [
                program.get("title", ""),
                program.get("amount", ""),
                program.get("eligibility", ""),
                " ".join(program.get("conditions", [])),
            ]
        ).lower()

        if query and query not in searchable_text:
            continue
        if kind != "all" and program.get("kind") != kind:
            continue
        if status != "all" and program.get("status") != status:
            continue

        filtered_programs.append(program)

    # В начале списка — возможности с ближайшим сроком или действующим статусом.
    status_order = {
        "open": 0,
        "review": 1,
        "regular": 2,
        "seasonal": 3,
        "check": 4,
        "closed": 5,
        "historical": 6,
    }
    filtered_programs.sort(
        key=lambda item: status_order.get(item.get("status"), 7)
    )

    return render_template(
        "catalog.html",
        programs=filtered_programs,
        query=query,
        selected_kind=kind,
        selected_status=status,
    )


@app.get("/quiz")
def quiz():
    """Показывает вопросы для предварительного подбора программ."""
    questions = read_json("questions.json")
    return render_template("quiz.html", questions=questions, errors=[])


@app.post("/quiz/result")
def quiz_result():
    """Получает ответы и показывает программы, которые подходят по правилам."""
    if not check_csrf_token():
        return (
            render_template(
                "message.html",
                title="Форма устарела",
                message="Обновите страницу и отправьте ответы ещё раз.",
                back_url=url_for("quiz"),
            ),
            400,
        )

    questions = read_json("questions.json")
    answers = {}
    errors = []

    # Собираем ответы по ключам, указанным в questions.json.
    for question in questions:
        key = question["key"]
        if question["type"] == "multi":
            answer = request.form.getlist(key)
        else:
            answer = request.form.get(key, "").strip()

        # Проверяем обязательные вопросы.
        if question.get("required", True) and not answer:
            errors.append(question["title"])

        # Не принимаем значения, которых нет среди вариантов ответа.
        allowed_values = {option["value"] for option in question["options"]}
        submitted_values = answer if isinstance(answer, list) else [answer]
        if any(value and value not in allowed_values for value in submitted_values):
            errors.append(question["title"])

        answers[key] = answer

    if errors:
        # Возвращаем форму с перечнем вопросов, которые нужно проверить.
        return render_template(
            "quiz.html", questions=questions, errors=list(dict.fromkeys(errors))
        ), 400

    # Ответы используются только для расчёта и не записываются в базу.
    recommendations = make_recommendations(
        get_all_programs(), questions, answers
    )
    return render_template("result.html", programs=recommendations)


@app.post("/subscribe")
def subscribe():
    """Добавляет email в список желающих получать обновления."""
    if not check_csrf_token():
        flash("Обновите страницу и попробуйте ещё раз.", "error")
        return redirect(url_for("home") + "#subscribe")

    email = request.form.get("email", "").strip().lower()
    consent = request.form.get("consent")

    if not valid_email(email):
        flash("Проверьте адрес электронной почты.", "error")
    elif consent != "yes":
        flash("Подтвердите согласие на обработку адреса.", "error")
    else:
        added = save_subscriber(email)
        if not added:
            flash("Этот адрес уже есть в списке подписчиков.", "info")
        else:
            sent = send_admin_notification(
                "Новая подписка — В КУРСЕ",
                f"Новый адрес подписчика: {email}",
            )
            if sent:
                flash("Подписка сохранена. Команда получила уведомление.", "success")
            else:
                flash("Подписка сохранена. Спасибо!", "success")

    return redirect(url_for("home") + "#subscribe")


@app.post("/consultation")
def consultation():
    """Сохраняет вопрос студента и уведомляет команду, если настроена почта."""
    if not check_csrf_token():
        flash("Обновите страницу и попробуйте ещё раз.", "error")
        return redirect(url_for("home") + "#consultation")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    message = request.form.get("message", "").strip()
    consent = request.form.get("consent")

    if len(name) < 2 or len(name) > 60:
        flash("Укажите имя длиной от 2 до 60 символов.", "error")
    elif not valid_email(email):
        flash("Проверьте адрес электронной почты.", "error")
    elif len(message) < 10 or len(message) > 3000:
        flash("Вопрос должен содержать от 10 до 3 000 символов.", "error")
    elif consent != "yes":
        flash("Подтвердите согласие на обработку данных обращения.", "error")
    else:
        save_consultation(name, email, message)
        notification_text = (
            f"Имя: {name}\n"
            f"Почта: {email}\n\n"
            f"Вопрос:\n{message}"
        )
        sent = send_admin_notification(
            "Новое обращение — В КУРСЕ", notification_text
        )
        if sent:
            flash("Обращение сохранено. Команда получила уведомление.", "success")
        else:
            flash("Обращение сохранено. Спасибо за обращение.", "success")

    return redirect(url_for("home") + "#consultation")


@app.errorhandler(404)
def page_not_found(_error):
    """Показывает понятное сообщение, если страница не найдена."""
    return (
        render_template(
            "message.html",
            title="Страница не найдена",
            message="Такой страницы нет. Вернитесь на главную.",
            back_url=url_for("home"),
        ),
        404,
    )


# Создаём таблицы SQLite, если их ещё нет.
# Это также срабатывает при подключении приложения через WSGI-сервер.
create_tables()


if __name__ == "__main__":
    # Локальный сервер для разработки и демонстрации проекта.
    # Для постоянного публичного запуска используйте сервер, рекомендованный хостингом.
    host = "0.0.0.0"
    port = int(os.environ.get("PORT", "5000"))
    app.run(host=host, port=port, debug=False)
