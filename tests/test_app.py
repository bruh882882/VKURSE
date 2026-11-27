"""Автотесты проекта «В КУРСЕ» на стандартной библиотеке unittest.

Запуск из корня проекта:
    .venv\\Scripts\\python.exe -m unittest discover -s tests -v
"""

import json
import os
import pathlib
import tempfile
import unittest

# Изолируем секретный ключ и хранилище SQLite до импорта приложения.
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests")

import database  # noqa: E402

_TMP_DIR = pathlib.Path(tempfile.mkdtemp(prefix="vkurse_test_"))
database.DATABASE_PATH = _TMP_DIR / "vkurse_test.db"

import app as app_module  # noqa: E402


def make_answers(**overrides):
    """Готовый набор ответов первокурсника-отличника с научными достижениями."""
    answers = {
        "level": "bachelor",
        "mode": "full",
        "funding": "budget",
        "course": "first",
        "citizenship": "russian",
        "grades": "no_session",
        "ege": "270plus",
        "research": "yes",
        "study_awards": "yes",
        "public": "no",
        "sport": "no",
        "fields": ["engineering"],
        "project": "no",
        "social_docs": "no",
        "apo_category": "no",
        "vuc": "no",
        "age": "under35",
    }
    answers.update(overrides)
    return answers


