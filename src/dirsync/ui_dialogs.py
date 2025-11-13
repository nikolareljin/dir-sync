from __future__ import annotations

import tkinter as tk
from contextlib import contextmanager
from tkinter import messagebox


@contextmanager
def _hidden_root():
    root = tk.Tk()
    root.withdraw()
    try:
        yield root
    finally:
        root.destroy()


def confirm(prompt: str, title: str = "Dir Sync") -> bool:
    with _hidden_root():
        return messagebox.askyesno(title, prompt)


def alert(prompt: str, title: str = "Dir Sync") -> None:
    with _hidden_root():
        messagebox.showinfo(title, prompt)
