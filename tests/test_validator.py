import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from dirsync.config import ConfigManager, SyncAction, SyncConfig
from dirsync.validator import ConfigValidator, PreflightValidator


# --- PreflightValidator: Basic Path Validation ---


class TestPreflightValidatorBasicPaths:
    def test_source_equals_destination_fails(self):
        action = SyncAction(name="test", src_path="/same/path", dst_path="/same/path")
        validator = PreflightValidator()
        is_valid, errors, warnings = validator.validate_action(action)
        assert not is_valid
        assert any("identical" in e.lower() for e in errors)

    def test_destination_nested_in_source_fails(self):
        action = SyncAction(name="test", src_path="/home/user", dst_path="/home/user/backup")
        validator = PreflightValidator()
        is_valid, errors, warnings = validator.validate_action(action)
        assert not is_valid
        assert any("recursion" in e.lower() for e in errors)

    def test_source_nested_in_destination_fails(self):
        action = SyncAction(name="test", src_path="/home/user/data", dst_path="/home/user")
        validator = PreflightValidator()
        is_valid, errors, warnings = validator.validate_action(action)
        assert not is_valid
        assert any("nested" in e.lower() for e in errors)

    def test_missing_source_fails(self):
        action = SyncAction(name="test", src_path="", dst_path="/dest")
        validator = PreflightValidator()
        is_valid, errors, warnings = validator.validate_action(action)
        assert not is_valid
        assert any("source" in e.lower() and "missing" in e.lower() for e in errors)

    def test_missing_destination_fails(self):
        action = SyncAction(name="test", src_path="/src", dst_path="")
        validator = PreflightValidator()
        is_valid, errors, warnings = validator.validate_action(action)
        assert not is_valid
        assert any("destination" in e.lower() and "missing" in e.lower() for e in errors)

    def test_valid_paths_pass(self):
        with TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "src"
            dst = Path(tmpdir) / "dst"
            src.mkdir()
            dst.mkdir()
            action = SyncAction(name="test", src_path=str(src), dst_path=str(dst))
            validator = PreflightValidator()
            is_valid, errors, warnings = validator.validate_action(action)
            assert is_valid
            assert errors == []


# --- PreflightValidator: Cron Validation ---


class TestPreflightValidatorCron:
    def test_valid_cron_passes(self):
        action = SyncAction(
            name="test",
            src_path="/src",
            dst_path="/dst",
            action_type="scheduled",
            schedule="0 2 * * *"
        )
        validator = PreflightValidator()
        is_valid, errors, warnings = validator.validate_action(action)
        assert is_valid
        assert errors == []

    def test_invalid_cron_fails(self):
        action = SyncAction(
            name="test",
            src_path="/src",
            dst_path="/dst",
            action_type="scheduled",
            schedule="invalid cron"
        )
        validator = PreflightValidator()
        is_valid, errors, warnings = validator.validate_action(action)
        assert not is_valid
        assert any("cron" in e.lower() and "invalid" in e.lower() for e in errors)

    def test_cron_out_of_range_fails(self):
        # Minute 99 is invalid (0-59)
        action = SyncAction(
            name="test",
            src_path="/src",
            dst_path="/dst",
            action_type="scheduled",
            schedule="99 * * * *"
        )
        validator = PreflightValidator()
        is_valid, errors, warnings = validator.validate_action(action)
        assert not is_valid

    def test_special_cron_expressions_pass(self):
        for special in ["@yearly", "@monthly", "@weekly", "@daily", "@hourly"]:
            action = SyncAction(
                name="test",
                src_path="/src",
                dst_path="/dst",
                action_type="scheduled",
                schedule=special
            )
            validator = PreflightValidator()
            is_valid, errors, warnings = validator.validate_action(action)
            assert is_valid, "Failed for {}".format(special)

    def test_cron_with_steps_passes(self):
        action = SyncAction(
            name="test",
            src_path="/src",
            dst_path="/dst",
            action_type="scheduled",
            schedule="*/15 * * * *"  # Every 15 minutes
        )
        validator = PreflightValidator()
        is_valid, errors, warnings = validator.validate_action(action)
        assert is_valid

    def test_cron_with_ranges_passes(self):
        action = SyncAction(
            name="test",
            src_path="/src",
            dst_path="/dst",
            action_type="scheduled",
            schedule="0 9-17 * * 1-5"  # Business hours, weekdays
        )
        validator = PreflightValidator()
        is_valid, errors, warnings = validator.validate_action(action)
        assert is_valid

    def test_cron_with_lists_passes(self):
        action = SyncAction(
            name="test",
            src_path="/src",
            dst_path="/dst",
            action_type="scheduled",
            schedule="0 9,12,17 * * *"  # 9am, noon, 5pm
        )
        validator = PreflightValidator()
        is_valid, errors, warnings = validator.validate_action(action)
        assert is_valid


