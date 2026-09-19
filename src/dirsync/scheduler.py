from __future__ import annotations

import threading
import time
from calendar import monthrange
from datetime import datetime, timedelta
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
                if action.action_type == "scheduled" and (action.schedule or action.schedule_rule):
                    self._scheduled[action.name] = {
                        "action": action,
                        "next": self._next_time(action),
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
                        payload["next"] = self._next_time(action)
            time.sleep(30)

    def _next_time(self, action_or_expr):
        base = datetime.now()
        if isinstance(action_or_expr, str):
            return croniter(action_or_expr, base).get_next(datetime)
        if action_or_expr.schedule_rule:
            return self._next_rule_time(action_or_expr.schedule_rule, base)
        return croniter(action_or_expr.schedule, base).get_next(datetime)

    @staticmethod
    def _next_rule_time(rule, base: datetime) -> datetime:
        kind = rule["kind"]
        if kind == "minutes":
            candidate = base.replace(second=0, microsecond=0) + timedelta(minutes=1)
            offset = (-(candidate.hour * 60 + candidate.minute)) % rule["interval_minutes"]
            return candidate + timedelta(minutes=offset)

        hour, minute = map(int, rule["time"].split(":"))
        if kind == "daily":
            candidate = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
            return candidate if candidate > base else candidate + timedelta(days=1)
        if kind == "weekly":
            for offset in range(8):
                day = (base + timedelta(days=offset)).date()
                candidate = datetime.combine(day, datetime.min.time()).replace(
                    hour=hour, minute=minute
                )
                if day.weekday() in rule["weekdays"] and candidate > base:
                    return candidate
        if kind == "monthly":
            year, month = base.year, base.month
            for _ in range(13):
                day = min(rule["day_of_month"], monthrange(year, month)[1])
                candidate = base.replace(
                    year=year,
                    month=month,
                    day=day,
                    hour=hour,
                    minute=minute,
                    second=0,
                    microsecond=0,
                )
                if candidate > base:
                    return candidate
                month += 1
                if month == 13:
                    year, month = year + 1, 1
        raise ValueError(f"Unsupported schedule rule: {kind}")
