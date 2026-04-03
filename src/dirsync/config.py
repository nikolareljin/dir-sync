from __future__ import annotations

import logging
import os
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

import yaml

from .constants import CONFIG_PATH, SUPPORTED_ACTION_TYPES, SUPPORTED_METHODS
from .validator import ConfigValidator, PreflightValidator

# Use module-level logger for consistent logging
_logger = logging.getLogger(__name__)


@dataclass
class SyncAction:
    name: str
    src_path: str
    dst_path: str
    method: str = "two_way"
    action_type: str = "manual"
    schedule: Optional[str] = None  # cron format when action_type == scheduled
    includes: List[str] = field(default_factory=list)  # glob patterns to include
    excludes: List[str] = field(default_factory=list)  # glob patterns to exclude
    dst_device_id: Optional[str] = None
    dst_path_on_device: Optional[str] = None

    def normalize(self) -> "SyncAction":
        self.src_path = os.path.expanduser(self.src_path)
        self.dst_path = os.path.expanduser(self.dst_path)
        self.dst_device_id = (self.dst_device_id or "").strip() or None
        self.dst_path_on_device = (self.dst_path_on_device or "").strip() or None
        if self.method not in SUPPORTED_METHODS:
            raise ValueError(f"Unsupported method: {self.method}")
        if self.action_type not in SUPPORTED_ACTION_TYPES:
            raise ValueError(f"Unsupported action type: {self.action_type}")
        if self.action_type != "scheduled":
            self.schedule = None
        self.includes = [p.strip() for p in self.includes if p.strip()]
        self.excludes = [p.strip() for p in self.excludes if p.strip()]
        return self

    def validate(self) -> Tuple[bool, List[str], List[str]]:
        """Validate this action using preflight validation.

        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        validator = PreflightValidator()
        return validator.validate_action(self)


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
        self.skip_validation = skip_validation
        if self.path.exists():
            self.load()
        else:
            self.save()

    def load(self) -> SyncConfig:
        with self.path.open("r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle) or {}
        actions = [SyncAction(**item).normalize() for item in raw.get("actions", [])]
        self.config = SyncConfig(sync_tool=raw.get("sync_tool", "rsync"), actions=actions)
        return self.config

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
            payload = yaml.safe_load(handle) or {}  # Default to empty dict if file is empty
        actions = [SyncAction(**item).normalize() for item in payload.get("actions", [])]

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

    def ensure_default(self) -> None:
        if not self.config.actions:
            home = Path.home()
            docs = home / "Documents"
            fallback_src = home / "dir-sync-source"
            if docs.exists() and docs.is_dir():
                default_src = docs
            else:
                try:
                    docs.mkdir(parents=True, exist_ok=True)
                    default_src = docs
                except OSError:
                    fallback_src.mkdir(parents=True, exist_ok=True)
                    default_src = fallback_src

            dst_path = home / "dir-sync-backups"
            if not dst_path.exists():
                dst_path.mkdir(parents=True, exist_ok=True)

            sample = SyncAction(
                name="documents-backup",
                src_path=str(default_src),
                dst_path=str(dst_path / "documents"),
                method="one_way",
                action_type="manual",
            )
            self.add_action(sample, validate=not self.skip_validation)

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
        if validate and not self.skip_validation:
            is_valid, errors, warnings = action.validate()
            if not is_valid:
                raise ValueError(
                    "Action validation failed:\n" + "\n".join("  - {}".format(e) for e in errors)
                )
            for warning in warnings:
                _logger.warning("Action '%s' warning: %s", action.name, warning)

            candidate_config = deepcopy(self.config)
            candidate_config.add_action(deepcopy(action))
            is_valid, errors, warnings = self._validate_actions(candidate_config.actions)
            if not is_valid:
                error_lines = "\n".join("  - {}".format(e) for e in errors)
                raise ValueError("Configuration validation failed:\n" + error_lines)
            for warning in warnings:
                _logger.warning("Config warning: %s", warning)

        self.config.add_action(action)
        self.save(validate=validate)

    def update_action(self, action: SyncAction, validate: bool = True) -> None:
        """Update an action with optional validation."""
        if validate and not self.skip_validation:
            is_valid, errors, warnings = action.validate()
            if not is_valid:
                raise ValueError(
                    "Action validation failed:\n" + "\n".join("  - {}".format(e) for e in errors)
                )
            for warning in warnings:
                _logger.warning("Action '%s' warning: %s", action.name, warning)

            candidate_config = deepcopy(self.config)
            candidate_config.update_action(deepcopy(action))
            is_valid, errors, warnings = self._validate_actions(candidate_config.actions)
            if not is_valid:
                error_lines = "\n".join("  - {}".format(e) for e in errors)
                raise ValueError("Configuration validation failed:\n" + error_lines)
            for warning in warnings:
                _logger.warning("Config warning: %s", warning)

        self.config.update_action(action)
        self.save(validate=validate)

    def remove_action(self, name: str, validate: bool = True) -> None:
        """Remove an action with optional validation of the resulting config."""
        if validate and not self.skip_validation:
            candidate_config = deepcopy(self.config)
            candidate_config.remove_action(name)
            is_valid, errors, warnings = self._validate_actions(candidate_config.actions)
            if not is_valid:
                error_lines = "\n".join("  - {}".format(e) for e in errors)
                raise ValueError("Configuration validation failed:\n" + error_lines)
            for warning in warnings:
                _logger.warning("Config warning: %s", warning)

        self.config.remove_action(name)
        self.save(validate=validate)


__all__ = [
    "SyncAction",
    "SyncConfig",
    "ConfigManager",
]
