from __future__ import annotations

import subprocess

import pytest

from dirsync.config import SyncAction
from dirsync.sync import SyncExecutor


class DummyNotifier:
    def __init__(self):
        self.messages: list[tuple[str, str]] = []

    def success(self, message):
        self.messages.append(("success", message))

    def error(self, message):
        self.messages.append(("error", message))

    def prompt(self, title, message):
        self.messages.append(("prompt", message))


def _make_action(tmp_path, **overrides):
    defaults = dict(
        name="test",
        src_path=str(tmp_path / "src"),
        dst_path=str(tmp_path / "dst"),
        method="one_way",
        action_type="manual",
    )
    defaults.update(overrides)
    return SyncAction(**defaults)


# --- Python copy fallback ---


class TestPythonCopyFallback:
    def test_basic_copy(self, tmp_path, monkeypatch):
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        (src / "file.txt").write_text("hello")

        notifier = DummyNotifier()
        executor = SyncExecutor(notifier)
        monkeypatch.setattr(executor, "rsync_path", None)
        monkeypatch.setattr(executor, "robocopy_path", None)

        action = _make_action(tmp_path)
        executor.run_action(action)

        assert (dst / "file.txt").read_text() == "hello"
        assert any("test" in msg for _, msg in notifier.messages)

    def test_copy_nested_dirs(self, tmp_path, monkeypatch):
        src = tmp_path / "src"
        (src / "sub" / "deep").mkdir(parents=True)
        (src / "sub" / "deep" / "nested.txt").write_text("deep")
        (src / "top.txt").write_text("top")

        notifier = DummyNotifier()
        executor = SyncExecutor(notifier)
        monkeypatch.setattr(executor, "rsync_path", None)
        monkeypatch.setattr(executor, "robocopy_path", None)

        action = _make_action(tmp_path)
        executor.run_action(action)

        assert (tmp_path / "dst" / "top.txt").read_text() == "top"
        assert (tmp_path / "dst" / "sub" / "deep" / "nested.txt").read_text() == "deep"

    def test_copy_with_includes(self, tmp_path, monkeypatch):
        src = tmp_path / "src"
        src.mkdir()
        (src / "keep.txt").write_text("keep")
        (src / "skip.log").write_text("skip")

        notifier = DummyNotifier()
        executor = SyncExecutor(notifier)
        monkeypatch.setattr(executor, "rsync_path", None)
        monkeypatch.setattr(executor, "robocopy_path", None)

        action = _make_action(tmp_path, includes=["*.txt"])
        executor.run_action(action)

        dst = tmp_path / "dst"
        assert (dst / "keep.txt").exists()
        assert not (dst / "skip.log").exists()

    def test_copy_with_excludes(self, tmp_path, monkeypatch):
        src = tmp_path / "src"
        src.mkdir()
        (src / "keep.txt").write_text("keep")
        (src / "skip.log").write_text("skip")

        notifier = DummyNotifier()
        executor = SyncExecutor(notifier)
        monkeypatch.setattr(executor, "rsync_path", None)
        monkeypatch.setattr(executor, "robocopy_path", None)

        action = _make_action(tmp_path, excludes=["*.log"])
        executor.run_action(action)

        dst = tmp_path / "dst"
        assert (dst / "keep.txt").exists()
        assert not (dst / "skip.log").exists()

    def test_copy_with_includes_and_excludes(self, tmp_path, monkeypatch):
        src = tmp_path / "src"
        src.mkdir()
        (src / "a.txt").write_text("a")
        (src / "b.py").write_text("b")
        (src / "c.log").write_text("c")

        notifier = DummyNotifier()
        executor = SyncExecutor(notifier)
        monkeypatch.setattr(executor, "rsync_path", None)
        monkeypatch.setattr(executor, "robocopy_path", None)

        action = _make_action(tmp_path, includes=["*.txt", "*.py"], excludes=["*.py"])
        executor.run_action(action)

        dst = tmp_path / "dst"
        assert (dst / "a.txt").exists()
        assert not (dst / "b.py").exists()  # excluded takes precedence
        assert not (dst / "c.log").exists()  # not included

    def test_soft_run_without_rsync(self, tmp_path, monkeypatch):
        src = tmp_path / "src"
        src.mkdir()

        notifier = DummyNotifier()
        executor = SyncExecutor(notifier)
        monkeypatch.setattr(executor, "rsync_path", None)
        monkeypatch.setattr(executor, "robocopy_path", None)

        action = _make_action(tmp_path)
        executor.run_action(action, soft_run=True)

        assert any("not available" in msg for _, msg in notifier.messages)


# --- Two-way sync ---


class TestTwoWaySync:
    def test_two_way_copies_both_directions(self, tmp_path, monkeypatch):
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        dst.mkdir()
        (src / "from_src.txt").write_text("src_content")
        (dst / "from_dst.txt").write_text("dst_content")

        notifier = DummyNotifier()
        executor = SyncExecutor(notifier)
        monkeypatch.setattr(executor, "rsync_path", None)
        monkeypatch.setattr(executor, "robocopy_path", None)

        action = _make_action(tmp_path, method="two_way")
        executor.run_action(action)

        assert (dst / "from_src.txt").read_text() == "src_content"
        assert (src / "from_dst.txt").read_text() == "dst_content"


