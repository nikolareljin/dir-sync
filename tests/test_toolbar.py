from __future__ import annotations

import os
from unittest.mock import Mock

os.environ.setdefault("PYSTRAY_BACKEND", "dummy")

from dirsync.toolbar import ToolbarController


def test_edit_action_launches_a_separate_gui_process() -> None:
    controller = object.__new__(ToolbarController)
    controller._launch_ui = Mock()

    callback = controller._make_editor("backup")
    callback(None, None)

    controller._launch_ui.assert_called_once_with("edit", "backup")
