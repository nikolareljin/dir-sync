from __future__ import annotations

import logging
from dataclasses import dataclass

try:
    from plyer import notification
except ImportError:  # pragma: no cover - optional dependency in tests
    notification = None


@dataclass
class NotificationPayload:
    title: str
    message: str
    app_name: str = "Dir Sync"


class Notifier:
    def __init__(self, app_name: str = "Dir Sync"):
        self.app_name = app_name
        self.logger = logging.getLogger(__name__)

    def send(self, title: str, message: str) -> None:
        self.logger.info("%s - %s", title, message)
        if notification:
            try:
                notification.notify(title=title, message=message, app_name=self.app_name)
            except NotImplementedError as exc:  # pragma: no cover - backend unavailable in CI
                self.logger.warning("Notifications unavailable on this platform: %s", exc)
            except Exception as exc:  # pragma: no cover - defensive logging
                self.logger.warning("Failed to deliver notification: %s", exc)

    def success(self, message: str) -> None:
        self.send("Dir Sync", message)

    def error(self, message: str) -> None:
        self.send("Dir Sync Error", message)

    def prompt(self, title: str, message: str) -> None:
        self.send(title, message)
