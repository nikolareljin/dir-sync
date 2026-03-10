from __future__ import annotations

from contextlib import contextmanager

try:
    import tkinter as tk
    from tkinter import messagebox
except ModuleNotFoundError:  # pragma: no cover - optional in headless test environments
    tk = None
    messagebox = None


@contextmanager
def _hidden_root():
    if not tk:
        yield None
        return
    root = tk.Tk()
    root.withdraw()
    try:
        yield root
    finally:
        root.destroy()


def confirm(prompt: str, title: str = "Dir Sync") -> bool:
    if not messagebox:
        return False
    with _hidden_root():
        return messagebox.askyesno(title, prompt)


def alert(prompt: str, title: str = "Dir Sync") -> None:
    if not messagebox:
        return
    with _hidden_root():
        messagebox.showinfo(title, prompt)
