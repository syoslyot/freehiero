from unittest.mock import MagicMock, patch

import pytest

import config
from models import Notification
from notifier import (
    GmailNotifier,
    LineNotifier,
    TelegramNotifier,
    build_notifiers,
)

SAMPLE_NOTIFICATION = Notification(
    title="社團通知",
    body="免費便當，快來拿！工程館一樓\nhttps://www.facebook.com/groups/123/posts/99",
)


class TestTelegramNotifier:
    def test_send_calls_api(self):
        with patch("notifier.httpx.post") as mock_post, \
             patch.object(config, "TELEGRAM_BOT_TOKEN", "tok"), \
             patch.object(config, "TELEGRAM_CHAT_ID", "chat"):
            mock_post.return_value = MagicMock(raise_for_status=lambda: None)
            TelegramNotifier().send(SAMPLE_NOTIFICATION)
            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args
            assert "tok" in call_kwargs.args[0]          # URL contains token
            assert "chat" in str(call_kwargs.kwargs)     # body contains chat_id

    def test_send_raises_on_http_error(self):
        with patch("notifier.httpx.post") as mock_post, \
             patch.object(config, "TELEGRAM_BOT_TOKEN", "tok"), \
             patch.object(config, "TELEGRAM_CHAT_ID", "chat"):
            mock_resp = MagicMock()
            mock_resp.raise_for_status.side_effect = Exception("HTTP 401")
            mock_post.return_value = mock_resp
            with pytest.raises(Exception, match="HTTP 401"):
                TelegramNotifier().send(SAMPLE_NOTIFICATION)


class TestGmailNotifier:
    def test_send_calls_smtp(self):
        with patch("notifier.smtplib.SMTP_SSL") as mock_smtp_cls, \
             patch.object(config, "GMAIL_SENDER", "a@gmail.com"), \
             patch.object(config, "GMAIL_APP_PASSWORD", "pw"), \
             patch.object(config, "GMAIL_RECIPIENT", "b@gmail.com"):
            mock_smtp = MagicMock()
            mock_smtp_cls.return_value.__enter__ = lambda s: mock_smtp
            mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
            GmailNotifier().send(SAMPLE_NOTIFICATION)
            mock_smtp.login.assert_called_once_with("a@gmail.com", "pw")
            mock_smtp.send_message.assert_called_once()


class TestLineNotifier:
    def test_send_calls_api(self):
        with patch("notifier.httpx.post") as mock_post, \
             patch.object(config, "LINE_CHANNEL_ACCESS_TOKEN", "token"), \
             patch.object(config, "LINE_USER_ID", "U123"):
            mock_post.return_value = MagicMock(raise_for_status=lambda: None)
            LineNotifier().send(SAMPLE_NOTIFICATION)
            mock_post.assert_called_once()
            assert "U123" in str(mock_post.call_args.kwargs)


class TestBuildNotifiers:
    def test_returns_telegram(self):
        with patch.object(config, "ENABLED_NOTIFIERS", ["telegram"]):
            notifiers = build_notifiers()
            assert len(notifiers) == 1
            assert isinstance(notifiers[0], TelegramNotifier)

    def test_returns_multiple(self):
        with patch.object(config, "ENABLED_NOTIFIERS", ["telegram", "gmail"]):
            notifiers = build_notifiers()
            assert len(notifiers) == 2

    def test_unknown_notifier_skipped(self):
        with patch.object(config, "ENABLED_NOTIFIERS", ["telegram", "unknown"]):
            notifiers = build_notifiers()
            assert len(notifiers) == 1

    def test_empty_returns_empty(self):
        with patch.object(config, "ENABLED_NOTIFIERS", []):
            assert build_notifiers() == []
