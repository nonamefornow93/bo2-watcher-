#!/usr/bin/env python3
"""BO2 launch-status label.

A tiny always-on-top, borderless widget that shows whether Call of Duty:
Black Ops II is currently running. Green = launched, red = not.

Controls:
    Left-click + drag : move the label
    Right-click       : quit
    Escape            : quit

Run:  python bo2_status_label.py
"""
from __future__ import annotations

import tkinter as tk

from bo2_achievement_watcher import bo2_running, progress

POLL_MS = 2000

COLOR_ON = "#1db954"     # green
COLOR_OFF = "#c0392b"    # red


class StatusLabel:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.overrideredirect(True)                 # borderless
        root.attributes("-topmost", True)           # always on top
        try:
            root.attributes("-alpha", 0.92)         # slight transparency
        except tk.TclError:
            pass

        text0, bg0 = self._render(bool(bo2_running()))
        self.label = tk.Label(
            root,
            text=text0,
            bg=bg0,
            fg="white",
            font=("Segoe UI", 12, "bold"),
            padx=16,
            pady=8,
            cursor="fleur",
        )
        self.label.pack()

        # Start near the top-right of the primary screen.
        root.update_idletasks()
        sw = root.winfo_screenwidth()
        w = self.label.winfo_reqwidth()
        root.geometry(f"+{sw - w - 40}+{30}")

        # Drag to move.
        self.label.bind("<Button-1>", self._drag_start)
        self.label.bind("<B1-Motion>", self._drag_move)
        # Quit.
        self.label.bind("<Button-3>", lambda e: root.destroy())
        root.bind("<Escape>", lambda e: root.destroy())

        self._last_text: str | None = None
        self._poll()

    @staticmethod
    def _render(running: bool) -> tuple[str, str]:
        got, total = progress()
        prog = f"{got}/{total}" if total else "no data"
        head = "BO2 RUNNING" if running else "BO2 not running"
        return f"{head}   {prog}", (COLOR_ON if running else COLOR_OFF)

    def _drag_start(self, event: tk.Event) -> None:
        self._dx, self._dy = event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y()

    def _drag_move(self, event: tk.Event) -> None:
        self.root.geometry(f"+{event.x_root - self._dx}+{event.y_root - self._dy}")

    def _poll(self) -> None:
        text, bg = self._render(bool(bo2_running()))
        if text != self._last_text:
            self._last_text = text
            self.label.config(text=text, bg=bg)
        self.root.after(POLL_MS, self._poll)


def run_label() -> None:
    """Show the floating always-on-top status pill and block until it closes."""
    root = tk.Tk()
    StatusLabel(root)
    root.mainloop()


def main() -> None:
    run_label()


if __name__ == "__main__":
    main()
