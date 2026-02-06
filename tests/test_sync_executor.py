from dirsync.config import SyncAction
from dirsync.sync import SyncExecutor


class DummyNotifier:
    def __init__(self):
        self.messages = []

    def success(self, message):
        self.messages.append(message)

    def error(self, message):  # pragma: no cover - not used
        self.messages.append(message)


def test_python_copy_fallback(tmp_path, monkeypatch):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    (src / "file.txt").write_text("hello")

    notifier = DummyNotifier()
    executor = SyncExecutor(notifier)
    monkeypatch.setattr(executor, "rsync_path", None)
    monkeypatch.setattr(executor, "robocopy_path", None)

    action = SyncAction(
        name="copy",
        src_path=str(src),
        dst_path=str(dst),
        method="one_way",
        action_type="manual",
    )
    executor.run_action(action)

    assert (dst / "file.txt").read_text() == "hello"
    assert any("copy" in msg for msg in notifier.messages)


def test_pending_changes_fallback(tmp_path, monkeypatch):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    dst.mkdir()
    (src / "file.txt").write_text("new-content")
    (dst / "file.txt").write_text("old-content")

    notifier = DummyNotifier()
    executor = SyncExecutor(notifier)
    monkeypatch.setattr(executor, "rsync_path", None)
    monkeypatch.setattr(executor, "robocopy_path", None)

    action = SyncAction(
        name="pending",
        src_path=str(src),
        dst_path=str(dst),
        method="one_way",
        action_type="manual",
    )

    assert executor.has_pending_source_changes(action) is True


def test_pending_actions_filters_changed_items(tmp_path, monkeypatch):
    src_a = tmp_path / "src-a"
    dst_a = tmp_path / "dst-a"
    src_b = tmp_path / "src-b"
    dst_b = tmp_path / "dst-b"
    src_a.mkdir()
    dst_a.mkdir()
    src_b.mkdir()
    dst_b.mkdir()
    (src_a / "file.txt").write_text("updated")
    (dst_a / "file.txt").write_text("outdated")
    (src_b / "same.txt").write_text("same")
    (dst_b / "same.txt").write_text("same")

    notifier = DummyNotifier()
    executor = SyncExecutor(notifier)
    monkeypatch.setattr(executor, "rsync_path", None)
    monkeypatch.setattr(executor, "robocopy_path", None)

    changed_action = SyncAction(
        name="changed",
        src_path=str(src_a),
        dst_path=str(dst_a),
        method="one_way",
        action_type="manual",
    )
    unchanged_action = SyncAction(
        name="unchanged",
        src_path=str(src_b),
        dst_path=str(dst_b),
        method="one_way",
        action_type="manual",
    )

    changed = executor.pending_actions([changed_action, unchanged_action])
    assert [a.name for a in changed] == ["changed"]
