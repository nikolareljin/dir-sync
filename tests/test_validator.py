from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from dirsync.config import ConfigManager, SyncAction
from dirsync.validator import ConfigValidator, PreflightValidator

# --- PreflightValidator: Basic Path Validation ---


class TestPreflightValidatorBasicPaths:
    def test_source_equals_destination_fails(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "path"
            path.mkdir()
            action = SyncAction(name="test", src_path=str(path), dst_path=str(path))
            validator = PreflightValidator()
            is_valid, errors, _warnings = validator.validate_action(action)
            assert not is_valid
            assert any("identical" in e.lower() for e in errors)

    def test_destination_nested_in_source_fails(self):
        with TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "src"
            dst = src / "backup"
            src.mkdir()
            dst.mkdir()
            action = SyncAction(name="test", src_path=str(src), dst_path=str(dst))
            validator = PreflightValidator()
            is_valid, errors, _warnings = validator.validate_action(action)
            assert not is_valid
            assert any("recursion" in e.lower() for e in errors)

    def test_source_nested_in_destination_fails(self):
        with TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "src" / "data"
            dst = Path(tmpdir) / "src"
            src.parent.mkdir(parents=True)
            src.mkdir()
            action = SyncAction(name="test", src_path=str(src), dst_path=str(dst))
            validator = PreflightValidator()
            is_valid, errors, _warnings = validator.validate_action(action)
            assert not is_valid
            assert any("nested" in e.lower() for e in errors)

    def test_missing_source_fails(self):
        action = SyncAction(name="test", src_path="", dst_path="/dest")
        validator = PreflightValidator()
        is_valid, errors, _warnings = validator.validate_action(action)
        assert not is_valid
        assert any("source" in e.lower() and "missing" in e.lower() for e in errors)

    def test_missing_destination_fails(self):
        action = SyncAction(name="test", src_path="/src", dst_path="")
        validator = PreflightValidator()
        is_valid, errors, _warnings = validator.validate_action(action)
        assert not is_valid
        assert any("destination" in e.lower() and "missing" in e.lower() for e in errors)

    def test_nonexistent_source_fails(self):
        with TemporaryDirectory() as tmpdir:
            nonexistent = Path(tmpdir) / "nonexistent"
            dst = Path(tmpdir) / "dst"
            dst.mkdir()
            action = SyncAction(name="test", src_path=str(nonexistent), dst_path=str(dst))
            validator = PreflightValidator()
            is_valid, errors, _warnings = validator.validate_action(action)
            assert not is_valid
            assert any("not exist" in e.lower() or "source" in e.lower() for e in errors)

    def test_source_file_fails(self):
        with TemporaryDirectory() as tmpdir:
            src_file = Path(tmpdir) / "source.txt"
            dst = Path(tmpdir) / "dst"
            src_file.write_text("data", encoding="utf-8")
            dst.mkdir()
            action = SyncAction(name="test", src_path=str(src_file), dst_path=str(dst))
            validator = PreflightValidator()
            is_valid, errors, _warnings = validator.validate_action(action)
            assert not is_valid
            assert any("source path must be a directory" in e.lower() for e in errors)

    def test_existing_destination_file_fails(self):
        with TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "src"
            dst_file = Path(tmpdir) / "dest.txt"
            src.mkdir()
            dst_file.write_text("data", encoding="utf-8")
            action = SyncAction(name="test", src_path=str(src), dst_path=str(dst_file))
            validator = PreflightValidator()
            is_valid, errors, _warnings = validator.validate_action(action)
            assert not is_valid
            assert any("destination path must be a directory" in e.lower() for e in errors)

    def test_valid_paths_pass(self):
        with TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "src"
            dst = Path(tmpdir) / "dst"
            src.mkdir()
            dst.mkdir()
            action = SyncAction(name="test", src_path=str(src), dst_path=str(dst))
            validator = PreflightValidator()
            is_valid, errors, _warnings = validator.validate_action(action)
            assert is_valid
            assert errors == []


# --- PreflightValidator: Cron Validation ---


class TestPreflightValidatorCron:
    def test_valid_cron_passes(self):
        with TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "src"
            dst = Path(tmpdir) / "dst"
            src.mkdir()
            dst.mkdir()
            action = SyncAction(
                name="test",
                src_path=str(src),
                dst_path=str(dst),
                action_type="scheduled",
                schedule="0 2 * * *",
            )
            validator = PreflightValidator()
            is_valid, errors, _warnings = validator.validate_action(action)
            assert is_valid
            assert errors == []

    def test_invalid_cron_fails(self):
        with TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "src"
            dst = Path(tmpdir) / "dst"
            src.mkdir()
            dst.mkdir()
            action = SyncAction(
                name="test",
                src_path=str(src),
                dst_path=str(dst),
                action_type="scheduled",
                schedule="invalid cron",
            )
            validator = PreflightValidator()
            is_valid, errors, _warnings = validator.validate_action(action)
            assert not is_valid
            assert any("cron" in e.lower() and "invalid" in e.lower() for e in errors)

    def test_cron_out_of_range_fails(self):
        with TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "src"
            dst = Path(tmpdir) / "dst"
            src.mkdir()
            dst.mkdir()
            action = SyncAction(
                name="test",
                src_path=str(src),
                dst_path=str(dst),
                action_type="scheduled",
                schedule="99 * * * *",
            )
            validator = PreflightValidator()
            is_valid, _errors, _warnings = validator.validate_action(action)
            assert not is_valid

    def test_special_cron_expressions_pass(self):
        with TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "src"
            dst = Path(tmpdir) / "dst"
            src.mkdir()
            dst.mkdir()
            for special in ["@yearly", "@monthly", "@weekly", "@daily", "@hourly"]:
                action = SyncAction(
                    name="test",
                    src_path=str(src),
                    dst_path=str(dst),
                    action_type="scheduled",
                    schedule=special,
                )
                validator = PreflightValidator()
                is_valid, _errors, _warnings = validator.validate_action(action)
                assert is_valid, "Failed for {}".format(special)

    def test_cron_with_steps_passes(self):
        with TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "src"
            dst = Path(tmpdir) / "dst"
            src.mkdir()
            dst.mkdir()
            action = SyncAction(
                name="test",
                src_path=str(src),
                dst_path=str(dst),
                action_type="scheduled",
                schedule="*/15 * * * *",  # Every 15 minutes
            )
            validator = PreflightValidator()
            is_valid, _errors, _warnings = validator.validate_action(action)
            assert is_valid

    def test_cron_with_ranges_passes(self):
        with TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "src"
            dst = Path(tmpdir) / "dst"
            src.mkdir()
            dst.mkdir()
            action = SyncAction(
                name="test",
                src_path=str(src),
                dst_path=str(dst),
                action_type="scheduled",
                schedule="0 9-17 * * 1-5",  # Business hours, weekdays
            )
            validator = PreflightValidator()
            is_valid, _errors, _warnings = validator.validate_action(action)
            assert is_valid

    def test_cron_with_lists_passes(self):
        with TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "src"
            dst = Path(tmpdir) / "dst"
            src.mkdir()
            dst.mkdir()
            action = SyncAction(
                name="test",
                src_path=str(src),
                dst_path=str(dst),
                action_type="scheduled",
                schedule="0 9,12,17 * * *",  # 9am, noon, 5pm
            )
            validator = PreflightValidator()
            is_valid, errors, _warnings = validator.validate_action(action)
            assert is_valid


# --- PreflightValidator: Destructive Sync Warnings ---


class TestPreflightValidatorDestructiveSync:
    def test_one_way_no_filters_warns(self):
        with TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "src"
            dst = Path(tmpdir) / "dst"
            src.mkdir()
            dst.mkdir()
            action = SyncAction(
                name="test",
                src_path=str(src),
                dst_path=str(dst),
                method="one_way",
                includes=[],
                excludes=[],
            )
            validator = PreflightValidator()
            is_valid, errors, warnings = validator.validate_action(action)
            assert is_valid
            assert any("destructive" in w.lower() or "overwrite" in w.lower() for w in warnings)

    def test_one_way_with_filters_no_warning(self):
        with TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "src"
            dst = Path(tmpdir) / "dst"
            src.mkdir()
            dst.mkdir()
            action = SyncAction(
                name="test",
                src_path=str(src),
                dst_path=str(dst),
                method="one_way",
                includes=["*.txt"],
                excludes=[],
            )
            validator = PreflightValidator()
            is_valid, errors, warnings = validator.validate_action(action)
            assert is_valid
            assert not any("destructive" in w.lower() or "overwrite" in w.lower() for w in warnings)


# --- ConfigValidator: Cross-Action Validation ---


class TestConfigValidator:
    def test_duplicate_action_names_fail(self):
        with TemporaryDirectory() as tmpdir:
            src1 = Path(tmpdir) / "src1"
            dst1 = Path(tmpdir) / "dst1"
            src1.mkdir()
            dst1.mkdir()
            src2 = Path(tmpdir) / "src2"
            dst2 = Path(tmpdir) / "dst2"
            src2.mkdir()
            dst2.mkdir()
            actions = [
                SyncAction(name="dup", src_path=str(src1), dst_path=str(dst1)),
                SyncAction(name="dup", src_path=str(src2), dst_path=str(dst2)),
            ]
            validator = ConfigValidator()
            is_valid, errors, _warnings = validator.validate_config(actions)
            assert not is_valid
            assert any("duplicate" in e.lower() for e in errors)

    def test_unique_action_names_pass(self):
        with TemporaryDirectory() as tmpdir:
            src1 = Path(tmpdir) / "src1"
            dst1 = Path(tmpdir) / "dst1"
            src1.mkdir()
            dst1.mkdir()
            src2 = Path(tmpdir) / "src2"
            dst2 = Path(tmpdir) / "dst2"
            src2.mkdir()
            dst2.mkdir()
            actions = [
                SyncAction(name="action1", src_path=str(src1), dst_path=str(dst1)),
                SyncAction(name="action2", src_path=str(src2), dst_path=str(dst2)),
            ]
            validator = ConfigValidator()
            is_valid, errors, _warnings = validator.validate_config(actions)
            assert is_valid
            assert errors == []


# --- ConfigManager Integration ---


class TestConfigManagerValidation:
    def test_save_validates_by_default(self, tmp_path):
        config_path = tmp_path / "config.yml"
        manager = ConfigManager(path=config_path)
        manager.config.actions = []

        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "path"
            path.mkdir()
            invalid_action = SyncAction(name="bad", src_path=str(path), dst_path=str(path))
            manager.config.actions.append(invalid_action)

            with pytest.raises(ValueError, match="validation failed"):
                manager.save()

    def test_save_with_validation_disabled(self, tmp_path):
        config_path = tmp_path / "config.yml"
        manager = ConfigManager(path=config_path, skip_validation=True)
        manager.config.actions = []

        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "path"
            path.mkdir()
            invalid_action = SyncAction(name="bad", src_path=str(path), dst_path=str(path))
            manager.config.actions.append(invalid_action)

        manager.save()
        assert config_path.exists()

    def test_add_action_validates(self, tmp_path):
        config_path = tmp_path / "config.yml"
        manager = ConfigManager(path=config_path)
        manager.config.actions = []

        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "path"
            path.mkdir()
            invalid_action = SyncAction(name="bad", src_path=str(path), dst_path=str(path))

            with pytest.raises(ValueError, match="validation failed"):
                manager.add_action(invalid_action)

    def test_add_action_rolls_back_on_configuration_validation_failure(self, tmp_path):
        config_path = tmp_path / "config.yml"
        manager = ConfigManager(path=config_path)

        with TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            valid_src = base / "valid-src"
            valid_dst = base / "valid-dst"
            valid_src.mkdir()
            valid_dst.mkdir()
            existing_action = SyncAction(
                name="existing", src_path=str(valid_src), dst_path=str(valid_dst)
            )

            broken_src = base / "broken-src"
            broken_dst = broken_src / "nested"
            broken_src.mkdir()
            broken_dst.mkdir()
            invalid_existing = SyncAction(
                name="broken", src_path=str(broken_src), dst_path=str(broken_dst)
            )

            new_src = base / "new-src"
            new_dst = base / "new-dst"
            new_src.mkdir()
            new_dst.mkdir()
            new_action = SyncAction(name="new", src_path=str(new_src), dst_path=str(new_dst))

            manager.config.actions = [existing_action, invalid_existing]

            with pytest.raises(ValueError, match="Configuration validation failed"):
                manager.add_action(new_action)

            assert manager.config.find_action("existing") is not None
            assert manager.config.find_action("new") is None

    def test_update_action_rolls_back_on_configuration_validation_failure(self, tmp_path):
        config_path = tmp_path / "config.yml"
        manager = ConfigManager(path=config_path)

        with TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            src = base / "src"
            dst = base / "dst"
            src.mkdir()
            dst.mkdir()
            current_action = SyncAction(name="edit", src_path=str(src), dst_path=str(dst))

            broken_src = base / "broken-src"
            broken_dst = broken_src / "nested"
            broken_src.mkdir()
            broken_dst.mkdir()
            invalid_existing = SyncAction(
                name="broken", src_path=str(broken_src), dst_path=str(broken_dst)
            )

            replacement_dst = base / "replacement-dst"
            replacement_dst.mkdir()
            updated_action = SyncAction(
                name="edit", src_path=str(src), dst_path=str(replacement_dst)
            )

            manager.config.actions = [current_action, invalid_existing]

            with pytest.raises(ValueError, match="Configuration validation failed"):
                manager.update_action(updated_action)

            action = manager.config.find_action("edit")
            assert action is not None
            assert action.src_path == str(src)
            assert action.dst_path == str(dst)

    def test_remove_action_rolls_back_on_configuration_validation_failure(self, tmp_path):
        config_path = tmp_path / "config.yml"
        manager = ConfigManager(path=config_path)

        with TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            src1 = base / "src1"
            dst1 = base / "dst1"
            src1.mkdir()
            dst1.mkdir()
            src2 = base / "src2"
            dst2 = src2 / "nested"
            src2.mkdir()
            dst2.mkdir()

            valid_action = SyncAction(name="valid", src_path=str(src1), dst_path=str(dst1))
            invalid_action = SyncAction(name="invalid", src_path=str(src2), dst_path=str(dst2))

            manager.config.actions = [valid_action, invalid_action]

            with pytest.raises(ValueError, match="Configuration validation failed"):
                manager.remove_action("valid")

            assert manager.config.find_action("valid") is not None
            assert manager.config.find_action("invalid") is not None

    def test_ensure_default_creates_safe_config(self, tmp_path, monkeypatch):
        config_path = tmp_path / "config.yml"
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        fallback_src = fake_home / "dir-sync-source"
        import dirsync.config as config_module

        monkeypatch.setattr(config_module.Path, "home", lambda: fake_home)
        manager = ConfigManager(path=config_path)
        manager.config.actions = []
        manager.ensure_default()

        assert len(manager.config.actions) == 1
        action = manager.config.actions[0]
        assert action.name == "documents-backup"
        assert "dir-sync-backups" in action.dst_path
        assert action.src_path == str(fallback_src)
        assert not (fake_home / "Documents").exists()
        is_valid, errors, _warnings = action.validate()
        assert is_valid, "Default action failed validation: {}".format(errors)

    def test_validate_method(self, tmp_path):
        config_path = tmp_path / "config.yml"
        manager = ConfigManager(path=config_path)
        manager.config.actions = []

        with TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "src"
            dst = Path(tmpdir) / "dst"
            src.mkdir()
            dst.mkdir()
            action = SyncAction(name="test", src_path=str(src), dst_path=str(dst))
            manager.config.actions.append(action)

            is_valid, errors, _warnings = manager.validate()
            assert is_valid
            assert errors == []


# --- SyncAction.validate() method ---


class TestSyncActionValidateMethod:
    def test_validate_method_exists(self):
        with TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "src"
            dst = Path(tmpdir) / "dst"
            src.mkdir()
            dst.mkdir()
            action = SyncAction(name="test", src_path=str(src), dst_path=str(dst))
            is_valid, _errors, _warnings = action.validate()
            assert is_valid

    def test_validate_method_catches_errors(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "path"
            path.mkdir()
            action = SyncAction(name="test", src_path=str(path), dst_path=str(path))
            is_valid, errors, _warnings = action.validate()
            assert not is_valid
            assert len(errors) > 0
