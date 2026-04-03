from __future__ import annotations

import pytest

from dirsync.config import ConfigManager, SyncAction, SyncConfig

# --- SyncAction ---


class TestSyncActionNormalize:
    def test_expands_home_dir(self):
        action = SyncAction(name="a", src_path="~/src", dst_path="~/dst")
        action.normalize()
        assert "~" not in action.src_path
        assert "~" not in action.dst_path

    def test_rejects_invalid_method(self):
        action = SyncAction(name="a", src_path="/a", dst_path="/b", method="invalid")
        with pytest.raises(ValueError, match="Unsupported method"):
            action.normalize()

    def test_rejects_invalid_action_type(self):
        action = SyncAction(name="a", src_path="/a", dst_path="/b", action_type="invalid")
        with pytest.raises(ValueError, match="Unsupported action type"):
            action.normalize()

    def test_clears_schedule_for_non_scheduled(self):
        action = SyncAction(
            name="a", src_path="/a", dst_path="/b", action_type="manual", schedule="0 * * * *"
        )
        action.normalize()
        assert action.schedule is None

    def test_keeps_schedule_for_scheduled(self):
        action = SyncAction(
            name="a", src_path="/a", dst_path="/b", action_type="scheduled", schedule="0 2 * * *"
        )
        action.normalize()
        assert action.schedule == "0 2 * * *"

    def test_strips_include_exclude_patterns(self):
        action = SyncAction(
            name="a",
            src_path="/a",
            dst_path="/b",
            includes=["  *.txt ", "", " docs/* "],
            excludes=["*.log  ", ""],
        )
        action.normalize()
        assert action.includes == ["*.txt", "docs/*"]
        assert action.excludes == ["*.log"]

    def test_defaults_to_empty_patterns(self):
        action = SyncAction(name="a", src_path="/a", dst_path="/b")
        action.normalize()
        assert action.includes == []
        assert action.excludes == []

    def test_returns_self(self):
        action = SyncAction(name="a", src_path="/a", dst_path="/b")
        result = action.normalize()
        assert result is action


# --- SyncConfig ---


class TestSyncConfig:
    def test_add_action(self):
        config = SyncConfig()
        action = SyncAction(name="test", src_path="/a", dst_path="/b")
        config.add_action(action)
        assert len(config.actions) == 1
        assert config.actions[0].name == "test"

    def test_add_duplicate_raises(self):
        config = SyncConfig()
        config.add_action(SyncAction(name="dup", src_path="/a", dst_path="/b"))
        with pytest.raises(ValueError, match="already exists"):
            config.add_action(SyncAction(name="dup", src_path="/c", dst_path="/d"))

    def test_update_action(self):
        config = SyncConfig()
        config.add_action(SyncAction(name="up", src_path="/a", dst_path="/b", method="one_way"))
        config.update_action(SyncAction(name="up", src_path="/x", dst_path="/y", method="two_way"))
        assert config.find_action("up").method == "two_way"

    def test_update_missing_raises(self):
        config = SyncConfig()
        with pytest.raises(ValueError, match="not found"):
            config.update_action(SyncAction(name="missing", src_path="/a", dst_path="/b"))

    def test_remove_action(self):
        config = SyncConfig()
        config.add_action(SyncAction(name="rm", src_path="/a", dst_path="/b"))
        config.remove_action("rm")
        assert config.find_action("rm") is None

    def test_remove_nonexistent_is_noop(self):
        config = SyncConfig()
        config.remove_action("nope")  # should not raise

    def test_find_action_returns_none_for_missing(self):
        config = SyncConfig()
        assert config.find_action("nope") is None


# --- ConfigManager ---


