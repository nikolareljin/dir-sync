from __future__ import annotations

import copy
import datetime as dt
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, scrolledtext, ttk
from tkinter import font as tkfont

import psutil

from .config import ConfigManager, SyncAction
from .constants import SUPPORTED_PROFILES
from .detector import is_pseudo_mount, normalize_mountpoint
from .ui_dialogs import alert, confirm

TRIGGER_LABELS = {
    "manual": "Run manually",
    "auto_on_start": "When the app starts",
    "auto_on_destination": "When the backup drive connects",
    "scheduled": "On a schedule",
}
TRIGGER_VALUES = {label: value for value, label in TRIGGER_LABELS.items()}

RECURRENCE_LABELS = {
    "minutes": "Every N minutes",
    "daily": "Every day",
    "weekly": "Every week",
    "monthly": "Every month",
}
RECURRENCE_VALUES = {label: value for value, label in RECURRENCE_LABELS.items()}


class ConfigWindow:
    def __init__(self, manager: ConfigManager, parent: tk.Misc | None = None):
        self.manager = manager
        self.parent = parent

    def add_action(self) -> None:
        action = SyncAction(
            name="new-action",
            src_path="",
            dst_path="",
            profile="backup",
            action_type="manual",
        )
        self._open(action, create=True)

    def edit_action(self, name: str) -> None:
        action = self.manager.config.find_action(name)
        if not action:
            return
        self._open(copy.deepcopy(action), create=False)

    def _open(self, action: SyncAction, create: bool) -> None:
        if self.parent is None:
            raise RuntimeError("ConfigWindow requires a Tk parent to open a dialog")
        root = tk.Toplevel(self.parent)
        root.title(f"Dir Sync - {action.name}")
        root.geometry("820x640")
        root.minsize(760, 580)

        self._configure_native_style(root)

        editor_viewport = ttk.Frame(root)
        editor_viewport.grid(row=0, column=0, sticky="nsew")
        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(0, weight=1)

        editor_canvas = tk.Canvas(editor_viewport, highlightthickness=0)
        editor_scrollbar = ttk.Scrollbar(
            editor_viewport, orient=tk.VERTICAL, command=editor_canvas.yview
        )
        editor_canvas.configure(yscrollcommand=editor_scrollbar.set)
        editor_canvas.grid(row=0, column=0, sticky="nsew")
        editor_scrollbar.grid(row=0, column=1, sticky="ns")
        editor_viewport.grid_columnconfigure(0, weight=1)
        editor_viewport.grid_rowconfigure(0, weight=1)

        content = ttk.Frame(editor_canvas, padding=(14, 12))
        content_window = editor_canvas.create_window((0, 0), window=content, anchor="nw")

        def _sync_editor_scrollregion(_event=None):
            editor_canvas.configure(scrollregion=editor_canvas.bbox("all"))

        def _fit_editor_width(event):
            editor_canvas.itemconfigure(content_window, width=event.width)

        def _scroll_editor(event):
            if event.widget.winfo_class() == "Text":
                return
            if getattr(event, "num", None) == 4:
                editor_canvas.yview_scroll(-1, "units")
            elif getattr(event, "num", None) == 5:
                editor_canvas.yview_scroll(1, "units")
            elif event.delta:
                editor_canvas.yview_scroll(-int(event.delta / 120), "units")

        content.bind("<Configure>", _sync_editor_scrollregion)
        editor_canvas.bind("<Configure>", _fit_editor_width)
        root.bind_all("<MouseWheel>", _scroll_editor)
        root.bind_all("<Button-4>", _scroll_editor)
        root.bind_all("<Button-5>", _scroll_editor)

        ttk.Label(content, text="Action name").grid(row=0, column=0, columnspan=2, sticky="w")
        name_var = tk.StringVar(value=action.name)
        name_entry = ttk.Entry(content, textvariable=name_var)
        name_entry.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(2, 8))

        src_path_var = tk.StringVar(value=action.src_path)
        dst_path_var = tk.StringVar(value=action.dst_path)
        profile_var = tk.StringVar(value=action.profile)
        action_type_var = tk.StringVar(value=TRIGGER_LABELS[action.action_type])
        dst_device_id_var = tk.StringVar(value=action.dst_device_id or "")
        dst_path_on_device_var = tk.StringVar(value=action.dst_path_on_device or "")

        schedule_var = tk.StringVar(value=action.schedule or "")

        rule = action.schedule_rule or {}
        schedule_editor_var = tk.StringVar(
            value="guided" if rule or not action.schedule else "advanced"
        )
        recurrence_var = tk.StringVar(
            value=RECURRENCE_LABELS.get(rule.get("kind", "daily"), "Every day")
        )
        interval_var = tk.StringVar(value=str(rule.get("interval_minutes", 15)))
        time_parts = str(rule.get("time", "09:00")).split(":", 1)
        hour_var = tk.StringVar(value=time_parts[0])
        minute_var = tk.StringVar(value=time_parts[1] if len(time_parts) == 2 else "00")
        monthly_day_var = tk.StringVar(value=str(rule.get("day_of_month", 1)))
        weekday_vars = [
            tk.BooleanVar(value=index in rule.get("weekdays", [0])) for index in range(7)
        ]

        # SRC pane
        src_frame = ttk.LabelFrame(content, text="Source", padding=(10, 8))
        src_frame.grid(row=2, column=0, sticky="nsew", padx=(0, 6), pady=4)
        ttk.Label(src_frame, text="Directory").grid(row=0, column=0, sticky="w")
        ttk.Entry(src_frame, textvariable=src_path_var).grid(row=1, column=0, sticky="ew")
        ttk.Button(src_frame, text="Browse", command=lambda: self._choose_dir(src_path_var)).grid(
            row=1, column=1, padx=(6, 0)
        )
        src_frame.grid_columnconfigure(0, weight=1)

        # DST pane
        dst_frame = ttk.LabelFrame(content, text="Destination", padding=(10, 8))
        dst_frame.grid(row=2, column=1, sticky="nsew", padx=(6, 0), pady=4)
        ttk.Label(dst_frame, text="Directory").grid(row=0, column=0, sticky="w")
        ttk.Entry(dst_frame, textvariable=dst_path_var).grid(row=1, column=0, sticky="ew")
        ttk.Button(dst_frame, text="Browse", command=lambda: self._choose_dir(dst_path_var)).grid(
            row=1, column=1, padx=(6, 0)
        )
        ttk.Button(
            dst_frame,
            text="Create Dir",
            command=lambda: self._create_dir(dst_path_var),
        ).grid(row=1, column=2, padx=(6, 0))
        dst_frame.grid_columnconfigure(0, weight=1)

        def populate_drive_fields():
            available = self._available_mounts()
            if available:
                src_path_var.set(available[0])
                dst_path_var.set(available[-1])
            drives = list(psutil.disk_partitions(all=False))
            if drives:
                dst_device_id_var.set(drives[-1].device)

        button_row = ttk.Frame(content)
        button_row.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 6))
        button_row.grid_columnconfigure(0, weight=1)
        button_row.grid_columnconfigure(1, weight=1)

        ttk.Button(button_row, text="Detect Drives", command=populate_drive_fields).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Button(
            button_row,
            text="List USB IDs",
            command=lambda: self._open_usb_picker(root, dst_device_id_var, dst_path_var),
        ).grid(row=0, column=1, sticky="e")

        ttk.Label(content, text="Sync profile").grid(row=4, column=0, sticky="w")
        profile_combo = ttk.Combobox(content, textvariable=profile_var, values=SUPPORTED_PROFILES)
        profile_combo.state(["readonly"])
        profile_combo.grid(row=5, column=0, sticky="ew", padx=(0, 6), pady=(2, 6))
        ttk.Label(content, text="Backup keeps destination-only files. Mirror deletes them.").grid(
            row=6, column=0, columnspan=2, sticky="w", pady=(0, 6)
        )
        ttk.Label(content, text="When should it run?").grid(row=4, column=1, sticky="w")
        action_type_combo = ttk.Combobox(
            content, textvariable=action_type_var, values=tuple(TRIGGER_VALUES)
        )
        action_type_combo.state(["readonly"])
        action_type_combo.grid(row=5, column=1, sticky="ew", padx=(6, 0), pady=(2, 6))

        ttk.Label(content, text="Destination device ID (optional, for USB/HDD auto-match)").grid(
            row=9, column=0, columnspan=2, sticky="w"
        )
        ttk.Entry(content, textvariable=dst_device_id_var).grid(
            row=10, column=0, columnspan=2, sticky="ew", pady=(2, 8)
        )

        ttk.Label(content, text="Destination path on device (optional, e.g. backups/photos)").grid(
            row=7, column=0, columnspan=2, sticky="w"
        )
        ttk.Entry(content, textvariable=dst_path_on_device_var).grid(
            row=8, column=0, columnspan=2, sticky="ew", pady=(2, 8)
        )

        filter_frame = ttk.LabelFrame(
            content,
            text="File filters (one glob pattern per line)",
            padding=(8, 6),
        )
        filter_frame.grid(row=11, column=0, columnspan=2, sticky="nsew", pady=(2, 6))
        filter_frame.grid_columnconfigure(0, weight=1)
        filter_frame.grid_columnconfigure(1, weight=1)

        ttk.Label(filter_frame, text="Include patterns").grid(row=0, column=0, sticky="w", padx=4)
        includes_text = scrolledtext.ScrolledText(
            filter_frame,
            height=5,
            width=30,
            wrap=tk.NONE,
            font=tkfont.nametofont("TkTextFont"),
            borderwidth=1,
            relief=tk.SOLID,
        )
        includes_text.grid(row=1, column=0, sticky="ew", padx=4, pady=(0, 4))
        includes_text.insert("1.0", "\n".join(action.includes))

        ttk.Label(filter_frame, text="Exclude patterns").grid(row=0, column=1, sticky="w", padx=4)
        excludes_text = scrolledtext.ScrolledText(
            filter_frame,
            height=5,
            width=30,
            wrap=tk.NONE,
            font=tkfont.nametofont("TkTextFont"),
            borderwidth=1,
            relief=tk.SOLID,
        )
        excludes_text.grid(row=1, column=1, sticky="ew", padx=4, pady=(0, 4))
        excludes_text.insert("1.0", "\n".join(action.excludes))

        schedule_frame = ttk.LabelFrame(content, text="Schedule", padding=(8, 6))
        schedule_frame.grid(row=12, column=0, columnspan=2, sticky="nsew", pady=(2, 6))
        schedule_frame.grid_columnconfigure(0, weight=1)

        editor_row = ttk.Frame(schedule_frame)
        editor_row.grid(row=0, column=0, sticky="w", padx=5, pady=(0, 6))
        ttk.Radiobutton(
            editor_row,
            text="Guided schedule",
            variable=schedule_editor_var,
            value="guided",
        ).grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(
            editor_row,
            text="Advanced cron",
            variable=schedule_editor_var,
            value="advanced",
        ).grid(row=0, column=1, sticky="w", padx=(16, 0))

        guided_frame = ttk.Frame(schedule_frame)
        guided_frame.grid(row=1, column=0, sticky="ew", padx=5)
        guided_frame.grid_columnconfigure(1, weight=1)
        ttk.Label(guided_frame, text="Repeat").grid(row=0, column=0, sticky="w")
        recurrence_combo = ttk.Combobox(
            guided_frame,
            textvariable=recurrence_var,
            values=tuple(RECURRENCE_VALUES),
            state="readonly",
            width=16,
        )
        recurrence_combo.grid(row=0, column=1, sticky="w", padx=(8, 0))

        interval_frame = ttk.Frame(guided_frame)
        ttk.Label(interval_frame, text="Run every").grid(row=0, column=0, sticky="w")
        ttk.Spinbox(interval_frame, from_=1, to=59, textvariable=interval_var, width=5).grid(
            row=0, column=1, padx=6
        )
        ttk.Label(interval_frame, text="minutes").grid(row=0, column=2, sticky="w")

        time_frame = ttk.Frame(guided_frame)
        ttk.Label(time_frame, text="At").grid(row=0, column=0, sticky="w")
        ttk.Spinbox(
            time_frame, from_=0, to=23, format="%02.0f", textvariable=hour_var, width=4
        ).grid(row=0, column=1, padx=(6, 1))
        ttk.Label(time_frame, text=":").grid(row=0, column=2)
        ttk.Spinbox(
            time_frame, from_=0, to=59, format="%02.0f", textvariable=minute_var, width=4
        ).grid(row=0, column=3, padx=(1, 8))
        time_hint = ttk.Label(time_frame)
        time_hint.grid(row=0, column=4, sticky="w")

        weekdays_frame = ttk.Frame(guided_frame)
        ttk.Label(weekdays_frame, text="On").grid(row=0, column=0, sticky="w")
        for index, day in enumerate(("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")):
            ttk.Checkbutton(weekdays_frame, text=day, variable=weekday_vars[index]).grid(
                row=0, column=index + 1, padx=(6, 0)
            )

        monthly_frame = ttk.Frame(guided_frame)
        ttk.Label(monthly_frame, text="On day").grid(row=0, column=0, sticky="w")
        ttk.Spinbox(monthly_frame, from_=1, to=31, textvariable=monthly_day_var, width=4).grid(
            row=0, column=1, padx=6
        )
        ttk.Label(monthly_frame, text="(uses the last day in shorter months)").grid(
            row=0, column=2, sticky="w"
        )

        next_run_var = tk.StringVar()
        ttk.Label(guided_frame, textvariable=next_run_var).grid(
            row=5, column=0, columnspan=2, sticky="w", pady=(8, 0)
        )

        advanced_frame = ttk.Frame(schedule_frame)
        ttk.Label(advanced_frame, text="Cron expression").grid(row=0, column=0, sticky="w")
        custom_entry = ttk.Entry(advanced_frame, textvariable=schedule_var, width=42)
        custom_entry.grid(row=1, column=0, sticky="ew", pady=(2, 0))
        ttk.Label(
            advanced_frame,
            text="For existing or expert schedules. Guided changes replace this expression.",
        ).grid(row=2, column=0, sticky="w", pady=(4, 0))

        def _time_value() -> str:
            try:
                hour, minute = int(hour_var.get()), int(minute_var.get())
            except ValueError:
                return "00:00"
            return f"{max(0, min(23, hour)):02d}:{max(0, min(59, minute)):02d}"

        def _guided_rule() -> dict:
            kind = RECURRENCE_VALUES[recurrence_var.get()]
            if kind == "minutes":
                try:
                    interval = int(interval_var.get())
                except ValueError:
                    interval = 0
                return {"kind": kind, "interval_minutes": interval}
            rule = {"kind": kind, "time": _time_value()}
            if kind == "weekly":
                rule["weekdays"] = [
                    index for index, value in enumerate(weekday_vars) if value.get()
                ]
            if kind == "monthly":
                try:
                    rule["day_of_month"] = int(monthly_day_var.get())
                except ValueError:
                    rule["day_of_month"] = 0
            return rule

        def _update_schedule_editor(*_args):
            guided_frame.grid_remove()
            advanced_frame.grid_remove()
            if schedule_editor_var.get() == "advanced":
                advanced_frame.grid(row=1, column=0, sticky="ew", padx=5)
                return
            guided_frame.grid()
            kind = RECURRENCE_VALUES[recurrence_var.get()]
            interval_frame.grid_forget()
            time_frame.grid_forget()
            weekdays_frame.grid_forget()
            monthly_frame.grid_forget()
            if kind == "minutes":
                interval_frame.grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))
                next_run_var.set("Runs on the next matching local-time minute.")
                return
            time_frame.grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))
            if kind == "weekly":
                weekdays_frame.grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))
            elif kind == "monthly":
                monthly_frame.grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))
            try:
                from .scheduler import ActionScheduler

                next_run = ActionScheduler._next_rule_time(_guided_rule(), dt.datetime.now())
                next_run_var.set(f"Next run: {next_run:%a, %d %b %Y at %H:%M}")
            except (KeyError, TypeError, ValueError):
                next_run_var.set("Choose a valid local time and recurrence.")
            try:
                hour, minute = map(int, _time_value().split(":"))
                suffix = "AM" if hour < 12 else "PM"
                display_hour = hour % 12 or 12
                time_hint.configure(text=f"({display_hour}:{minute:02d}{suffix.lower()})")
            except ValueError:
                time_hint.configure(text="")

        def _toggle_schedule_visibility(*_args):
            if action_type_var.get() == TRIGGER_LABELS["scheduled"]:
                schedule_frame.grid()
                _update_schedule_editor()
            else:
                schedule_frame.grid_remove()

        for variable in (
            schedule_editor_var,
            recurrence_var,
            interval_var,
            hour_var,
            minute_var,
            monthly_day_var,
        ):
            variable.trace_add("write", _update_schedule_editor)
        for variable in weekday_vars:
            variable.trace_add("write", _update_schedule_editor)
        action_type_var.trace_add("write", _toggle_schedule_visibility)
        _toggle_schedule_visibility()

        button_text = "Create" if create else "Save"

        def _parse_patterns(text_widget: tk.Text) -> list[str]:
            raw = text_widget.get("1.0", "end").strip()
            return [line.strip() for line in raw.splitlines() if line.strip()]

        def on_submit():
            payload = SyncAction(
                name=name_var.get().strip(),
                src_path=src_path_var.get().strip(),
                dst_path=dst_path_var.get().strip(),
                profile=profile_var.get(),
                delete_policy=(
                    "delete_destination_extras"
                    if profile_var.get() == "mirror"
                    else "keep_destination"
                ),
                conflict_policy="source_wins",
                action_type=TRIGGER_VALUES[action_type_var.get()],
                schedule=(
                    schedule_var.get().strip()
                    if action_type_var.get() == TRIGGER_LABELS["scheduled"]
                    and schedule_editor_var.get() == "advanced"
                    else None
                ),
                schedule_rule=(
                    _guided_rule()
                    if action_type_var.get() == TRIGGER_LABELS["scheduled"]
                    and schedule_editor_var.get() == "guided"
                    else None
                ),
                includes=_parse_patterns(includes_text),
                excludes=_parse_patterns(excludes_text),
                dst_device_id=dst_device_id_var.get().strip() or None,
                dst_path_on_device=dst_path_on_device_var.get().strip() or None,
            )
            if payload.profile == "mirror" and not confirm(
                "Mirror deletes files that exist only at the destination. Continue?",
                title="Enable destructive mirror",
            ):
                return
            try:
                if create:
                    self.manager.add_action(payload)
                else:
                    self.manager.update_action(payload)
            except ValueError as exc:
                alert(str(exc))
                return
            root.destroy()

        def on_delete():
            if create:
                root.destroy()
                return
            try:
                self.manager.remove_action(action.name)
            except ValueError as exc:
                alert(str(exc))
                return
            root.destroy()

        action_buttons = ttk.Frame(content)
        action_buttons.grid(row=13, column=0, columnspan=2, sticky="e", pady=(8, 0))
        ttk.Button(action_buttons, text=button_text, command=on_submit).grid(
            row=0, column=0, padx=(0, 8)
        )
        ttk.Button(action_buttons, text="Cancel", command=root.destroy).grid(row=0, column=1)
        if not create:
            ttk.Button(action_buttons, text="Delete", command=on_delete).grid(
                row=0, column=2, padx=(8, 0)
            )

        content.grid_columnconfigure(0, weight=1)
        content.grid_columnconfigure(1, weight=1)

        self._fit_window_to_content(root, min_width=760, min_height=580)
        root.lift()
        root.focus_force()

    def _choose_dir(self, variable: tk.StringVar) -> None:
        initial_directory = self._picker_initial_directory(variable.get())
        path = filedialog.askdirectory(initialdir=str(initial_directory), mustexist=True)
        if path:
            variable.set(path)
            self.manager.remember_browse_directory(path)

    def _picker_initial_directory(self, value: str) -> Path:
        """Pick a useful filesystem location without falling back to the process cwd."""
        candidate = Path(value).expanduser() if value.strip() else None
        if candidate and candidate.is_absolute():
            if candidate.is_dir():
                return candidate
            if candidate.parent.is_dir():
                return candidate.parent
        remembered = self.manager.last_browse_directory
        if remembered:
            remembered_path = Path(remembered).expanduser()
            if remembered_path.is_absolute() and remembered_path.is_dir():
                return remembered_path
        return Path.home()

    def _create_dir(self, variable: tk.StringVar) -> None:
        path = variable.get().strip()
        if not path:
            alert("Destination path is empty. Enter a path first.")
            return
        try:
            Path(path).mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            alert(f"Could not create directory:\n{path}\n\n{exc}")
            return
        alert(f"Directory is ready:\n{path}")

    def _open_usb_picker(
        self,
        parent: tk.Tk,
        dst_device_id_var: tk.StringVar,
        dst_path_var: tk.StringVar,
    ) -> None:
        drives = self._discover_drives()
        usb_drives = [drive for drive in drives if drive["removable"]]
        if not usb_drives:
            alert("No removable USB/HDD devices detected.")
            return

        dialog = tk.Toplevel(parent)
        dialog.title("Detected USB/HDD IDs")
        dialog.geometry("760x260")

        columns = ("volume_id", "device", "mountpoint")
        tree = ttk.Treeview(dialog, columns=columns, show="headings", height=8)
        tree.heading("volume_id", text="Device ID")
        tree.heading("device", text="Device")
        tree.heading("mountpoint", text="Mountpoint")
        tree.column("volume_id", width=180)
        tree.column("device", width=180)
        tree.column("mountpoint", width=360)
        tree.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=8, pady=8)

        for drive in usb_drives:
            tree.insert(
                "",
                "end",
                values=(drive["volume_id"], drive["device"], drive["mountpoint"]),
            )

        def apply_selected():
            selection = tree.selection()
            if not selection:
                return
            volume_id, _, mountpoint = tree.item(selection[0], "values")
            dst_device_id_var.set(volume_id)
            if not dst_path_var.get().strip():
                dst_path_var.set(mountpoint)
            dialog.destroy()

        ttk.Button(dialog, text="Use Selected", command=apply_selected).grid(
            row=1, column=0, sticky="w", padx=8, pady=8
        )
        ttk.Button(dialog, text="Close", command=dialog.destroy).grid(
            row=1, column=1, sticky="e", padx=8, pady=8
        )

        dialog.grid_rowconfigure(0, weight=1)
        dialog.grid_columnconfigure(0, weight=1)
        dialog.grid_columnconfigure(1, weight=1)

    def _available_mounts(self) -> list[str]:
        drives = []
        for part in psutil.disk_partitions(all=True):
            if not part.mountpoint:
                continue
            if is_pseudo_mount(part):
                continue
            drives.append(normalize_mountpoint(part.mountpoint))
        return drives

    def _discover_drives(self) -> list[dict[str, str | bool]]:
        discovered: list[dict[str, str | bool]] = []
        for part in psutil.disk_partitions(all=False):
            mountpoint = part.mountpoint.rstrip("/\\")
            device = part.device
            discovered.append(
                {
                    "mountpoint": mountpoint,
                    "device": device,
                    "volume_id": self._resolve_volume_id(device),
                    "removable": self._is_removable(device),
                }
            )
        return discovered

    def _resolve_volume_id(self, device: str) -> str:
        if not device:
            return ""
        by_uuid = Path("/dev/disk/by-uuid")
        resolved = Path(device).resolve()
        if by_uuid.exists():
            for entry in by_uuid.iterdir():
                try:
                    if entry.resolve() == resolved:
                        return entry.name
                except OSError:
                    continue
        return device

    def _is_removable(self, device: str) -> bool:
        if not device.startswith("/dev/"):
            return False

        leaf = Path(device).name
        candidates = [leaf]
        if leaf and leaf[-1].isdigit():
            candidates.append(leaf.rstrip("0123456789"))
            candidates.append(leaf.rstrip("0123456789p"))

        for name in candidates:
            sys_path = Path("/sys/class/block") / name / "removable"
            if not sys_path.exists():
                continue
            try:
                return sys_path.read_text(encoding="utf-8").strip() == "1"
            except OSError:
                return False
        return False

    def _fit_window_to_content(self, root: tk.Tk, min_width: int, min_height: int) -> None:
        root.update_idletasks()
        max_height = max(480, root.winfo_screenheight() - 80)
        root.minsize(min_width, min(min_height, max_height))
        width = max(min_width, root.winfo_reqwidth() + 20)
        height = min(max_height, max(min_height, root.winfo_reqheight() + 20))
        root.geometry(f"{width}x{height}")

    def _configure_native_style(self, root: tk.Tk) -> None:
        style = ttk.Style(root)
        themes = style.theme_names()
        preferred_themes: list[str]
        if sys.platform.startswith("win"):
            preferred_themes = ["vista", "xpnative", "winnative", "default"]
        elif sys.platform == "darwin":
            preferred_themes = ["aqua", "default"]
        else:
            preferred_themes = ["default", "alt", "clam"]

        for theme in preferred_themes:
            if theme in themes:
                style.theme_use(theme)
                break

        default_font = tkfont.nametofont("TkDefaultFont")
        heading_font = default_font.copy()
        heading_font.configure(weight="bold")
        root.option_add("*Font", default_font)
        style.configure("TLabelframe.Label", font=heading_font)
