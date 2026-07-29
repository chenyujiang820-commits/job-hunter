import os
import unittest
from unittest.mock import patch


class AppHealthTests(unittest.TestCase):
    def test_health_route_reports_status_without_exposing_settings(self):
        from fastapi.testclient import TestClient

        from server.app import create_app

        app = create_app()
        response = TestClient(app).get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertNotIn("SECRET", response.text)

    def test_settings_load_from_environment_without_echoing_secret(self):
        from server.settings import Settings

        with patch.dict(
            os.environ,
            {
                "DATABASE_URL": "sqlite:///./test.db",
                "S3_ENDPOINT": "http://localhost:9000",
                "S3_BUCKET": "job-hunter",
                "DEFAULT_MODEL_KEY": "SECRET-MODEL-KEY",
            },
            clear=False,
        ):
            settings = Settings()

        self.assertEqual(settings.database_url, "sqlite:///./test.db")
        self.assertEqual(settings.s3_endpoint, "http://localhost:9000")
        self.assertEqual(settings.s3_bucket, "job-hunter")
        self.assertEqual(settings.default_model_key, "SECRET-MODEL-KEY")


if __name__ == "__main__":
    unittest.main()