# --- PreflightValidator: Destructive Sync Warnings ---


class TestPreflightValidatorDestructiveSync:
    def test_one_way_no_filters_warns(self):
        action = SyncAction(
            name="test",
            src_path="/src",
            dst_path="/dst",
            method="one_way",
            includes=[],
            excludes=[]
        )
        validator = PreflightValidator()
        is_valid, errors, warnings = validator.validate_action(action)
        assert is_valid  # Still valid
        assert any("destructive" in w.lower() or "overwrite" in w.lower() for w in warnings)

    def test_one_way_with_filters_no_warning(self):
        action = SyncAction(
            name="test",
            src_path="/src",
            dst_path="/dst",
            method="one_way",
            includes=["*.txt"],
            excludes=[]
        )
        validator = PreflightValidator()
        is_valid, errors, warnings = validator.validate_action(action)
        assert is_valid
        # Should not have destructive warning when filters are present
        assert not any("destructive" in w.lower() or "overwrite" in w.lower() for w in warnings)


# --- ConfigValidator: Cross-Action Validation ---


class TestConfigValidator:
    def test_duplicate_action_names_fail(self):
        actions = [
            SyncAction(name="dup", src_path="/src1", dst_path="/dst1"),
            SyncAction(name="dup", src_path="/src2", dst_path="/dst2"),
        ]
        validator = ConfigValidator()
        is_valid, errors, warnings = validator.validate_config(actions)
        assert not is_valid
        assert any("duplicate" in e.lower() for e in errors)

    def test_unique_action_names_pass(self):
        actions = [
            SyncAction(name="action1", src_path="/src1", dst_path="/dst1"),
            SyncAction(name="action2", src_path="/src2", dst_path="/dst2"),
        ]
        validator = ConfigValidator()
        is_valid, errors, warnings = validator.validate_config(actions)
        assert is_valid
        assert errors == []


# --- ConfigManager Integration ---


class TestConfigManagerValidation:
    def test_save_validates_by_default(self, tmp_path):
        config_path = tmp_path / "config.yml"
        manager = ConfigManager(path=config_path)
        manager.config.actions = []
        
        # Add invalid action (same src/dst)
        invalid_action = SyncAction(name="bad", src_path="/same", dst_path="/same")
        manager.config.actions.append(invalid_action)
        
        with pytest.raises(ValueError, match="validation failed"):
            manager.save()

    def test_save_with_validation_disabled(self, tmp_path):
        config_path = tmp_path / "config.yml"
        manager = ConfigManager(path=config_path, skip_validation=True)
        manager.config.actions = []
        
        # Add invalid action
        invalid_action = SyncAction(name="bad", src_path="/same", dst_path="/same")
        manager.config.actions.append(invalid_action)
        
        # Should not raise
        manager.save()
        assert config_path.exists()

    def test_add_action_validates(self, tmp_path):
        config_path = tmp_path / "config.yml"
        manager = ConfigManager(path=config_path)
        manager.config.actions = []
        
        invalid_action = SyncAction(name="bad", src_path="/same", dst_path="/same")
        
        with pytest.raises(ValueError, match="validation failed"):
            manager.add_action(invalid_action)

    def test_ensure_default_creates_safe_config(self, tmp_path):
        config_path = tmp_path / "config.yml"
        manager = ConfigManager(path=config_path)
        manager.config.actions = []
        manager.ensure_default()
        
        assert len(manager.config.actions) == 1
        action = manager.config.actions[0]
        assert action.name == "documents-backup"
        # Default should use Documents folder, not entire home
        assert "Documents" in action.src_path
        # Destination should be under dir-sync-backups subfolder
        assert "dir-sync-backups" in action.dst_path
        # Validate the default passes validation
        is_valid, errors, warnings = action.validate()
        assert is_valid, "Default action failed validation: {}".format(errors)

    def test_validate_method(self, tmp_path):
        config_path = tmp_path / "config.yml"
        manager = ConfigManager(path=config_path)
        manager.config.actions = []
        
        # Add valid action
        action = SyncAction(name="test", src_path="/src", dst_path="/dst")
        manager.config.actions.append(action)
        
        is_valid, errors, warnings = manager.validate()
        assert is_valid
        assert errors == []


# --- SyncAction.validate() method ---


class TestSyncActionValidateMethod:
    def test_validate_method_exists(self):
        action = SyncAction(name="test", src_path="/src", dst_path="/dst")
        is_valid, errors, warnings = action.validate()
        assert is_valid

    def test_validate_method_catches_errors(self):
        action = SyncAction(name="test", src_path="/same", dst_path="/same")
        is_valid, errors, warnings = action.validate()
        assert not is_valid
        assert len(errors) > 0
