import unittest

from crawlers.access_guard import (
    ManualInterventionRequired,
    inspect_response,
)


class AccessGuardTests(unittest.TestCase):
    def test_captcha_body_requires_manual_intervention(self):
        with self.assertRaises(ManualInterventionRequired) as context:
            inspect_response(200, "请完成滑块验证码", platform="zhaopin")

        self.assertEqual(context.exception.status, "paused_manual_intervention")
        self.assertIn("暂停人工处理", str(context.exception))

    def test_login_status_requires_manual_intervention(self):
        with self.assertRaises(ManualInterventionRequired):
            inspect_response(401, "登录后继续", platform="boss")

    def test_rate_limit_status_requires_manual_intervention(self):
        with self.assertRaises(ManualInterventionRequired):
            inspect_response(429, "too many requests", platform="zhaopin")

    def test_rate_limit_text_requires_manual_intervention(self):
        with self.assertRaises(ManualInterventionRequired):
            inspect_response(200, "Too Many Requests", platform="zhaopin")

    def test_normal_response_is_allowed(self):
        inspect_response(200, "<html><div class='joblist-box__item'>职位</div></html>", platform="zhaopin")


if __name__ == "__main__":
    unittest.main()
