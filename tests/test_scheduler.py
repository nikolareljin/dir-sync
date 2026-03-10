from __future__ import annotations

import threading
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from dirsync.config import SyncAction
from dirsync.scheduler import ActionScheduler


def _make_action(name, action_type="manual", schedule=None):
    return SyncAction(
        name=name,
        src_path="/src",
        dst_path="/dst",
        method="one_way",
        action_type=action_type,
        schedule=schedule,
    )


class TestSchedulerConfigure:
    def test_registers_scheduled_actions(self):
        runner = MagicMock()
        scheduler = ActionScheduler(runner)
        actions = [
            _make_action("cron-job", action_type="scheduled", schedule="0 2 * * *"),
            _make_action("manual-job", action_type="manual"),
        ]
        scheduler.configure(actions)
        assert "cron-job" in scheduler._scheduled
        assert "manual-job" not in scheduler._scheduled

    def test_auto_on_start_triggers_immediately(self):
        called = threading.Event()

        def runner(action):
            called.set()

        scheduler = ActionScheduler(runner)
        actions = [_make_action("startup", action_type="auto_on_start")]
        scheduler.configure(actions)
        assert called.wait(timeout=2)

    def test_configure_replaces_previous(self):
        runner = MagicMock()
        scheduler = ActionScheduler(runner)
        scheduler.configure([_make_action("a", action_type="scheduled", schedule="0 * * * *")])
        assert "a" in scheduler._scheduled
        scheduler.configure([_make_action("b", action_type="scheduled", schedule="0 * * * *")])
        assert "a" not in scheduler._scheduled
        assert "b" in scheduler._scheduled

    def test_manual_and_auto_on_destination_ignored(self):
        runner = MagicMock()
        scheduler = ActionScheduler(runner)
        actions = [
            _make_action("manual", action_type="manual"),
            _make_action("dest", action_type="auto_on_destination"),
        ]
        scheduler.configure(actions)
        assert len(scheduler._scheduled) == 0


class TestSchedulerNextTime:
    def test_next_time_returns_future_datetime(self):
        runner = MagicMock()
        scheduler = ActionScheduler(runner)
        result = scheduler._next_time("* * * * *")
        assert isinstance(result, datetime)
        assert result > datetime.now()


class TestSchedulerStartStop:
    def test_start_creates_thread(self):
        runner = MagicMock()
        scheduler = ActionScheduler(runner)
        with patch("time.sleep", return_value=None):
            scheduler.start()
            assert scheduler._thread is not None
            assert scheduler._thread.is_alive()
            scheduler.stop()

    def test_stop_terminates_thread(self):
        runner = MagicMock()
        scheduler = ActionScheduler(runner)
        with patch("time.sleep", return_value=None):
            scheduler.start()
            scheduler.stop()
            scheduler._thread.join(timeout=2)
            assert not scheduler._thread.is_alive()

    def test_double_start_is_noop(self):
        runner = MagicMock()
        scheduler = ActionScheduler(runner)
        with patch("time.sleep", return_value=None):
            scheduler.start()
            first_thread = scheduler._thread
            scheduler.start()
            assert scheduler._thread is first_thread
            scheduler.stop()


class TestSchedulerLoop:
    def test_runs_due_action(self):
        called = threading.Event()

        def runner(action):
            called.set()

        scheduler = ActionScheduler(runner)
        action = _make_action("due", action_type="scheduled", schedule="* * * * *")
        scheduler.configure([action])

        # Force the next time to be in the past so it triggers immediately
        with scheduler._lock:
            scheduler._scheduled["due"]["next"] = datetime.now() - timedelta(minutes=1)

        scheduler.start()
        assert called.wait(timeout=5)
        scheduler.stop()
