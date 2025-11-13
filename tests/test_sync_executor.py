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
