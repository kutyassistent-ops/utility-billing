"""Дымовые тесты приложения: регистрация, вход, страницы.

Запуск из каталога проекта:

    python -m unittest discover -s tests -t . -v
"""

import os
import tempfile
import unittest

# База и секрет подставляются до импорта app: config читает окружение
# на этапе импорта модуля.
_TMP = tempfile.mkdtemp(prefix="billing-test-")
os.environ.setdefault("DB_PATH", os.path.join(_TMP, "test.db"))
os.environ.setdefault("SECRET_KEY", "test-secret-key")

from app import create_app  # noqa: E402


class SmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config.update(TESTING=True)

    def setUp(self):
        self.client = self.app.test_client()

    def test_login_page_opens(self):
        self.assertEqual(self.client.get("/auth/login").status_code, 200)

    def test_register_login_dashboard_stats(self):
        response = self.client.post(
            "/auth/register",
            data={
                "username": "demo-owner",
                "password": "demo-password",
                "role": "owner",
                "full_name": "Demo",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        # регистрация не логинит — входим отдельным запросом
        response = self.client.post(
            "/auth/login",
            data={"username": "demo-owner", "password": "demo-password"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        self.assertEqual(self.client.get("/dashboard").status_code, 200)

        response = self.client.post(
            "/add_property",
            data={"address": "Тестовый адрес, 1"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        # без объектов /stats редиректит на дашборд, с объектом — открывается
        self.assertEqual(self.client.get("/stats").status_code, 200)

    def test_wrong_password_does_not_login(self):
        self.client.post(
            "/auth/register",
            data={
                "username": "demo-tenant",
                "password": "demo-password",
                "role": "owner",
                "full_name": "Demo",
            },
            follow_redirects=True,
        )
        self.client.post(
            "/auth/login",
            data={"username": "demo-tenant", "password": "wrong"},
            follow_redirects=True,
        )
        self.assertEqual(self.client.get("/dashboard").status_code, 302)


if __name__ == "__main__":
    unittest.main()