class RouteTests(unittest.TestCase):
    def setUp(self):
        app_module.app.config["TESTING"] = True
        self.client = app_module.app.test_client()

    def get_csrf(self):
        self.client.get("/")
        with self.client.session_transaction() as sess:
            return sess.get("csrf_token", "")

    def post(self, url, data):
        data = dict(data)
        data["csrf_token"] = self.get_csrf()
        return self.client.post(url, data=data, follow_redirects=False)

    def test_home_page(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Стипендии и поддержка", resp.get_data(as_text=True))

    def test_catalog_page(self):
        resp = self.client.get("/catalog")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Справочник", resp.get_data(as_text=True))

    def test_sources_page(self):
        resp = self.client.get("/sources")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Источники данных", resp.get_data(as_text=True))

    def test_quiz_page(self):
        resp = self.client.get("/quiz")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Ответьте на вопросы", resp.get_data(as_text=True))

    def test_404_page(self):
        resp = self.client.get("/neponyatnyi-adres")
        self.assertEqual(resp.status_code, 404)

    def test_catalog_multiword_search(self):
        resp = self.client.get("/catalog?q=стипендия+москвы")
        self.assertIn("Именная стипендия Правительства Москвы", resp.get_data(as_text=True))

    def test_catalog_keyword_search(self):
        resp = self.client.get("/catalog?q=карта+мир")
        self.assertIn("АПОС", resp.get_data(as_text=True))

    def test_catalog_kind_filter(self):
        text = self.client.get("/catalog?kind=grant").get_data(as_text=True)
        self.assertIn("Студенческий стартап", text)
        self.assertNotIn("Государственная академическая стипендия", text)

    def test_catalog_invalid_filter_falls_back(self):
        resp = self.client.get("/catalog?kind=unknown&status=unknown")
        self.assertEqual(resp.status_code, 200)


class QuizFlowTests(RouteTests):
    def test_missing_required_reports_error(self):
        resp = self.post("/quiz/result", {"level": "bachelor"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Заполните обязательные вопросы", resp.get_data(as_text=True))

    def test_invalid_option_rejected(self):
        resp = self.post("/quiz/result", {"level": "hacker"})
        self.assertEqual(resp.status_code, 400)

    def test_answers_preserved_on_error(self):
        resp = self.post("/quiz/result", {"level": "bachelor", "mode": "full"})
        self.assertEqual(resp.status_code, 400)
        html = resp.get_data(as_text=True)
        self.assertIn('value="bachelor"', html)
        self.assertIn("checked", html)

    def test_csrf_protection(self):
        resp = self.client.post(
            "/subscribe", data={"email": "a@b.ru", "consent": "yes"}
        )
        self.assertEqual(resp.status_code, 302)

    def test_full_quiz_returns_result(self):
        answers = make_answers()
        answers["fields"] = ["engineering", "space"]
        resp = self.post("/quiz/result", answers)
        self.assertEqual(resp.status_code, 200)
        text = resp.get_data(as_text=True)
        self.assertIn("Государственная академическая стипендия", text)

class RecommendationTests(unittest.TestCase):
    def setUp(self):
        self.programs = app_module.get_all_programs()
        self.questions = app_module.read_json("questions.json")

    def recommend(self, **overrides):
        return app_module.make_recommendations(
            self.programs, self.questions, make_answers(**overrides)
        )

    def ids(self, results):
        return [p["id"] for p in results]

    def test_freshman_top_bracket_gets_gas_and_rector(self):
        ids = self.ids(self.recommend())
        self.assertIn("S-01", ids)
        self.assertIn("S-02", ids)

    def test_rector_requires_high_ege(self):
        ids = self.ids(self.recommend(ege="under200"))
        self.assertIn("S-01", ids)
        self.assertNotIn("S-02", ids)

    def test_gas_excluded_for_debt(self):
        ids = self.ids(self.recommend(grades="satisfactory"))
        self.assertNotIn("S-01", ids)

    def test_historical_not_recommended(self):
        ids = self.ids(self.recommend(
            course="third", grades="excellent", fields=["electronics"]
        ))
        self.assertNotIn("S-14", ids)

    def test_pgas_reasons_no_false_negative_label(self):
        results = self.recommend(
            grades="excellent",
            research="no",
            study_awards="no",
            public="no",
            sport="yes",
        )
        pgas = next((p for p in results if p["id"] == "S-03"), None)
        self.assertIsNotNone(pgas)
        joined = " · ".join(pgas["match_reasons"])
        self.assertIn("Спортивные достижения", joined)
        self.assertNotIn("Пока нет", joined)

    def test_gaidar_matches_economics(self):
        ids = self.ids(self.recommend(
            fields=["economics"], grades="excellent", research="yes"
        ))
        self.assertIn("S-18", ids)

    def test_grant_systema_needs_project(self):
        ids = self.ids(self.recommend(project="yes"))
        self.assertIn("G-01", ids)


class DatabaseTests(unittest.TestCase):
    def tearDown(self):
        database.create_tables()
        conn = database.get_connection()
        try:
            conn.execute("DELETE FROM subscribers")
            conn.execute("DELETE FROM consultations")
            conn.commit()
        finally:
            conn.close()

    def test_save_subscriber_and_duplicate(self):
        self.assertTrue(database.save_subscriber("student@mail.ru"))
        self.assertFalse(database.save_subscriber("student@mail.ru"))
        self.assertEqual(len(database.get_subscribers()), 1)

    def test_save_consultation_and_duplicate_guard(self):
        text = "Добрый день, нужна помощь с ПГАС."
        self.assertTrue(database.save_consultation("Ivan", "i@m.ru", text))
        self.assertFalse(database.save_consultation("Ivan", "i@m.ru", text))
        self.assertEqual(len(database.get_consultations()), 1)


class JsonDataTests(unittest.TestCase):
    BASE = pathlib.Path(__file__).resolve().parent.parent

    def test_all_question_keys_used(self):
        used = set()
        for program in app_module.get_all_programs():
            rule = program.get("match") or {}
            for cond in rule.get("all", []) + rule.get("any", []):
                used.add(cond["field"])
        questions = app_module.read_json("questions.json")
        keys = {q["key"] for q in questions}
        self.assertTrue(keys.issubset(used), f"Неиспользуемые ключи: {keys - used}")

    def test_data_summary_counts(self):
        with open(self.BASE / "DATA_SUMMARY.json", encoding="utf-8") as f:
            summary = json.load(f)
        self.assertEqual(len(app_module.read_json("scholarships.json")), summary["scholarships"])
        self.assertEqual(len(app_module.read_json("support.json")), summary["support"])
        self.assertEqual(len(app_module.read_json("grants.json")), summary["grants"])
        self.assertEqual(len(app_module.read_json("questions.json")), summary["questions"])

    def test_sources_json_consistent(self):
        sources = app_module.read_json("sources.json")
        self.assertIsInstance(sources, dict)
        self.assertGreater(len(sources), 0)


if __name__ == "__main__":
    unittest.main()