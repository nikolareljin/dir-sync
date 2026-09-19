from __future__ import annotations

import pytest

from dirsync.config import ConfigManager, SyncAction, SyncConfig
from dirsync.ui_config import ConfigWindow

# --- SyncAction ---


class TestSyncActionNormalize:
    def test_expands_home_dir(self):
        action = SyncAction(name="a", src_path="~/src", dst_path="~/dst")
        action.normalize()
        assert "~" not in action.src_path
        assert "~" not in action.dst_path

    def test_rejects_invalid_profile(self):
        action = SyncAction(name="a", src_path="/a", dst_path="/b", profile="invalid")
        with pytest.raises(ValueError, match="Unsupported sync profile"):
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

    def test_validate_rejects_unsupported_profile(self, tmp_path):
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        dst.mkdir()
        action = SyncAction(name="a", src_path=str(src), dst_path=str(dst), profile="invalid")

        is_valid, errors, _warnings = action.validate()

        assert not is_valid
        assert any("Unsupported sync profile" in error for error in errors)

    def test_validate_rejects_unsupported_action_type(self, tmp_path):
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        dst.mkdir()
        action = SyncAction(
            name="a",
            src_path=str(src),
            dst_path=str(dst),
            action_type="invalid",
        )

        is_valid, errors, _warnings = action.validate()

        assert not is_valid
        assert any("Unsupported action type" in error for error in errors)


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
        config.add_action(SyncAction(name="up", src_path="/a", dst_path="/b", profile="backup"))
        config.update_action(
            SyncAction(
                name="up",
                src_path="/x",
                dst_path="/y",
                profile="mirror",
                delete_policy="delete_destination_extras",
            )
        )
        assert config.find_action("up").profile == "mirror"

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
            profile="backup",
            action_type="manual",
        )
        manager.config.add_action(sample)
        manager.save()

        loaded = ConfigManager(path=config_path)
        assert loaded.config.find_action("sample")
        assert loaded.config.find_action("sample").profile == "backup"

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
            SyncAction(name="exp", src_path=str(src), dst_path=str(dst), profile="backup")
        )
        manager.save()
        manager.export(export_path)
        assert export_path.exists()

        other = ConfigManager(path=tmp_path / "other.yml")
        other.import_file(export_path)
        assert other.config.find_action("exp")
        assert other.config.find_action("exp").profile == "backup"

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

    def test_ensure_default_rejects_file_at_fallback_source(self, tmp_path, monkeypatch):
        config_path = tmp_path / "config.yml"
        manager = ConfigManager(path=config_path)
        manager.config.actions = []
        monkeypatch.setattr("dirsync.config.Path.home", lambda: tmp_path)
        (tmp_path / "dir-sync-source").write_text("not a directory", encoding="utf-8")

        with pytest.raises(ValueError, match="Default source path .* is not a directory"):
            manager.ensure_default()

    def test_ensure_default_rejects_file_at_backup_root(self, tmp_path, monkeypatch):
        config_path = tmp_path / "config.yml"
        manager = ConfigManager(path=config_path)
        manager.config.actions = []
        monkeypatch.setattr("dirsync.config.Path.home", lambda: tmp_path)
        (tmp_path / "dir-sync-backups").write_text("not a directory", encoding="utf-8")

        with pytest.raises(ValueError, match="Default destination path .* is not a directory"):
            manager.ensure_default()

    def test_load_empty_file(self, tmp_path):
        config_path = tmp_path / "config.yml"
        config_path.write_text("")
        manager = ConfigManager(path=config_path)
        assert manager.config.actions == []
        assert manager.config.sync_tool == "rsync"

    def test_load_rejects_non_mapping_yaml(self, tmp_path):
        config_path = tmp_path / "config.yml"
        config_path.write_text("- not\n- a\n- mapping\n", encoding="utf-8")

        with pytest.raises(ValueError, match="YAML mapping"):
            ConfigManager(path=config_path)

    def test_import_file_rejects_non_mapping_yaml(self, tmp_path):
        config_path = tmp_path / "config.yml"
        source_path = tmp_path / "invalid.yml"
        source_path.write_text("- not\n- a\n- mapping\n", encoding="utf-8")
        manager = ConfigManager(path=config_path)

        with pytest.raises(ValueError, match="YAML mapping"):
            manager.import_file(source_path)

    def test_load_rejects_falsy_non_mapping_yaml(self, tmp_path):
        config_path = tmp_path / "config.yml"
        config_path.write_text("false\n", encoding="utf-8")

        with pytest.raises(ValueError, match="YAML mapping"):
            ConfigManager(path=config_path)

    def test_import_file_rejects_falsy_non_mapping_yaml(self, tmp_path):
        config_path = tmp_path / "config.yml"
        source_path = tmp_path / "invalid.yml"
        source_path.write_text("false\n", encoding="utf-8")
        manager = ConfigManager(path=config_path)

        with pytest.raises(ValueError, match="YAML mapping"):
            manager.import_file(source_path)

    def test_load_rejects_non_list_actions(self, tmp_path):
        config_path = tmp_path / "config.yml"
        config_path.write_text("actions: {}\n", encoding="utf-8")

        with pytest.raises(ValueError, match="field 'actions' must be a list"):
            ConfigManager(path=config_path)

    def test_load_rejects_non_mapping_action_items(self, tmp_path):
        config_path = tmp_path / "config.yml"
        config_path.write_text("actions:\n  - valid\n", encoding="utf-8")

        with pytest.raises(ValueError, match="action at index 0 must be a mapping"):
            ConfigManager(path=config_path)

    def test_load_reports_invalid_action_index(self, tmp_path):
        config_path = tmp_path / "config.yml"
        config_path.write_text(
            "actions:\n" "  - name: broken\n" "    src_path: null\n" "    dst_path: /tmp/dst\n",
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match=r"action at index 0 is invalid"):
            ConfigManager(path=config_path)

    def test_import_file_reports_invalid_action_index(self, tmp_path):
        config_path = tmp_path / "config.yml"
        source_path = tmp_path / "invalid.yml"
        source_path.write_text(
            "actions:\n" "  - name: broken\n" "    src_path: null\n" "    dst_path: /tmp/dst\n",
            encoding="utf-8",
        )
        manager = ConfigManager(path=config_path)

        with pytest.raises(ValueError, match=r"action at index 0 is invalid"):
            manager.import_file(source_path)

    def test_add_action_logs_warning_once(self, tmp_path, caplog):
        config_path = tmp_path / "config.yml"
        manager = ConfigManager(path=config_path)
        manager.config.actions = []
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        dst.mkdir()
        action = SyncAction(
            name="warn-add",
            src_path=str(src),
            dst_path=str(dst),
            profile="mirror",
            delete_policy="delete_destination_extras",
        )

        with caplog.at_level("WARNING"):
            manager.add_action(action)

        messages = [record.getMessage() for record in caplog.records]
        assert messages == [
            "Config warning: Action 'warn-add': Mirror deletes destination-only files so "
            "the destination exactly matches the source."
        ]

    def test_update_action_logs_warning_once(self, tmp_path, caplog):
        config_path = tmp_path / "config.yml"
        manager = ConfigManager(path=config_path)
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        dst.mkdir()
        manager.add_action(
            SyncAction(
                name="warn-update",
                src_path=str(src),
                dst_path=str(dst),
                profile="mirror",
                delete_policy="delete_destination_extras",
            )
        )

        caplog.clear()

        with caplog.at_level("WARNING"):
            manager.update_action(
                SyncAction(
                    name="warn-update",
                    src_path=str(src),
                    dst_path=str(dst),
                    profile="mirror",
                    delete_policy="delete_destination_extras",
                )
            )

        messages = [record.getMessage() for record in caplog.records]
        assert messages == [
            "Config warning: Action 'warn-update': Mirror deletes destination-only files so "
            "the destination exactly matches the source."
        ]


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
        profile="backup",
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


