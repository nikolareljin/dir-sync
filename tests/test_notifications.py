from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

from dirsync.notifications import NotificationPayload, Notifier


class TestNotificationPayload:
    def test_defaults(self):
        payload = NotificationPayload(title="Test", message="Hello")
        assert payload.app_name == "Dir Sync"

    def test_custom_app_name(self):
        payload = NotificationPayload(title="T", message="M", app_name="Custom")
        assert payload.app_name == "Custom"


class TestNotifier:
    def test_success_logs_message(self, caplog):
        notifier = Notifier()
        with caplog.at_level(logging.INFO):
            notifier.success("job done")
        assert "job done" in caplog.text

    def test_error_logs_message(self, caplog):
        notifier = Notifier()
        with caplog.at_level(logging.INFO):
            notifier.error("something broke")
        assert "something broke" in caplog.text

    def test_prompt_logs_message(self, caplog):
        notifier = Notifier()
        with caplog.at_level(logging.INFO):
            notifier.prompt("Custom Title", "custom message")
        assert "custom message" in caplog.text
        assert "Custom Title" in caplog.text

    def test_send_calls_plyer_notification(self):
        mock_notification = MagicMock()
        notifier = Notifier()
        with patch("dirsync.notifications.notification", mock_notification):
            notifier.send("Title", "Message")
        mock_notification.notify.assert_called_once_with(
            title="Title", message="Message", app_name="Dir Sync"
        )

    def test_send_handles_missing_plyer(self, caplog):
        notifier = Notifier()
        with patch("dirsync.notifications.notification", None):
            with caplog.at_level(logging.INFO):
                notifier.send("Title", "Message")
        assert "Title" in caplog.text

    def test_send_handles_not_implemented(self, caplog):
        mock_notification = MagicMock()
        mock_notification.notify.side_effect = NotImplementedError("no backend")
        notifier = Notifier()
        with patch("dirsync.notifications.notification", mock_notification):
            with caplog.at_level(logging.WARNING):
                notifier.send("Title", "Message")

    def test_custom_app_name(self):
        mock_notification = MagicMock()
        notifier = Notifier(app_name="MyApp")
        with patch("dirsync.notifications.notification", mock_notification):
            notifier.success("done")
        mock_notification.notify.assert_called_once_with(
            title="Dir Sync", message="done", app_name="MyApp"
        )
