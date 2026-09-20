from __future__ import annotations

import tkinter as tk
from threading import Event
from typing import Callable, TypeVar

try:
    from gi.repository import GLib
except ImportError:  # pragma: no cover - only absent on non-GTK platforms
    GLib = None

T = TypeVar("T")


class UiDispatcher:
    """Run Tk and the GTK event context together on the main thread."""

    def __init__(self) -> None:
        self.root: tk.Tk | None = None

    def start(self) -> None:
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.after(25, self._pump_gtk)

    def run(self) -> None:
        if not self.root:
            raise RuntimeError("UI dispatcher has not been started")
        self.root.mainloop()

    def dispatch(self, task: Callable[[], None]) -> None:
        if not self.root:
            raise RuntimeError("UI dispatcher has not been started")
        self.root.after(0, task)

    def call(self, task: Callable[[], T]) -> T:
        complete = Event()
        result: list[T] = []
        errors: list[BaseException] = []

        def wrapped() -> None:
            try:
                result.append(task())
            except BaseException as exc:  # pragma: no cover - re-raised by caller
                errors.append(exc)
            finally:
                complete.set()

        self.dispatch(wrapped)
        complete.wait()
        if errors:
            raise errors[0]
        return result[0]

    def stop(self) -> None:
        if self.root:
            self.root.after(0, self._destroy)

    def _destroy(self) -> None:
        if self.root:
            self.root.destroy()
            self.root = None

    def _pump_gtk(self) -> None:
        if not self.root:
            return
        if GLib:
            context = GLib.MainContext.default()
            while context.pending():
                context.iteration(False)
        if self.root:
            self.root.after(25, self._pump_gtk)
