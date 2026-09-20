from __future__ import annotations

import sys
import tkinter as tk

from .config import ConfigManager
from .ui_about import show_about
from .ui_config import ConfigWindow


def main(arguments: list[str] | None = None) -> None:
    arguments = arguments or sys.argv[1:]
    if not arguments or arguments[0] not in {"add", "edit", "about"}:
        raise SystemExit("Usage: --ui-process {add|edit <action-name>|about}")

    root = tk.Tk()
    root.withdraw()
    command = arguments[0]
    if command == "about":
        show_about(root)
    else:
        manager = ConfigManager()
        manager.ensure_default()
        window = ConfigWindow(manager, root)
        if command == "add":
            window.add_action()
        else:
            if len(arguments) != 2:
                raise SystemExit("Usage: --ui-process edit <action-name>")
            window.edit_action(arguments[1])
    root.mainloop()
