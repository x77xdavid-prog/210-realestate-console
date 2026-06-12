import unittest
from unittest import mock

from realestate_alert.models import Listing
from realestate_alert.notifiers import GmailNotifier, build_email_message


def _sample_listing() -> Listing:
    return Listing(
        source="manual",
        external_id="yc-001",
        title="양천구 목동 병원 가능 근린상가",
        location="서울 양천구 목동 917-9",
        deposit=120000000,
        monthly_rent=5400000,
        area_m2=118,
        floor="2층",
        premium=30000000,
        url="https://example.test/listings/yc-001",
    )


class _FakeSmtp:
    def __init__(self):
        self.logged_in = None
        self.sent_messages = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def login(self, user, password):
        self.logged_in = (user, password)

    def send_message(self, message):
        self.sent_messages.append(message)


class GmailNotifierTests(unittest.TestCase):
    def test_sends_email_with_naver_links(self):
        fake = _FakeSmtp()
        notifier = GmailNotifier(
            sender="sender@gmail.com",
            recipients=["doctor@gmail.com"],
            smtp_factory=lambda: fake,
        )
        with mock.patch.dict("os.environ", {"GMAIL_APP_PASSWORD": "app-password"}):
            notifier.notify([_sample_listing()])

        self.assertEqual(fake.logged_in, ("sender@gmail.com", "app-password"))
        self.assertEqual(len(fake.sent_messages), 1)
        message = fake.sent_messages[0]
        self.assertIn("신규 매물 1건", message["Subject"])
        self.assertEqual(message["To"], "doctor@gmail.com")
        html = message.get_payload(1).get_payload(decode=True).decode("utf-8")
        self.assertIn("new.land.naver.com", html)
        self.assertIn("map.naver.com", html)

    def test_skips_sending_without_password_env(self):
        fake = _FakeSmtp()
        notifier = GmailNotifier(
            sender="sender@gmail.com",
            recipients=["doctor@gmail.com"],
            password_env="MISSING_PASSWORD_ENV",
            smtp_factory=lambda: fake,
        )
        with mock.patch.dict("os.environ", {}, clear=True):
            notifier.notify([_sample_listing()])

        self.assertIsNone(fake.logged_in)
        self.assertEqual(fake.sent_messages, [])

    def test_does_nothing_for_empty_listings(self):
        fake = _FakeSmtp()
        notifier = GmailNotifier(
            sender="sender@gmail.com",
            recipients=["doctor@gmail.com"],
            smtp_factory=lambda: fake,
        )
        with mock.patch.dict("os.environ", {"GMAIL_APP_PASSWORD": "app-password"}):
            notifier.notify([])

        self.assertEqual(fake.sent_messages, [])

    def test_build_email_message_has_plain_and_html_parts(self):
        message = build_email_message("sender@gmail.com", ["a@b.c", "d@e.f"], [_sample_listing()])
        self.assertEqual(message["To"], "a@b.c, d@e.f")
        parts = [part.get_content_type() for part in message.get_payload()]
        self.assertEqual(parts, ["text/plain", "text/html"])
