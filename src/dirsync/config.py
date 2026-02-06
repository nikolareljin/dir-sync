from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional

import yaml

from .constants import CONFIG_PATH, SUPPORTED_ACTION_TYPES, SUPPORTED_METHODS


@dataclass
class SyncAction:
    name: str
    src_path: str
    dst_path: str
    method: str = "two_way"
    action_type: str = "manual"
    schedule: Optional[str] = None  # cron format when action_type == scheduled
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
        return self


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
    def __init__(self, path: Path = CONFIG_PATH):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.config = SyncConfig()
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

    def save(self) -> None:
        data = {
            "sync_tool": self.config.sync_tool,
            "actions": [asdict(a) for a in self.config.actions],
        }
        with self.path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(data, handle, sort_keys=False)

    def export(self, target: Path) -> Path:
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

    def import_file(self, source: Path) -> SyncConfig:
        with source.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle)
        actions = [SyncAction(**item).normalize() for item in payload.get("actions", [])]
        self.config = SyncConfig(sync_tool=payload.get("sync_tool", "rsync"), actions=actions)
        self.save()
        return self.config

    def ensure_default(self) -> None:
        if not self.config.actions:
            sample = SyncAction(
                name="home-backup",
                src_path=str(Path.home()),
                dst_path=str(Path.home() / "dir-sync-backups"),
                method="one_way",
                action_type="manual",
            )
            self.config.actions.append(sample)
            self.save()


__all__ = [
    "SyncAction",
    "SyncConfig",
    "ConfigManager",
]
