from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from croniter import croniter

from .constants import IS_WINDOWS

if TYPE_CHECKING:
    from .config import SyncAction


class PreflightValidator:
    """Validates sync actions before they can be saved or imported.

    Blocks invalid or dangerous sync definitions covering:
    - source equals destination
    - destination nested inside source (would cause recursion)
    - source nested inside destination (would cause unexpected deletes)
    - missing source path
    - invalid cron expressions
    - destructive profile warnings
    """

    # Paths that are dangerous to use as destinations and should trigger warnings.
    # Note: Excludes /home to avoid false positives for normal user destinations.
    # On Windows, dangerous system paths are handled via WINDOWS_DANGEROUS_DESTINATIONS.
    DANGEROUS_DESTINATIONS = (
        "/",
        "/etc",
        "/usr",
        "/var",
        "/bin",
        "/sbin",
        "/boot",
        "/dev",
        "/proc",
        "/sys",
    )

    # Windows dangerous paths
    WINDOWS_DANGEROUS_DESTINATIONS = (
        "C:\\Windows",
        "C:\\Program Files",
        "C:\\Program Files (x86)",
        "C:\\ProgramData",
        "C:\\Users\\Public",
    )

    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def validate_action(self, action: SyncAction) -> tuple[bool, list[str], list[str]]:
        """Validate a single sync action.

        Args:
            action: SyncAction to validate

        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        self.errors = []
        self.warnings = []

        # Check for missing/empty source FIRST (before path resolution)
        if not action.src_path or not str(action.src_path).strip():
            self.errors.append("Source path is missing or empty")

        # Check for missing/empty destination FIRST (before path resolution)
        if not action.dst_path or not str(action.dst_path).strip():
            self.errors.append("Destination path is missing or empty")

        # If we have empty paths, return early to avoid misleading errors
        if (
            not action.src_path
            or not str(action.src_path).strip()
            or not action.dst_path
            or not str(action.dst_path).strip()
        ):
            return False, self.errors, self.warnings

        # Normalize paths for comparison
        try:
            src_expanded = Path(action.src_path).expanduser().resolve()
            dst_expanded = Path(action.dst_path).expanduser().resolve()
        except (OSError, RuntimeError) as e:
            self.errors.append("Cannot resolve paths: {}".format(e))
            return False, self.errors, self.warnings

        # Check source path exists (destination can be created by executor)
        if not src_expanded.exists():
            self.errors.append(
                "Source path does not exist: '{}'. "
                "Please ensure the source directory exists before creating a sync action.".format(
                    src_expanded
                )
            )
        elif not src_expanded.is_dir():
            self.errors.append(
                "Source path must be a directory: '{}'. "
                "File sources are not supported by the sync executor.".format(src_expanded)
            )

        # If destination exists, it must also be a directory.
        if dst_expanded.exists() and not dst_expanded.is_dir():
            self.errors.append(
                "Destination path must be a directory when it already exists: '{}'.".format(
                    dst_expanded
                )
            )

        # Check source equals destination
        if src_expanded == dst_expanded:
            self.errors.append(
                "Source and destination paths are identical. " "This would cause data loss."
            )

        # Check destination nested inside source (recursion risk)
        if self._is_subpath(dst_expanded, src_expanded):
            self.errors.append(
                "Destination is nested inside source. "
                "This would cause infinite recursion during sync."
            )

        # Check source nested inside destination (unexpected deletes risk)
        if self._is_subpath(src_expanded, dst_expanded):
            self.errors.append(
                "Source is nested inside destination. "
                "This may cause unexpected deletions during sync."
            )

        # Check for dangerous destination paths
        if self._is_dangerous_destination(dst_expanded):
            self.warnings.append(
                "Destination '{}' is a system-critical path. "
                "Syncing to this location is not recommended.".format(dst_expanded)
            )

        # A scheduled action is either a guided rule or an advanced raw cron expression.
        if action.action_type == "scheduled":
            if action.schedule_rule is not None:
                self._validate_schedule_rule(action.schedule_rule)
            elif not action.schedule or not str(action.schedule).strip():
                self.errors.append(
                    "Scheduled action requires a recurrence or a valid cron expression."
                )
            else:
                schedule = str(action.schedule).strip()
                try:
                    croniter(schedule)
                except (KeyError, TypeError, ValueError) as exc:
                    self.errors.append(
                        "Invalid cron expression: '{}'. Croniter error: {}.".format(schedule, exc)
                    )

        # Mirror intentionally deletes destination-only files and needs a clear warning.
        if action.profile == "mirror":
            self.warnings.append(
                "Mirror deletes destination-only files so the destination exactly "
                "matches the source."
            )

        is_valid = len(self.errors) == 0
        return is_valid, self.errors, self.warnings

    def _validate_schedule_rule(self, rule: dict) -> None:
        kind = rule.get("kind")
        if kind not in {"minutes", "daily", "weekly", "monthly"}:
            self.errors.append("Schedule recurrence must be minutes, daily, weekly, or monthly.")
            return
        if kind == "minutes":
            interval = rule.get("interval_minutes")
            if type(interval) is not int or not 1 <= interval <= 59:
                self.errors.append("Minute recurrence must be between 1 and 59 minutes.")
            return
        time_value = rule.get("time")
        if not isinstance(time_value, str) or not re.fullmatch(
            r"(?:[01]\d|2[0-3]):[0-5]\d", time_value
        ):
            self.errors.append("Scheduled time must use 24-hour HH:MM format.")
        if kind == "weekly":
            weekdays = rule.get("weekdays")
            if (
                not isinstance(weekdays, list)
                or not weekdays
                or any(type(day) is not int or day not in range(7) for day in weekdays)
            ):
                self.errors.append("Weekly recurrence requires one or more weekdays.")
        if kind == "monthly":
            day = rule.get("day_of_month")
            if type(day) is not int or not 1 <= day <= 31:
                self.errors.append("Monthly recurrence requires a day between 1 and 31.")

    def _is_subpath(self, path: Path, parent: Path) -> bool:
        """Check if path is a subpath of parent."""
        try:
            path.relative_to(parent)
            return path != parent  # Exclude exact matches
        except ValueError:
            return False

    def _is_dangerous_destination(self, path: Path) -> bool:
        """Check if path is a dangerous system location.

        Handles both Unix-style paths and Windows paths.
        """
        path_str = str(path)

        # Check Unix-style dangerous destinations
        if path_str in self.DANGEROUS_DESTINATIONS or any(
            path_str.startswith(dangerous + "/") for dangerous in self.DANGEROUS_DESTINATIONS
        ):
            return True

        # Check Windows-style dangerous destinations
        if IS_WINDOWS:
            path_upper = path_str.upper()
            for dangerous in self.WINDOWS_DANGEROUS_DESTINATIONS:
                dangerous_upper = dangerous.upper()
                if path_upper == dangerous_upper or path_upper.startswith(dangerous_upper + "\\"):
                    return True

        return False


class ConfigValidator:
    """Validates entire configuration for cross-action issues."""

    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def validate_config(self, actions: list[SyncAction]) -> tuple[bool, list[str], list[str]]:
        """Validate a list of sync actions for cross-action issues.

        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        self.errors = []
        self.warnings = []

        action_names = set()
        for action in actions:
            # Check for duplicate action names
            if action.name in action_names:
                self.errors.append("Duplicate action name: '{}'".format(action.name))
            action_names.add(action.name)

            # Validate individual action
            validator = PreflightValidator()
            _is_valid, errors, warnings = validator.validate_action(action)
            # Prefix errors and warnings with action name for clarity
            for err in errors:
                self.errors.append("Action '{}': {}".format(action.name, err))
            for warn in warnings:
                self.warnings.append("Action '{}': {}".format(action.name, warn))

        is_valid = len(self.errors) == 0
        return is_valid, self.errors, self.warnings


__all__ = [
    "PreflightValidator",
    "ConfigValidator",
]
