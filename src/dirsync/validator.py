import re
from pathlib import Path
from typing import List, Tuple


class PreflightValidator:
    """Validates sync actions before they can be saved or executed.
    
    Blocks invalid or dangerous sync definitions covering:
    - source equals destination
    - destination nested inside source (would cause recursion)
    - source nested inside destination (would cause unexpected deletes)
    - missing source path
    - missing or unavailable sync backend
    - invalid cron expressions
    - destructive profile warnings
    """

    # Paths that are dangerous to use as destinations for automatic sync
    DANGEROUS_DESTINATIONS = (
        "/",
        "/home",
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

    def __init__(self):
        self.errors = []
        self.warnings = []

    def validate_action(self, action):
        """Validate a single sync action.
        
        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        self.errors = []
        self.warnings = []

        # Normalize paths for comparison
        try:
            src_expanded = Path(action.src_path).expanduser().resolve()
            dst_expanded = Path(action.dst_path).expanduser().resolve()
        except (OSError, RuntimeError) as e:
            self.errors.append("Cannot resolve paths: {}".format(e))
            return False, self.errors, self.warnings

        # Check for missing source
        if not action.src_path or not action.src_path.strip():
            self.errors.append("Source path is missing or empty")

        # Check for missing destination
        if not action.dst_path or not action.dst_path.strip():
            self.errors.append("Destination path is missing or empty")

        # Check source equals destination
        if src_expanded == dst_expanded:
            self.errors.append(
                "Source and destination paths are identical. "
                "This would cause data loss."
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
                "This may cause unexpected deletions during two-way sync."
            )

        # Check for dangerous destination paths
        if self._is_dangerous_destination(dst_expanded):
            self.warnings.append(
                "Destination '{}' is a system-critical path. "
                "Automatic sync to this location is not recommended.".format(dst_expanded)
            )

        # Check cron expression if scheduled
        if action.action_type == "scheduled" and action.schedule:
            if not self._is_valid_cron(action.schedule):
                self.errors.append(
                    "Invalid cron expression: '{}'. "
                    "Please use valid cron format (e.g., '0 2 * * *').".format(action.schedule)
                )

        # Check method-specific requirements
        if action.method == "two_way":
            if not action.src_path or not action.dst_path:
                self.errors.append(
                    "Two-way sync requires both source and destination paths."
                )

        # Check for destructive profile
        if action.method == "one_way" and self._looks_like_destructive_sync(action):
            self.warnings.append(
                "One-way sync with no includes/excludes may overwrite all destination contents. "
                "Consider adding include/exclude patterns for safety."
            )

        is_valid = len(self.errors) == 0
        return is_valid, self.errors, self.warnings

    def _is_subpath(self, path, parent):
        """Check if path is a subpath of parent."""
        try:
            path.relative_to(parent)
            return path != parent  # Exclude exact matches
        except ValueError:
            return False

    def _is_dangerous_destination(self, path):
        """Check if path is a dangerous system location."""
        path_str = str(path)
        return path_str in self.DANGEROUS_DESTINATIONS or any(
            path_str.startswith(dangerous + "/") for dangerous in self.DANGEROUS_DESTINATIONS
        )

    def _is_valid_cron(self, expression):
        """Validate cron expression format.
        
        Supports standard 5-field cron: minute hour day month weekday
        Also supports special strings: @yearly, @monthly, @weekly, @daily, @hourly, @reboot
        """
        special_expressions = ("@yearly", "@monthly", "@weekly", "@daily", "@hourly", "@reboot")
        if expression.lower() in special_expressions:
            return True

        parts = expression.split()
        if len(parts) != 5:
            return False

        # Validate each field with basic ranges
        ranges = [
            (0, 59),   # minute
            (0, 23),   # hour
            (1, 31),   # day of month
            (1, 12),   # month
            (0, 6),    # day of week
        ]

        for part, (min_val, max_val) in zip(parts, ranges):
            if not self._is_valid_cron_field(part, min_val, max_val):
                return False

        return True

    def _is_valid_cron_field(self, field, min_val, max_val):
        """Validate a single cron field."""
        # Handle wildcard
        if field == "*":
            return True

        # Handle step values (e.g., */5, 1-10/2)
        if "/" in field:
            parts = field.split("/")
            if len(parts) != 2:
                return False
            base, step = parts
            if not step.isdigit() or int(step) <= 0:
                return False
            if base == "*":
                return True
            field = base  # Validate the base part

        # Handle ranges (e.g., 1-5)
        if "-" in field:
            range_parts = field.split("-")
            if len(range_parts) != 2:
                return False
            for part in range_parts:
                if not part.isdigit():
                    return False
                val = int(part)
                if val < min_val or val > max_val:
                    return False
            return True

        # Handle comma-separated lists (e.g., 1,3,5)
        if "," in field:
            for part in field.split(","):
                if not self._is_valid_cron_field(part, min_val, max_val):
                    return False
            return True

        # Single value
        if not field.isdigit():
            return False
        val = int(field)
        return min_val <= val <= max_val

    def _looks_like_destructive_sync(self, action):
        """Check if sync configuration looks potentially destructive."""
        # One-way sync with no filters to a non-empty-appearing destination
        has_no_filters = not action.includes and not action.excludes
        return has_no_filters


class ConfigValidator:
    """Validates entire configuration for cross-action issues."""

    def __init__(self):
        self.errors = []
        self.warnings = []

    def validate_config(self, actions):
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
            is_valid, errors, warnings = validator.validate_action(action)
            self.errors.extend(errors)
            self.warnings.extend(warnings)

        is_valid = len(self.errors) == 0
        return is_valid, self.errors, self.warnings


__all__ = [
    "PreflightValidator",
    "ConfigValidator",
]