def test_guided_schedule_rule_roundtrips(tmp_path):
    config_path = tmp_path / "config.yml"
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    dst.mkdir()
    manager = ConfigManager(path=config_path)
    manager.config.actions = []
    manager.add_action(
        SyncAction(
            name="weekly",
            src_path=str(src),
            dst_path=str(dst),
            action_type="scheduled",
            schedule_rule={"kind": "weekly", "time": "13:02", "weekdays": [0, 6]},
        )
    )

    loaded = ConfigManager(path=config_path)
    action = loaded.config.find_action("weekly")
    assert action.schedule is None
    assert action.schedule_rule == {"kind": "weekly", "time": "13:02", "weekdays": [0, 6]}


def test_last_browse_directory_is_local_and_not_exported(tmp_path):
    config_path = tmp_path / "config.yml"
    manager = ConfigManager(path=config_path)
    directory = tmp_path / "remembered"
    directory.mkdir()
    manager.remember_browse_directory(str(directory))

    loaded = ConfigManager(path=config_path)
    assert loaded.last_browse_directory == str(directory)

    export_path = tmp_path / "export.yml"
    loaded.export(export_path, validate=False)
    assert "ui_state" not in export_path.read_text(encoding="utf-8")


def test_picker_prefers_selected_then_remembered_then_home(tmp_path, monkeypatch):
    manager = ConfigManager(path=tmp_path / "config.yml")
    window = ConfigWindow(manager)
    selected = tmp_path / "selected"
    remembered = tmp_path / "remembered"
    selected.mkdir()
    remembered.mkdir()
    manager.last_browse_directory = str(remembered)

    assert window._picker_initial_directory(str(selected)) == selected
    assert window._picker_initial_directory("") == remembered

    manager.last_browse_directory = None
    monkeypatch.setattr("dirsync.ui_config.Path.home", lambda: tmp_path)
    assert window._picker_initial_directory("") == tmp_path