class TestConfigManager:
    def test_roundtrip(self, tmp_path):
        config_path = tmp_path / "config.yml"
        manager = ConfigManager(path=config_path)
        manager.config.actions = []
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        dst.mkdir()
        sample = SyncAction(
            name="sample",
            src_path=str(src),
            dst_path=str(dst),
            method="one_way",
            action_type="manual",
        )
        manager.config.add_action(sample)
        manager.save()

        loaded = ConfigManager(path=config_path)
        assert loaded.config.find_action("sample")
        assert loaded.config.find_action("sample").method == "one_way"

    def test_roundtrip_with_includes_excludes(self, tmp_path):
        config_path = tmp_path / "config.yml"
        manager = ConfigManager(path=config_path)
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        dst.mkdir()
        action = SyncAction(
            name="filtered",
            src_path=str(src),
            dst_path=str(dst),
            includes=["*.py", "docs/*"],
            excludes=["*.pyc", "__pycache__/*"],
        )
        manager.config.add_action(action)
        manager.save()

        loaded = ConfigManager(path=config_path)
        found = loaded.config.find_action("filtered")
        assert found.includes == ["*.py", "docs/*"]
        assert found.excludes == ["*.pyc", "__pycache__/*"]

    def test_export_import(self, tmp_path):
        config_path = tmp_path / "config.yml"
        export_path = tmp_path / "exports" / "export.yml"
        manager = ConfigManager(path=config_path)
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        dst.mkdir()
        manager.config.add_action(
            SyncAction(name="exp", src_path=str(src), dst_path=str(dst), method="one_way")
        )
        manager.save()
        manager.export(export_path)
        assert export_path.exists()

        other = ConfigManager(path=tmp_path / "other.yml")
        other.import_file(export_path)
        assert other.config.find_action("exp")
        assert other.config.find_action("exp").method == "one_way"

    def test_creates_file_on_init(self, tmp_path):
        config_path = tmp_path / "sub" / "config.yml"
        ConfigManager(path=config_path)
        assert config_path.exists()

    def test_ensure_default_adds_sample(self, tmp_path):
        config_path = tmp_path / "config.yml"
        manager = ConfigManager(path=config_path)
        manager.config.actions = []
        manager.ensure_default()
        assert len(manager.config.actions) == 1
        assert manager.config.actions[0].name == "documents-backup"
        assert "dir-sync-backups" in manager.config.actions[0].dst_path

    def test_ensure_default_noop_when_actions_exist(self, tmp_path):
        config_path = tmp_path / "config.yml"
        manager = ConfigManager(path=config_path)
        manager.config.add_action(SyncAction(name="keep", src_path="/a", dst_path="/b"))
        manager.ensure_default()
        assert len(manager.config.actions) == 1
        assert manager.config.actions[0].name == "keep"

    def test_load_empty_file(self, tmp_path):
        config_path = tmp_path / "config.yml"
        config_path.write_text("")
        manager = ConfigManager(path=config_path)
        assert manager.config.actions == []
        assert manager.config.sync_tool == "rsync"

    def test_import_file_rejects_non_mapping_yaml(self, tmp_path):
        config_path = tmp_path / "config.yml"
        source_path = tmp_path / "invalid.yml"
        source_path.write_text("- not\n- a\n- mapping\n")
        manager = ConfigManager(path=config_path)

        with pytest.raises(ValueError, match="YAML mapping"):
            manager.import_file(source_path)


def test_config_persists_device_binding_fields(tmp_path):
    config_path = tmp_path / "config.yml"
    manager = ConfigManager(path=config_path)
    manager.config.actions = []
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    dst.mkdir()
    sample = SyncAction(
        name="usb-sync",
        src_path=str(src),
        dst_path=str(dst),
        method="one_way",
        action_type="auto_on_destination",
        dst_device_id="8D06-A5B2",
        dst_path_on_device="backup/photos",
    )
    manager.config.add_action(sample)
    manager.save()

    loaded = ConfigManager(path=config_path)
    action = loaded.config.find_action("usb-sync")
    assert action
    assert action.dst_device_id == "8D06-A5B2"
    assert action.dst_path_on_device == "backup/photos"