# --- Rsync command building ---


class TestRsyncCommandBuilding:
    def test_rsync_includes_excludes_in_command(self, tmp_path, monkeypatch):
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        dst.mkdir()

        notifier = DummyNotifier()
        executor = SyncExecutor(notifier)
        monkeypatch.setattr(executor, "rsync_path", "/usr/bin/rsync")
        monkeypatch.setattr(executor, "robocopy_path", None)

        captured_cmds = []

        def fake_run(cmd, **kwargs):
            captured_cmds.append(list(cmd))
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)

        action = _make_action(tmp_path, includes=["*.txt", "docs/*"], excludes=["*.log", "tmp/"])
        executor.run_action(action)

        cmd = captured_cmds[0]
        assert "--include" in cmd
        assert "*.txt" in cmd
        assert "docs/*" in cmd
        assert "--exclude" in cmd
        assert "*.log" in cmd
        assert "tmp/" in cmd

        # Verify ordering: includes before excludes, paths at end
        include_idx = cmd.index("--include")
        exclude_idx = cmd.index("--exclude")
        assert include_idx < exclude_idx
        assert cmd[-1].endswith("/")  # dst path
        assert cmd[-2].endswith("/")  # src path

    def test_rsync_dry_run_flags(self, tmp_path, monkeypatch):
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        dst.mkdir()

        notifier = DummyNotifier()
        executor = SyncExecutor(notifier)
        monkeypatch.setattr(executor, "rsync_path", "/usr/bin/rsync")
        monkeypatch.setattr(executor, "robocopy_path", None)

        captured_cmds = []

        def fake_run(cmd, **kwargs):
            captured_cmds.append(list(cmd))
            return subprocess.CompletedProcess(cmd, 0, stdout="preview output", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)

        action = _make_action(tmp_path)
        executor.run_action(action, soft_run=True)

        cmd = captured_cmds[0]
        assert "--dry-run" in cmd
        assert "--stats" in cmd

    def test_rsync_no_patterns_no_flags(self, tmp_path, monkeypatch):
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        dst.mkdir()

        notifier = DummyNotifier()
        executor = SyncExecutor(notifier)
        monkeypatch.setattr(executor, "rsync_path", "/usr/bin/rsync")
        monkeypatch.setattr(executor, "robocopy_path", None)

        captured_cmds = []

        def fake_run(cmd, **kwargs):
            captured_cmds.append(list(cmd))
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)

        action = _make_action(tmp_path)
        executor.run_action(action)

        cmd = captured_cmds[0]
        assert "--include" not in cmd
        assert "--exclude" not in cmd


# --- Robocopy command building ---


class TestRobocopyCommandBuilding:
    def test_robocopy_includes_excludes_in_command(self, tmp_path, monkeypatch):
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        dst.mkdir()

        notifier = DummyNotifier()
        executor = SyncExecutor(notifier)
        monkeypatch.setattr(executor, "rsync_path", None)
        monkeypatch.setattr(executor, "robocopy_path", "robocopy")

        captured_cmds = []

        def fake_run(cmd, **kwargs):
            captured_cmds.append(list(cmd))
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)

        action = _make_action(tmp_path, includes=["*.txt"], excludes=["*.log"])
        executor.run_action(action)

        cmd = captured_cmds[0]
        assert "*.txt" in cmd
        assert "/XF" in cmd
        assert "*.log" in cmd
        assert "/XD" in cmd

    def test_robocopy_dry_run(self, tmp_path, monkeypatch):
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        dst.mkdir()

        notifier = DummyNotifier()
        executor = SyncExecutor(notifier)
        monkeypatch.setattr(executor, "rsync_path", None)
        monkeypatch.setattr(executor, "robocopy_path", "robocopy")

        captured_cmds = []

        def fake_run(cmd, **kwargs):
            captured_cmds.append(list(cmd))
            return subprocess.CompletedProcess(cmd, 0, stdout="preview", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)

        action = _make_action(tmp_path)
        executor.run_action(action, soft_run=True)

        cmd = captured_cmds[0]
        assert "/L" in cmd


# --- Error handling ---


class TestSyncErrors:
    def test_command_failure_raises(self, tmp_path, monkeypatch):
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        dst.mkdir()

        notifier = DummyNotifier()
        executor = SyncExecutor(notifier)
        monkeypatch.setattr(executor, "rsync_path", "/usr/bin/rsync")
        monkeypatch.setattr(executor, "robocopy_path", None)

        def fake_run(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="sync error")

        monkeypatch.setattr(subprocess, "run", fake_run)
        monkeypatch.setattr("dirsync.sync.alert", lambda *a, **kw: None)

        action = _make_action(tmp_path)
        with pytest.raises(RuntimeError, match="sync error"):
            executor.run_action(action)

        assert any("error" in level for level, _ in notifier.messages)


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
