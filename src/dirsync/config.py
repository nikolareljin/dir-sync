from __future__ import annotations

import logging
import os
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, List, Optional, Tuple

import yaml

from .constants import (
    CONFIG_PATH,
    CONFLICT_POLICIES,
    DELETE_POLICIES,
    SUPPORTED_ACTION_TYPES,
    SUPPORTED_PROFILES,
)
from .validator import ConfigValidator, PreflightValidator

# Use module-level logger for consistent logging
_logger = logging.getLogger(__name__)


@dataclass
class SyncAction:
    name: str
    src_path: str
    dst_path: str
    profile: str = "backup"
    delete_policy: str = "keep_destination"
    conflict_policy: str = "source_wins"
    action_type: str = "manual"
    schedule: Optional[str] = None  # Advanced raw cron expression
    schedule_rule: Optional[dict[str, Any]] = None  # Guided local-time recurrence
    includes: List[str] = field(default_factory=list)  # glob patterns to include
    excludes: List[str] = field(default_factory=list)  # glob patterns to exclude
    dst_device_id: Optional[str] = None
    dst_path_on_device: Optional[str] = None

    def normalize(self) -> "SyncAction":
        self.src_path = os.path.expanduser(self.src_path)
        self.dst_path = os.path.expanduser(self.dst_path)
        self.dst_device_id = (self.dst_device_id or "").strip() or None
        self.dst_path_on_device = (self.dst_path_on_device or "").strip() or None
        if self.profile not in SUPPORTED_PROFILES:
            raise ValueError(f"Unsupported sync profile: {self.profile}")
        if self.delete_policy not in DELETE_POLICIES:
            raise ValueError(f"Unsupported delete policy: {self.delete_policy}")
        if self.conflict_policy not in CONFLICT_POLICIES:
            raise ValueError(f"Unsupported conflict policy: {self.conflict_policy}")
        expected_delete_policy = (
            "keep_destination" if self.profile == "backup" else "delete_destination_extras"
        )
        if self.delete_policy != expected_delete_policy:
            raise ValueError(
                f"Sync profile {self.profile} requires delete_policy " f"{expected_delete_policy}"
            )
        if self.action_type not in SUPPORTED_ACTION_TYPES:
            raise ValueError(f"Unsupported action type: {self.action_type}")
        if self.action_type != "scheduled":
            self.schedule = None
            self.schedule_rule = None
        elif self.schedule_rule is not None and not isinstance(self.schedule_rule, dict):
            raise ValueError("Schedule rule must be a mapping.")
        elif self.schedule is not None and self.schedule_rule is not None:
            raise ValueError(
                "Scheduled actions must use either a guided rule or a cron expression."
            )
        self.includes = [p.strip() for p in self.includes if p.strip()]
        self.excludes = [p.strip() for p in self.excludes if p.strip()]
        return self

    def validate(self) -> Tuple[bool, List[str], List[str]]:
        """Validate this action using preflight validation.

        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        # Keep validate() aligned with normalize()-time constraints without
        # mutating the current action instance, then validate the normalized
        # copy so warnings reflect the effective configuration.
        try:
            normalized = deepcopy(self).normalize()
        except (ValueError, AttributeError, TypeError) as exc:
            return False, [str(exc)], []

        validator = PreflightValidator()
        return validator.validate_action(normalized)


@dataclass
class SyncConfig:
    sync_tool: str = "rsync"
    actions: List[SyncAction] = field(default_factory=list)

    def add_action(self, action: SyncAction) -> None:
        existing = self.find_action(action.name)
        if existing:
            raise ValueError(f"Action '{action.name}' already exists")
        self.actions.append(action.normalize())

    def update_action(self, action: SyncAction) -> None:
        for idx, current in enumerate(self.actions):
            if current.name == action.name:
                self.actions[idx] = action.normalize()
                return
        raise ValueError(f"Action '{action.name}' not found")

    def remove_action(self, name: str) -> None:
        self.actions = [a for a in self.actions if a.name != name]

    def find_action(self, name: str) -> Optional[SyncAction]:
        for action in self.actions:
            if action.name == name:
                return action
        return None


class ConfigManager:
    def __init__(self, path: Path = CONFIG_PATH, skip_validation: bool = False):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.config = SyncConfig()
        self.last_browse_directory: Optional[str] = None
        self.skip_validation = skip_validation
        if self.path.exists():
            self.load()
        else:
            self.save()

    def load(self) -> SyncConfig:
        with self.path.open("r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle)
        raw = {} if raw is None else raw
        if not isinstance(raw, dict):
            raise ValueError("Configuration file must be a YAML mapping at the top level.")
        raw_actions = raw.get("actions", [])
        if not isinstance(raw_actions, list):
            raise ValueError("Configuration field 'actions' must be a list.")

        actions = []
        for index, item in enumerate(raw_actions):
            if not isinstance(item, dict):
                raise ValueError(f"Configuration action at index {index} must be a mapping.")
            try:
                actions.append(self._action_from_payload(item))
            except (AttributeError, TypeError, ValueError) as exc:
                raise ValueError(
                    f"Configuration action at index {index} is invalid: {exc}"
                ) from exc
        self.config = SyncConfig(sync_tool=raw.get("sync_tool", "rsync"), actions=actions)
        ui_state = raw.get("ui_state", {})
        if isinstance(ui_state, dict):
            last_directory = ui_state.get("last_browse_directory")
            self.last_browse_directory = (
                str(last_directory).strip()
                if isinstance(last_directory, str) and last_directory.strip()
                else None
            )
        return self.config

    @staticmethod
    def _action_from_payload(item: dict) -> SyncAction:
        """Load legacy actions safely while writing only the profile schema."""
        payload = dict(item)
        legacy_method = payload.pop("method", None)
        if legacy_method == "two_way":
            raise ValueError(
                "Legacy two_way actions are not supported because they cannot reconcile "
                "conflicts safely. Recreate this action as backup or mirror."
            )
        if legacy_method == "one_way":
            payload.setdefault("profile", "backup")
            payload.setdefault("delete_policy", "keep_destination")
            payload.setdefault("conflict_policy", "source_wins")
        elif legacy_method is not None:
            raise ValueError(f"Unsupported legacy method: {legacy_method}")
        return SyncAction(**payload).normalize()

    def save(self, validate: bool = True) -> None:
        """Save configuration with optional validation.

        Args:
            validate: If True, run preflight validation before saving.
                     Raises ValueError if validation fails.
        """
        if validate and not self.skip_validation:
            is_valid, errors, warnings = self.validate()
            if not is_valid:
                error_lines = "\n".join("  - {}".format(e) for e in errors)
                raise ValueError("Configuration validation failed:\n" + error_lines)
            # Log warnings but don't block save
            for warning in warnings:
                _logger.warning("Config warning: %s", warning)

        data = {
            "sync_tool": self.config.sync_tool,
            "actions": [asdict(a) for a in self.config.actions],
            "ui_state": {"last_browse_directory": self.last_browse_directory},
        }
        with self.path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(data, handle, sort_keys=False)

    def export(self, target: Path, validate: bool = True) -> Path:
        """Export configuration to a file with optional validation."""
        if validate and not self.skip_validation:
            is_valid, errors, warnings = self.validate()
            if not is_valid:
                error_lines = "\n".join("  - {}".format(e) for e in errors)
                raise ValueError("Configuration validation failed:\n" + error_lines)
            for warning in warnings:
                _logger.warning("Config warning: %s", warning)

        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(
                {
                    "sync_tool": self.config.sync_tool,
                    "actions": [asdict(a) for a in self.config.actions],
                },
                handle,
                sort_keys=False,
            )
        return target

    def import_file(self, source: Path, validate: bool = True) -> SyncConfig:
        """Import configuration from a file with optional validation.

        Note: Validates imported config BEFORE mutating manager state to prevent
        partial state corruption on validation failure.
        """
        with source.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle)
        payload = {} if payload is None else payload
        if not isinstance(payload, dict):
            raise ValueError("Imported configuration must be a YAML mapping at the top level.")
        raw_actions = payload.get("actions", [])
        if not isinstance(raw_actions, list):
            raise ValueError("Imported configuration field 'actions' must be a list.")

        actions = []
        for index, item in enumerate(raw_actions):
            if not isinstance(item, dict):
                raise ValueError(
                    f"Imported configuration action at index {index} must be a mapping."
                )
            try:
                actions.append(self._action_from_payload(item))
            except (AttributeError, TypeError, ValueError) as exc:
                raise ValueError(
                    f"Imported configuration action at index {index} is invalid: {exc}"
                ) from exc

        # Create temporary config for validation (don't mutate self.config yet)
        temp_config = SyncConfig(sync_tool=payload.get("sync_tool", "rsync"), actions=actions)

        if validate and not self.skip_validation:
            # Validate the temp config before assigning
            validator = ConfigValidator()
            is_valid, errors, warnings = validator.validate_config(temp_config.actions)
            if not is_valid:
                error_lines = "\n".join("  - {}".format(e) for e in errors)
                raise ValueError("Configuration validation failed:\n" + error_lines)
            # Log warnings but don't block import
            for warning in warnings:
                _logger.warning("Config warning: %s", warning)

        # Only mutate state after validation passes
        self.config = temp_config
        self.save(validate=False)  # Already validated
        return self.config

    def remember_browse_directory(self, directory: str) -> None:
        """Persist the last filesystem location used by either directory picker."""
        value = str(directory).strip()
        if value and value != self.last_browse_directory:
            self.last_browse_directory = value
            self.save(validate=False)

    def ensure_default(self) -> None:
        if not self.config.actions:
            home = Path.home()
            docs = home / "Documents"
            fallback_src = home / "dir-sync-source"
            if docs.exists() and docs.is_dir():
                default_src = docs
            else:
                if fallback_src.exists():
                    if not fallback_src.is_dir():
                        raise ValueError(
                            f"Default source path '{fallback_src}' exists but is not a directory."
                        )
                else:
                    fallback_src.mkdir(parents=True, exist_ok=True)
                default_src = fallback_src

            dst_path = home / "dir-sync-backups"
            if dst_path.exists():
                if not dst_path.is_dir():
                    raise ValueError(
                        f"Default destination path '{dst_path}' exists but is not a directory."
                    )
            else:
                dst_path.mkdir(parents=True, exist_ok=True)

            sample = SyncAction(
                name="documents-backup",
                src_path=str(default_src),
                dst_path=str(dst_path / "documents"),
                profile="backup",
                action_type="manual",
            )
            self.config.add_action(sample)
            self.save(validate=False)

    def validate(self) -> Tuple[bool, List[str], List[str]]:
        """Validate entire configuration using preflight validation.

        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        validator = ConfigValidator()
        return validator.validate_config(self.config.actions)

    def _validate_actions(self, actions: List[SyncAction]) -> Tuple[bool, List[str], List[str]]:
        """Validate a prospective action list without mutating manager state."""
        validator = ConfigValidator()
        return validator.validate_config(actions)

    def add_action(self, action: SyncAction, validate: bool = True) -> None:
        """Add an action with optional validation."""
        save_validate = validate
        if validate and not self.skip_validation:
            is_valid, errors, warnings = action.validate()
            if not is_valid:
                raise ValueError(
                    "Action validation failed:\n" + "\n".join("  - {}".format(e) for e in errors)
                )

            candidate_config = deepcopy(self.config)
            candidate_config.add_action(deepcopy(action))
            is_valid, errors, warnings = self._validate_actions(candidate_config.actions)
            if not is_valid:
                error_lines = "\n".join("  - {}".format(e) for e in errors)
                raise ValueError("Configuration validation failed:\n" + error_lines)
            for warning in warnings:
                _logger.warning("Config warning: %s", warning)
            save_validate = False

        self.config.add_action(action)
        self.save(validate=save_validate)

    def update_action(self, action: SyncAction, validate: bool = True) -> None:
        """Update an action with optional validation."""
        save_validate = validate
        if validate and not self.skip_validation:
            is_valid, errors, warnings = action.validate()
            if not is_valid:
                raise ValueError(
                    "Action validation failed:\n" + "\n".join("  - {}".format(e) for e in errors)
                )

            candidate_config = deepcopy(self.config)
            candidate_config.update_action(deepcopy(action))
            is_valid, errors, warnings = self._validate_actions(candidate_config.actions)
            if not is_valid:
                error_lines = "\n".join("  - {}".format(e) for e in errors)
                raise ValueError("Configuration validation failed:\n" + error_lines)
            for warning in warnings:
                _logger.warning("Config warning: %s", warning)
            save_validate = False

        self.config.update_action(action)
        self.save(validate=save_validate)

    def remove_action(self, name: str, validate: bool = True) -> None:
        """Remove an action with optional validation of the resulting config."""
        save_validate = validate
        if validate and not self.skip_validation:
            candidate_config = deepcopy(self.config)
            candidate_config.remove_action(name)
            is_valid, errors, warnings = self._validate_actions(candidate_config.actions)
            if not is_valid:
                error_lines = "\n".join("  - {}".format(e) for e in errors)
                raise ValueError("Configuration validation failed:\n" + error_lines)
            for warning in warnings:
                _logger.warning("Config warning: %s", warning)
            save_validate = False

        self.config.remove_action(name)
        self.save(validate=save_validate)


__all__ = [
    "SyncAction",
    "SyncConfig",
    "ConfigManager",
]
