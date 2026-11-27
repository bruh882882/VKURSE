"""Простой алгоритм подбора стипендий и других программ."""

# Понятные подписи для коротких ответов «Да», чтобы в карточке результата
# было видно конкретное совпавшее основание, а не просто слово «Да».
SPECIFIC_REASON_LABELS = {
    ("public", "yes"): "Общественная или культурно-творческая деятельность",
    ("sport", "yes"): "Спортивные достижения",
    ("social_docs", "yes"): "Подтверждённое социальное основание",
    ("apo_category", "yes"): "Категория программы АПОС",
    ("vuc", "yes"): "Договор с ВУЦ МАИ",
    ("age", "under35"): "Возраст до 35 лет",
}

GAS_EGE_RATES = {
    "under200": "3 000 ₽/мес.",
    "200_249": "4 000 ₽/мес.",
    "250_269": "8 000 ₽/мес.",
    "270plus": "12 000 ₽/мес.",
}


def condition_is_true(condition, answers):
    """Проверяет, совпал ли один ответ с условием из JSON.

    Например, условие может требовать, чтобы форма обучения была очной.
    Для вопроса с несколькими вариантами достаточно одного совпадения.
    """
    field = condition["field"]
    allowed_values = condition["in"]
    answer = answers.get(field)

    if isinstance(answer, list):
        return any(value in allowed_values for value in answer)

    return answer in allowed_values


def program_matches(program, answers):
    """Проверяет, подходит ли программа по ответам студента.

    В JSON используются два списка условий:
    - all: должны совпасть все условия;
    - any: достаточно одного совпавшего условия.

    Архивные записи не попадают в рекомендации, но остаются в каталоге.
    """
    if program.get("status") == "historical":
        return False

    rule = program.get("match")
    if not rule:
        # Если правила нет, мы не угадываем подходящую категорию.
        return False

    required_conditions = rule.get("all", [])
    optional_conditions = rule.get("any", [])

    if not all(condition_is_true(item, answers) for item in required_conditions):
        return False

    if optional_conditions and not any(
        condition_is_true(item, answers) for item in optional_conditions
    ):
        return False

    return True


def build_personal_hint(program, answers):
    """Формирует уточняющую подсказку по размеру выплаты, если её можно определить по ответам."""
    if program.get("id") != "S-01":
        return ""

    level = answers.get("level")
    course = answers.get("course")
    grades = answers.get("grades")
    ege = answers.get("ege")

    if level == "specialized":
        return "Для специализированного высшего образования ориентир в навигаторе МАИ — 5 000 ₽/мес."

    if course == "first" and grades == "no_session" and ege in GAS_EGE_RATES:
        return (
            f"Ориентир ГАС для первокурсника с вашими баллами до первой сессии — "
            f"{GAS_EGE_RATES[ege]} (по навигатору МАИ 2026/27)."
        )

    if grades == "excellent":
        return "Ориентир ГАС после сессии на «отлично» — 12 500 ₽/мес. (для бакалавриата и специалитета)."
    if grades == "good":
        return "Ориентир ГАС после сессии на «хорошо» и «отлично» — 7 500 ₽/мес. (для бакалавриата и специалитета)."

    return ""


def make_recommendations(programs, questions, answers):
    """Находит подходящие программы и объясняет совпадения."""
    # Переводим технические коды ответов в понятные подписи.
    answer_labels = {}
    for question in questions:
        answer_labels[question["key"]] = {
            option["value"]: option["label"]
            for option in question["options"]
        }

    results = []
    for program in programs:
        if not program_matches(program, answers):
            continue

        rule = program.get("match", {})
        matched_reasons = []

        # Учитываем только реально совпавшие условия (важно для блока any).
        conditions = rule.get("all", []) + rule.get("any", [])
        for condition in conditions:
            if not condition_is_true(condition, answers):
                continue

            field = condition["field"]
            answer = answers.get(field)
            labels = answer_labels.get(field, {})

            if isinstance(answer, list):
                matched_values = [
                    SPECIFIC_REASON_LABELS.get((field, value), labels.get(value, value))
                    for value in answer
                    if value in condition["in"]
                ]
                reason = ", ".join(matched_values)
            else:
                reason = SPECIFIC_REASON_LABELS.get(
                    (field, answer), labels.get(answer, answer or "")
                )

            if reason and reason not in matched_reasons:
                matched_reasons.append(reason)

        # Для ГАС первокурсника дополняем причины выбранным диапазоном баллов ЕГЭ.
        if (
            program.get("id") == "S-01"
            and answers.get("course") == "first"
            and answers.get("ege") in GAS_EGE_RATES
        ):
            ege_label = answer_labels.get("ege", {}).get(answers["ege"], "")
            if ege_label:
                ege_reason = f"Баллы ЕГЭ: {ege_label}"
                if ege_reason not in matched_reasons:
                    matched_reasons.append(ege_reason)

        # Не меняем исходную запись в JSON — создаём отдельную копию для страницы.
        result = dict(program)
        result["match_reasons"] = matched_reasons[:5]
        personal_hint = build_personal_hint(program, answers)
        if personal_hint:
            result["personal_hint"] = personal_hint
        results.append(result)

    # Сначала показываем доступные сейчас программы, затем остальные.
    priority = {
        "open": 0,
        "review": 1,
        "regular": 2,
        "seasonal": 3,
        "check": 4,
        "closed": 5,
    }
    results.sort(key=lambda item: priority.get(item.get("status"), 6))
    return results

