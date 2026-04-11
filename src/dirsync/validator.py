from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from croniter import croniter

from .constants import IS_WINDOWS

if TYPE_CHECKING:
    from .config import SyncAction


class PreflightValidator:
    """Validates sync actions before they can be saved or executed.

    Blocks invalid or dangerous sync definitions covering:
    - source equals destination
    - destination nested inside source (would cause recursion)
    - source nested inside destination (would cause unexpected deletes)
    - missing source path
    - invalid cron expressions
    - destructive profile warnings
    """

    # Paths that are dangerous to use as destinations for automatic sync.
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
                "Automatic sync to this location is not recommended.".format(dst_expanded)
            )

        # Check cron expression if scheduled
        if action.action_type == "scheduled":
            # If action_type is scheduled, schedule must be provided and valid
            if not action.schedule or not str(action.schedule).strip():
                self.errors.append(
                    "Scheduled action requires a valid cron expression. "
                    "Please provide a schedule (e.g., '0 2 * * *')."
                )
            else:
                schedule = str(action.schedule).strip()

                # Use croniter to validate cron expressions for compatibility with runtime scheduler
                try:
                    croniter(schedule)
                except (KeyError, TypeError, ValueError) as e:
                    self.errors.append(
                        "Invalid cron expression: '{}'. "
                        "Croniter error: {}. "
                        "Please use valid cron format (e.g., '0 2 * * *').".format(
                            schedule, e
                        )
                    )

        # Check for destructive profile
        if action.method == "one_way" and self._looks_like_destructive_sync(action):
            self.warnings.append(
                "One-way sync with no includes/excludes may overwrite all destination contents. "
                "Consider adding include/exclude patterns for safety."
            )

        is_valid = len(self.errors) == 0
        return is_valid, self.errors, self.warnings

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

    def _looks_like_destructive_sync(self, action: SyncAction) -> bool:
        """Check if sync configuration looks potentially destructive."""
        # Current heuristic: flag syncs with no include/exclude filters.
        has_no_filters = not action.includes and not action.excludes
        return has_no_filters


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
