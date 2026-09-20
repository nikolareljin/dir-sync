from __future__ import annotations

import tkinter as tk
import webbrowser
from tkinter import ttk

from .version import get_app_version

DOCUMENTATION_URL = "https://nikolareljin.github.io/dir-sync/"
SOURCE_URL = "https://github.com/nikolareljin/dir-sync"


def show_about(parent: tk.Misc) -> None:
    """Open the native application about dialog."""
    dialog = tk.Toplevel(parent)
    dialog.title("About Dir Sync")
    dialog.resizable(False, False)

    content = ttk.Frame(dialog, padding=(24, 20))
    content.grid(sticky="nsew")
    ttk.Label(content, text="Dir Sync", font=("TkDefaultFont", 16, "bold")).grid(
        row=0, column=0, sticky="w"
    )
    ttk.Label(content, text=f"Version {get_app_version()}").grid(row=1, column=0, sticky="w")
    ttk.Label(
        content,
        text="Safe directory backup and synchronization for local folders and drives.",
        wraplength=380,
    ).grid(row=2, column=0, sticky="w", pady=(12, 4))
    ttk.Label(content, text="Created by Nik Reljin").grid(row=3, column=0, sticky="w")
    ttk.Label(content, text="MIT License").grid(row=4, column=0, sticky="w")

    buttons = ttk.Frame(content)
    buttons.grid(row=5, column=0, sticky="e", pady=(18, 0))
    ttk.Button(
        buttons, text="Documentation", command=lambda: webbrowser.open(DOCUMENTATION_URL)
    ).grid(row=0, column=0, padx=(0, 8))
    ttk.Button(buttons, text="Source", command=lambda: webbrowser.open(SOURCE_URL)).grid(
        row=0, column=1, padx=(0, 8)
    )
    ttk.Button(buttons, text="Close", command=dialog.destroy).grid(row=0, column=2)

    dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
    dialog.grab_set()
    dialog.lift()
    dialog.focus_force()
