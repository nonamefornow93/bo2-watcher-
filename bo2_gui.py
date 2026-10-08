#!/usr/bin/env python3
"""Tkinter GUI for the BO2 Achievement Toolkit.

A single window that replaces the old BO2 Toolkit.bat console menu:
launch the game, watch for achievement unlocks live (with Steam-style
popups), view the campaign checklist / rarity ranking / zombies guide,
test the popup, show the floating status label, and reset progress.

The game folder is chosen by the user on first launch and stored in
%APPDATA%\\BO2AchievementToolkit\\config.json -- nothing is hardcoded, so the
built app (and this repo) stay portable and safe to publish.
"""
from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import webbrowser

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

import bo2_config as config
from bo2_achievement_watcher import (
    bo2_running,
    desc_of,
    load_titles,
    parse_achievements,
    progress,
    rarity_text,
    reset_progress,
    show_popup,
    status_text,
    title_of,
    unlocked_set,
)

POLL_SECONDS = 3.0
ZOMBIES_TXT = "BO2 Zombies Achievements.txt"
PLUTONIUM_URL = "https://plutonium.pw/"

DETACHED = (getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0))
DEVNULL = subprocess.DEVNULL


class ToolkitGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.cfg = config.load()
        self._queue: "queue.Queue[tuple[str, dict]]" = queue.Queue()
        self._watch_thread: threading.Thread | None = None
        self._watch_stop = threading.Event()
        self._watching = False
        self._icon = None  # keep a reference so the PhotoImage isn't GC'd

        self._build_ui()
        self._center(860, 560)
        self._drain_queue()          # start the thread-safe UI pump
        self._refresh_header()
        self._ensure_game_dir()      # first-launch game folder picker

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        self.root.title("BO2 Achievement Toolkit")
        self.root.minsize(760, 480)
        try:
            ico = config.resource_path("bo2_icon.png")
            if os.path.exists(ico):
                self._icon = tk.PhotoImage(file=ico)
                self.root.iconphoto(True, self._icon)
        except tk.TclError:
            pass

        style = ttk.Style(self.root)
        for theme in ("clam", "vista", "winnative"):
            if theme in style.theme_names():
                try:
                    style.theme_use(theme)
                    break
                except tk.TclError:
                    continue

        self.header_var = tk.StringVar(value="Loading...")
        ttk.Label(self.root, textvariable=self.header_var,
                  font=("Segoe UI", 11, "bold"), padding=(12, 10),
                  anchor="w").grid(row=0, column=0, sticky="we")
        ttk.Separator(self.root, orient="horizontal").grid(
            row=1, column=0, sticky="we")

        body = ttk.Frame(self.root, padding=(12, 10))
        body.grid(row=2, column=0, sticky="nsew")
        self.root.rowconfigure(2, weight=1)
        self.root.columnconfigure(0, weight=1)

        left = ttk.Frame(body)
        left.pack(side="left", fill="y", padx=(0, 12))
        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True)

        def btn(text: str, cmd) -> ttk.Button:
            b = ttk.Button(left, text=text, command=cmd, width=27)
            b.pack(fill="x", pady=3)
            return b

        btn("Launch Campaign", self._launch_campaign)
        btn("Launch Zombies (Plutonium)", self._launch_zombies)
        ttk.Separator(left, orient="horizontal").pack(fill="x", pady=8)
        self.watch_btn = btn("Start Live Watching", self._toggle_watch)
        btn("Show Floating Label", self._show_label)
        btn("Test Unlock Popup", self._test_popup)
        ttk.Separator(left, orient="horizontal").pack(fill="x", pady=8)
        btn("Campaign Checklist", self._show_checklist)
        btn("Rarity Ranking", self._show_rarity)
        btn("Zombies Guide", self._show_zombies)
        ttk.Separator(left, orient="horizontal").pack(fill="x", pady=8)
        btn("Reset Progress...", self._reset)
        btn("Settings...", self._settings)

        self.output = scrolledtext.ScrolledText(
            right, wrap="none", font=("Consolas", 10), state="disabled",
            background="#11151c", foreground="#d6deeb",
            insertbackground="#d6deeb", padx=8, pady=6)
        self.output.pack(fill="both", expand=True)

        self.status_var = tk.StringVar(value="Idle")
        ttk.Label(self.root, textvariable=self.status_var, relief="sunken",
                  anchor="w", padding=(8, 4)).grid(row=3, column=0, sticky="we")

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _center(self, w: int, h: int) -> None:
        self.root.update_idletasks()
        x = max(0, (self.root.winfo_screenwidth() - w) // 2)
        y = max(0, (self.root.winfo_screenheight() - h) // 3)
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    # ------------------------------------------------------- thread -> UI
    def _emit(self, kind: str, **kw) -> None:
        self._queue.put((kind, kw))

    def _drain_queue(self) -> None:
        try:
            while True:
                kind, kw = self._queue.get_nowait()
                if kind == "output":
                    self._write_output(kw["text"], kw.get("clear", False))
                elif kind == "log":
                    self._write_output(kw["text"] + "\n")
                elif kind == "status":
                    self.status_var.set(kw["text"])
                elif kind == "header":
                    self._refresh_header()
        except queue.Empty:
            pass
        self.root.after(150, self._drain_queue)

    def _write_output(self, text: str, clear: bool = False) -> None:
        self.output.configure(state="normal")
        if clear:
            self.output.delete("1.0", "end")
        if text and not text.endswith("\n"):
            text += "\n"
        self.output.insert("end", text)
        self.output.see("end")
        self.output.configure(state="disabled")

    def _refresh_header(self) -> None:
        got, total = progress(config.achievements_ini(self.cfg), config.map_path())
        gd = self.cfg.get("game_dir") or "(not set)"
        self.header_var.set(f"Campaign progress: {got}/{total}        Game folder: {gd}")

    # ----------------------------------------------------- first launch
    def _ensure_game_dir(self) -> None:
        gd = self.cfg.get("game_dir", "")
        if gd and config.looks_like_bo2(gd):
            return
        messagebox.showinfo(
            "Welcome to the BO2 Achievement Toolkit",
            "First launch: pick your Call of Duty: Black Ops II game folder\n"
            "(the one containing t6sp.exe).\n\n"
            "Nothing is hardcoded, so the app stays portable. You can change\n"
            "it later via Settings.")
        self._pick_game_dir(first=True)

    def _pick_game_dir(self, first: bool = False) -> None:
        while True:
            d = filedialog.askdirectory(
                title="Select your BO2 game folder (contains t6sp.exe)")
            if not d:
                if first:
                    self._emit("status",
                               text="No game folder set - open Settings to choose one.")
                return
            if config.looks_like_bo2(d):
                self._set_game_dir(d)
                return
            if not messagebox.askyesno(
                    "Not a BO2 folder",
                    "That folder doesn't contain t6sp.exe / t6mp.exe / t6zm.exe.\n\n"
                    "Use it anyway?"):
                continue
            self._set_game_dir(d)
            return

    def _set_game_dir(self, d: str) -> None:
        self.cfg["game_dir"] = d
        config.save(self.cfg)
        self._refresh_header()
        self._emit("log", text=f"Game folder set to: {d}")

    def _require_game_dir(self) -> str:
        gd = self.cfg.get("game_dir", "")
        if gd and os.path.isdir(gd):
            return gd
        self._emit("log", text="Game folder not set - choose it now.")
        self._pick_game_dir()
        return self.cfg.get("game_dir", "")

    # --------------------------------------------------------- launching
    def _launch_campaign(self) -> None:
        gd = self._require_game_dir()
        if not gd:
            return
        for name, is_cmd in (("sp.cmd", True), ("t6sp.exe", False)):
            path = os.path.join(gd, name)
            if not os.path.exists(path):
                continue
            try:
                if is_cmd:
                    # sp.cmd sets the correct CODEX steam_api.dll, then runs t6sp.
                    subprocess.Popen(["cmd", "/c", path], cwd=gd)
                else:
                    subprocess.Popen([path], cwd=gd)
            except OSError as exc:
                messagebox.showerror("Launch failed", str(exc))
                return
            self._emit("log", text=f"Launching campaign via {name}...")
            self._start_watching(auto=True)
            return
        messagebox.showerror(
            "Not found", f"No sp.cmd or t6sp.exe found in:\n{gd}")

    def _launch_zombies(self) -> None:
        root = config.plutonium_dir()
        if not os.path.isdir(root):
            if messagebox.askyesno(
                    "Plutonium not found",
                    "Zombies is best played through Plutonium (free & maintained);\n"
                    "the offline crack's Zombies crashes on modern Windows.\n\n"
                    "Plutonium wasn't found at:\n  %LOCALAPPDATA%\\Plutonium\n\n"
                    "Open the Plutonium website to install it?"):
                webbrowser.open(PLUTONIUM_URL)
            return

        home = os.path.expanduser("~")
        candidates = [
            (os.path.join(root, "plutonium.exe"), root),
            (os.path.join(root, "bin", "plutonium-launcher-win32.exe"), root),
            (os.path.join(home, "Desktop", "plutonium.exe"), None),
            (os.path.join(home, "OneDrive", "Desktop", "plutonium.exe"), None),
            (os.path.join(home, "Downloads", "plutonium.exe"), None),
        ]
        for path, cwd in candidates:
            if not os.path.exists(path):
                continue
            try:
                subprocess.Popen([path], cwd=cwd or os.path.dirname(path))
            except OSError as exc:
                messagebox.showerror("Launch failed", str(exc))
                return
            self._emit("log", text=f"Launching Plutonium ({os.path.basename(path)})...")
            self._emit("log", text="Note: Plutonium Zombies does NOT write CODEX "
                                   "achievements, so unlocks aren't auto-tracked.")
            return
        messagebox.showerror(
            "Plutonium",
            "Plutonium is installed but no launcher exe was found.\n"
            "You can start Plutonium manually and pick Black Ops II - Zombies.")

    # --------------------------------------------------------- watching
    def _toggle_watch(self) -> None:
        if self._watching:
            self._stop_watching()
        else:
            self._start_watching()

    def _start_watching(self, auto: bool = False) -> None:
        if self._watching:
            return
        ini = config.achievements_ini(self.cfg)
        self._watch_stop.clear()
        self._watching = True
        self.watch_btn.configure(text="Stop Live Watching")
        self._emit("status", text=f"Watching {ini}")
        if not auto:
            self._emit("log", text="--- Live watching started ---")
            self._emit("log", text=f"INI: {ini}")
            self._emit("log", text=f"Polling every {POLL_SECONDS:.0f}s. New campaign "
                                   "unlocks will pop up automatically.")
        self._watch_thread = threading.Thread(
            target=self._watch_loop, args=(ini,), daemon=True)
        self._watch_thread.start()

    def _stop_watching(self) -> None:
        if not self._watching:
            return
        self._watch_stop.set()
        self._watching = False
        self.watch_btn.configure(text="Start Live Watching")
        self._emit("status", text="Idle")
        self._emit("log", text="--- Live watching stopped ---")

    def _watch_loop(self, ini: str) -> None:
        titles = load_titles(config.map_path())
        known = unlocked_set(parse_achievements(ini))
        was_running = bool(bo2_running())
        self._emit("log", text=f"Baseline: {len(known)} achievement(s) already unlocked.")
        if was_running:
            self._emit("log", text="BO2 is currently running.")

        while not self._watch_stop.is_set():
            if self._watch_stop.wait(POLL_SECONDS):
                break
            running = bo2_running()
            is_running = bool(running)
            if is_running != was_running:
                self._emit("log", text=("> BO2 started." if is_running else ". BO2 stopped."))
                self._emit("header")
                was_running = is_running

            current = parse_achievements(ini)
            now = unlocked_set(current)
            new = now - known
            if new:
                for name in sorted(new):
                    title = title_of(titles, name)
                    self._emit("log", text=f"* Unlocked: {title}")
                    show_popup(title, desc_of(titles, name))
                known = now
                self._emit("header")

    # --------------------------------------------------------- popups
    def _test_popup(self) -> None:
        self._emit("log", text="Showing a test popup...")
        show_popup("Achievement Unlocked", "This is how a real unlock will look.")

    def _show_label(self) -> None:
        if config.is_frozen():
            cmd = [sys.executable, "label"]
            cwd = config.app_dir()
        else:
            pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
            if not os.path.exists(pythonw):
                pythonw = "pythonw"
            cmd = [pythonw, os.path.join(config.app_dir(), "bo2_status_label.py")]
            cwd = config.app_dir()
        try:
            subprocess.Popen(cmd, cwd=cwd, creationflags=DETACHED, close_fds=True,
                             stdin=DEVNULL, stdout=DEVNULL, stderr=DEVNULL)
        except OSError as exc:
            messagebox.showerror("Label failed", str(exc))
            return
        self._emit("log", text="Floating label started (drag to move, right-click to close).")

    # --------------------------------------------------------- reports
    def _show_checklist(self) -> None:
        self._emit("output", clear=True,
                   text=status_text(config.achievements_ini(self.cfg), config.map_path()))

    def _show_rarity(self) -> None:
        self._emit("output", clear=True,
                   text=rarity_text(config.achievements_ini(self.cfg), config.map_path()))

    def _show_zombies(self) -> None:
        try:
            with open(config.resource_path(ZOMBIES_TXT), "r",
                      encoding="utf-8", errors="replace") as fh:
                body = fh.read()
        except OSError:
            body = "Zombies reference file not found."
        header = (
            "BO2 ZOMBIES ACHIEVEMENTS (manual reference)\n"
            "NOTE: Zombies runs as a separate app (212910) under a different\n"
            "emulator, so its unlocks are NOT written to the file this tool reads.\n"
            "Treat this as a checklist; there is no auto-popup for Zombies.\n"
            + "=" * 72 + "\n")
        self._emit("output", clear=True, text=header + body)

    # --------------------------------------------------------- reset
    def _reset(self) -> None:
        if not messagebox.askyesno(
                "Reset all progress?",
                "This backs up then deletes achievements.ini, clearing campaign\n"
                "progress to 0/35. A timestamped .bak copy is kept.\n"
                "Close the game first.\n\nContinue?"):
            return
        ok, msg = reset_progress(config.achievements_ini(self.cfg))
        self._emit("output", clear=True, text=msg)
        self._refresh_header()
        messagebox.showinfo("Reset", "Done - progress cleared." if ok
                            else "Could not reset (is the game still running?).")

    # --------------------------------------------------------- settings
    def _settings(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("Settings")
        win.transient(self.root)
        win.resizable(False, False)
        frm = ttk.Frame(win, padding=16)
        frm.grid(sticky="nsew")

        ttk.Label(frm, text="BO2 game folder (contains t6sp.exe):").grid(
            row=0, column=0, columnspan=3, sticky="w")
        var = tk.StringVar(value=self.cfg.get("game_dir", ""))
        ttk.Entry(frm, textvariable=var, width=62).grid(
            row=1, column=0, columnspan=2, sticky="we", pady=(4, 8))

        def browse() -> None:
            d = filedialog.askdirectory(parent=win, title="Select BO2 game folder")
            if d:
                var.set(d)

        ttk.Button(frm, text="Browse...", command=browse).grid(
            row=1, column=2, sticky="e", padx=(8, 0), pady=(4, 8))

        ttk.Label(frm, text="Achievements file (CODEX, read automatically):").grid(
            row=2, column=0, columnspan=3, sticky="w")
        ttk.Label(frm, text=config.achievements_ini(self.cfg), foreground="#666",
                  wraplength=520, justify="left").grid(
            row=3, column=0, columnspan=3, sticky="w", pady=(2, 12))

        def save() -> None:
            d = var.get().strip().strip('"')
            if d and not os.path.isdir(d):
                messagebox.showwarning("Invalid folder",
                                       "That folder does not exist.", parent=win)
                return
            self._set_game_dir(d)
            win.destroy()

        btns = ttk.Frame(frm)
        btns.grid(row=4, column=0, columnspan=3, sticky="e")
        ttk.Button(btns, text="Cancel", command=win.destroy).pack(side="right")
        ttk.Button(btns, text="Save", command=save).pack(side="right", padx=(0, 8))

        win.grab_set()
        self._center_toplevel(win, 560, 220)

    def _center_toplevel(self, win: tk.Toplevel, w: int, h: int) -> None:
        win.update_idletasks()
        x = self.root.winfo_x() + max(0, (self.root.winfo_width() - w) // 2)
        y = self.root.winfo_y() + max(0, (self.root.winfo_height() - h) // 2)
        win.geometry(f"{w}x{h}+{x}+{y}")

    # --------------------------------------------------------- lifecycle
    def _on_close(self) -> None:
        self._watch_stop.set()
        self._watching = False
        self.root.destroy()


def run_gui() -> None:
    root = tk.Tk()
    ToolkitGUI(root)
    root.mainloop()


if __name__ == "__main__":
    run_gui()
