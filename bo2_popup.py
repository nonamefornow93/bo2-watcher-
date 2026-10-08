#!/usr/bin/env python3
"""Steam-style achievement popup for BO2.

Usage:  pythonw bo2_popup.py "Achievement Title" ["description"]

Shows a dark overlay in the bottom-right corner that slides in, plays a
chime, stays a few seconds, then slides back out and closes -- mimicking
Steam's own "Achievement Unlocked" notification.
"""
from __future__ import annotations

import ctypes
import os
import sys
import tkinter as tk

try:
    import winsound
except ImportError:  # non-Windows; sound is optional
    winsound = None

from bo2_config import resource_path

# Real BO2 game icon (extracted from t6sp.exe). Falls back to a drawn star.
ICON_PATH = resource_path("bo2_icon.png")

# Custom unlock sound (user-provided MP3). Falls back to a system chime.
SOUND_PATH = resource_path("bo2_popup_sound.mp3")

BG = "#1b2838"        # Steam dark panel
ACCENT = "#66c0f4"    # Steam light blue
HEADER = "#c7d5e0"    # Steam gray text
DESC = "#8f98a0"      # Steam muted text
GOLD = "#f0b90b"

MARGIN = 24
SHOW_MS = 5000        # how long it stays fully on screen
SLIDE_STEP = 30       # pixels per animation frame
SLIDE_DELAY = 8       # ms per animation frame


class Popup:
    def __init__(self, root: tk.Tk, title: str, desc: str) -> None:
        self.root = root
        root.overrideredirect(True)              # borderless
        root.attributes("-topmost", True)        # above the game
        try:
            root.attributes("-alpha", 0.97)
        except tk.TclError:
            pass

        frame = tk.Frame(root, bg=BG, highlightbackground=ACCENT,
                         highlightthickness=1)
        frame.pack(fill="both", expand=True)

        # Badge: the real BO2 game icon if available, else a drawn gold star.
        self._icon = None
        badge = None
        try:
            if os.path.exists(ICON_PATH):
                self._icon = tk.PhotoImage(file=ICON_PATH)
                badge = tk.Label(frame, image=self._icon, bg=BG, bd=0,
                                 highlightthickness=0)
        except tk.TclError:
            badge = None
        if badge is None:
            badge = tk.Canvas(frame, width=56, height=56, bg=BG,
                              highlightthickness=0)
            badge.create_oval(5, 5, 51, 51, fill=GOLD, outline="")
            badge.create_text(28, 29, text="*", font=("Segoe UI", 24, "bold"),
                              fill=BG)
        rows = 3 if desc else 2
        badge.grid(row=0, column=0, rowspan=rows, padx=(14, 10), pady=14)

        tk.Label(frame, text="Achievement Unlocked", bg=BG, fg=HEADER,
                 font=("Segoe UI", 10), anchor="w").grid(
            row=0, column=1, sticky="w", padx=(0, 16), pady=(14, 0))

        tk.Label(frame, text=title, bg=BG, fg="white", anchor="w",
                 font=("Segoe UI", 13, "bold"), justify="left",
                 wraplength=260).grid(
            row=1, column=1, sticky="w", padx=(0, 16),
            pady=(0, 14 if not desc else 2))

        if desc:
            tk.Label(frame, text=desc, bg=BG, fg=DESC, anchor="w",
                     font=("Segoe UI", 9), justify="left",
                     wraplength=260).grid(
                row=2, column=1, sticky="w", padx=(0, 16), pady=(0, 14))

        root.update_idletasks()
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        w = root.winfo_reqwidth()
        h = root.winfo_reqheight()
        self.final_x = sw - w - MARGIN
        self.final_y = sh - h - MARGIN - 48      # sit above the taskbar
        self._screen_w = sw
        self.x = sw                              # start fully off-screen right
        root.geometry(f"+{self.x}+{self.final_y}")
        self._force_topmost()
        self._slide_in()

    def _force_topmost(self) -> None:
        """Re-assert topmost + no-focus-steal so it overlays borderless games."""
        try:
            hwnd = int(self.root.frame(), 16)
            SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE = 0x0001, 0x0002, 0x0010
            HWND_TOPMOST = -1
            ctypes.windll.user32.SetWindowPos(
                hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE)
        except Exception:
            pass

    def _slide_in(self) -> None:
        self.x -= SLIDE_STEP
        if self.x <= self.final_x:
            self.root.geometry(f"+{self.final_x}+{self.final_y}")
            self.root.after(SHOW_MS, self._slide_out)
            return
        self.root.geometry(f"+{self.x}+{self.final_y}")
        self.root.after(SLIDE_DELAY, self._slide_in)

    def _slide_out(self) -> None:
        self.x = self.root.winfo_x() + SLIDE_STEP
        if self.x >= self._screen_w:
            self.root.destroy()
            return
        self.root.geometry(f"+{self.x}+{self.final_y}")
        self.root.after(SLIDE_DELAY, self._slide_out)


def chime() -> None:
    # Prefer the user's custom MP3 via Windows MCI (plays MP3 without extra deps).
    if os.path.exists(SOUND_PATH):
        try:
            winmm = ctypes.windll.winmm
            open_cmd = f'open "{SOUND_PATH}" type mpegvideo alias bo2pop'
            if winmm.mciSendStringW(open_cmd, None, 0, None) == 0:
                winmm.mciSendStringW("play bo2pop from 0", None, 0, None)
                return
        except Exception:
            pass
    if not winsound:
        return
    try:
        winsound.PlaySound("SystemAsterisk",
                           winsound.SND_ALIAS | winsound.SND_ASYNC)
    except Exception:
        pass


def run_popup(title: str = "Achievement", desc: str = "") -> None:
    """Show the overlay popup and block until it closes itself."""
    chime()
    root = tk.Tk()
    Popup(root, title, desc)
    root.mainloop()


def main() -> None:
    title = sys.argv[1] if len(sys.argv) > 1 else "Achievement"
    desc = sys.argv[2] if len(sys.argv) > 2 else ""
    run_popup(title, desc)


if __name__ == "__main__":
    main()
