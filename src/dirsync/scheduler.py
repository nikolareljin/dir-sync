from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Dict

from croniter import croniter


class ActionScheduler:
    def __init__(self, runner):
        self.runner = runner
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._scheduled: Dict[str, Dict[str, object]] = {}
        self._lock = threading.Lock()

    def configure(self, actions):
        with self._lock:
            self._scheduled = {}
            for action in actions:
                if action.action_type == "scheduled" and action.schedule:
                    self._scheduled[action.name] = {
                        "action": action,
                        "next": self._next_time(action.schedule),
                    }
                elif action.action_type == "auto_on_start":
                    threading.Thread(target=self.runner, args=(action,), daemon=True).start()

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1)

    def _loop(self):
        while not self._stop.is_set():
            now = datetime.now()
            with self._lock:
                for payload in self._scheduled.values():
                    action = payload["action"]
                    if now >= payload["next"]:
                        threading.Thread(target=self.runner, args=(action,), daemon=True).start()
                        payload["next"] = self._next_time(action.schedule)
            time.sleep(30)

    def _next_time(self, expr: str):
        base = datetime.now()
        return croniter(expr, base).get_next(datetime)
