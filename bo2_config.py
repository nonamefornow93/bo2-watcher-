#!/usr/bin/env python3
"""Shared config + resource helpers for the BO2 Achievement Toolkit.

Everything user-specific lives in %APPDATA%\\BO2AchievementToolkit\\config.json so
the installed app (and the GitHub repo) contain NO personal paths. The game
folder is chosen by the user on first launch.

This module also centralises the "where are my bundled files?" question so it
works both when running from source AND when frozen by PyInstaller (which
unpacks data files into a temp dir exposed as sys._MEIPASS).
"""
from __future__ import annotations

import json
import os
import sys

APP_NAME = "BO2AchievementToolkit"
CONFIG_VERSION = 1

# Campaign app id for the CODEX Steam emulator local store.
APPID = "202970"

# Game executables we accept as proof a folder really is a BO2 install.
GAME_EXES = (
    "t6sp.exe",                       # campaign
    "t6mp.exe",                       # multiplayer
    "t6zm.exe",                       # zombies
    "t6zm - Zombies Offline.exe",     # offline zombies launcher
    "t6mp - Multiplayer Offline.exe", # offline multiplayer launcher
)

DEFAULTS = {
    "version": CONFIG_VERSION,
    "game_dir": "",
    "achievements_ini": "",  # blank => derive from the CODEX default location
}


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_dir() -> str:
    """Directory holding bundled resources (exe dir when frozen, script dir otherwise)."""
    if is_frozen():
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def resource_path(rel: str) -> str:
    """Absolute path to a bundled data file.

    PyInstaller onefile extracts data into sys._MEIPASS; onefolder keeps it
    next to the exe. Both cases resolve the same relative name.
    """
    base = getattr(sys, "_MEIPASS", None) or app_dir()
    return os.path.join(base, rel)


def config_dir() -> str:
    root = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(root, APP_NAME)


def config_path() -> str:
    return os.path.join(config_dir(), "config.json")


def default_achievements_ini() -> str:
    """The CODEX emulator's local campaign achievement store."""
    sys_drive = os.environ.get("SystemDrive", "C:")
    if not sys_drive.endswith(("\\", "/")):
        sys_drive += "\\"
    return os.path.join(
        sys_drive, "Users", "Public", "Documents", "Steam", "CODEX",
        APPID, "achievements.ini",
    )


def load() -> dict:
    """Return the merged config (defaults + whatever is on disk)."""
    cfg = dict(DEFAULTS)
    try:
        with open(config_path(), "r", encoding="utf-8") as fh:
            stored = json.load(fh)
        if isinstance(stored, dict):
            cfg.update({k: v for k, v in stored.items() if k in DEFAULTS})
    except (OSError, json.JSONDecodeError, ValueError):
        pass
    return cfg


def save(cfg: dict) -> None:
    """Persist config, creating the folder if needed. Never raises."""
    try:
        os.makedirs(config_dir(), exist_ok=True)
        merged = dict(DEFAULTS)
        merged.update({k: v for k, v in cfg.items() if k in DEFAULTS})
        with open(config_path(), "w", encoding="utf-8") as fh:
            json.dump(merged, fh, indent=2)
    except OSError:
        pass


def achievements_ini(cfg: dict | None = None) -> str:
    """The achievement .ini path to read, honouring a user override."""
    if cfg is None:
        cfg = load()
    return cfg.get("achievements_ini") or default_achievements_ini()


def map_path() -> str:
    """Campaign title/description/percent map (bundled)."""
    return resource_path("bo2_achievements.json")


def looks_like_bo2(path: str) -> bool:
    """True if `path` looks like a real BO2 install (has a known game exe)."""
    if not path or not os.path.isdir(path):
        return False
    return any(os.path.exists(os.path.join(path, exe)) for exe in GAME_EXES)


def game_exe(game_dir: str, name: str) -> str:
    """Full path to a game exe inside game_dir ('' if game_dir is empty)."""
    if not game_dir:
        return ""
    return os.path.join(game_dir, name)


def plutonium_dir() -> str:
    return os.path.join(os.environ.get("LOCALAPPDATA", ""), "Plutonium")


def has_plutonium() -> bool:
    return os.path.isdir(plutonium_dir())
