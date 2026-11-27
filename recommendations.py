"""Простой алгоритм подбора стипендий и других программ."""


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

        # Добавляем ответы, которые совпали с обязательными условиями.
        conditions = rule.get("all", []) + rule.get("any", [])
        for condition in conditions:
            field = condition["field"]
            answer = answers.get(field)
            labels = answer_labels.get(field, {})

            if isinstance(answer, list):
                matched_values = [
                    labels.get(value, value)
                    for value in answer
                    if value in condition["in"]
                ]
                reason = ", ".join(matched_values)
            else:
                reason = labels.get(answer, answer or "")

            if reason and reason not in matched_reasons:
                matched_reasons.append(reason)

        # Не меняем исходную запись в JSON — создаём отдельную копию для страницы.
        result = dict(program)
        result["match_reasons"] = matched_reasons[:4]
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
