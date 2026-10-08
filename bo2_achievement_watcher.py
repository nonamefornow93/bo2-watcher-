#!/usr/bin/env python3
"""BO2 achievement watcher.

Reads the CODEX Steam-emulator local achievement store for Call of Duty:
Black Ops II (appid 202970) and reports / watches unlocks. This does NOT use
the Steam API or Steam's own achievement cache -- it reads the emulator's
local achievements.ini, so it works independently of Steam.

Usage:
    python bo2_achievement_watcher.py status     # list what's unlocked now
    python bo2_achievement_watcher.py watch      # watch for new unlocks live
    python bo2_achievement_watcher.py watch --no-toast   # console only
"""
from __future__ import annotations

import argparse
import configparser
import json
import os
import shutil
import subprocess
import sys
import textwrap
import time
from datetime import datetime

import psutil

from bo2_config import achievements_ini, is_frozen, map_path

APPID = "202970"

# CODEX stores its per-app data here; the user can override it via config.json.
DEFAULT_INI = achievements_ini()

# Process-name prefixes BO2 may run under. This build ships several launchers,
# including ones with spaces (e.g. "t6mp - Multiplayer Offline.exe"), so match
# by prefix rather than exact name.
BO2_PROCESS_PREFIXES = (
    "t6mp",        # multiplayer (+ "t6mp - Multiplayer Offline.exe")
    "t6zm",        # zombies (+ "t6zm - Zombies Offline.exe")
    "t6sp",        # single-player / campaign
    "blackops2",   # launcher
    "black ops",   # any "Black Ops ..." named exe
)

# Plutonium's launcher/bootstrapper are shared across all its CoD titles
# (t4/t5/t6/iw5), so they only count as BO2 when the command line targets t6.
PLUTONIUM_LAUNCHERS = ("plutonium-bootstrapper", "plutonium-launcher")

POLL_SECONDS = 3.0

# Friendly titles for the full 35-achievement set (built by
# build_achievement_map.py). Optional: the watcher still works without it.
DEFAULT_MAP = map_path()

# Steam-style overlay popup script (used only when running from source; the
# frozen build relaunches its own exe with the "popup" subcommand instead).
POPUP_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bo2_popup.py")


def load_titles(map_path: str) -> dict[str, dict]:
    """Return {apiname: {title, description}} from the JSON map, or {} if absent."""
    try:
        with open(map_path, "r", encoding="utf-8") as fh:
            return json.load(fh).get("achievements", {})
    except (OSError, json.JSONDecodeError):
        return {}


def title_of(titles: dict[str, dict], name: str) -> str:
    return titles.get(name, {}).get("title", name)


def desc_of(titles: dict[str, dict], name: str) -> str:
    return titles.get(name, {}).get("description", "")


def parse_achievements(ini_path: str) -> dict[str, dict]:
    """Return {api_name: {achieved, unlock_time}} parsed from the emu INI."""
    result: dict[str, dict] = {}
    if not os.path.exists(ini_path):
        return result

    cp = configparser.ConfigParser()
    # The file uses arbitrary section names; keep them verbatim.
    cp.optionxform = str  # type: ignore[assignment]
    try:
        with open(ini_path, "r", encoding="utf-8", errors="replace") as fh:
            cp.read_file(fh)
    except (configparser.Error, OSError) as exc:
        print(f"[warn] could not read {ini_path}: {exc}", file=sys.stderr)
        return result

    for section in cp.sections():
        if section == "SteamAchievements":
            continue  # index section, not an achievement definition
        achieved_raw = cp.get(section, "Achieved", fallback="0")
        unlock_raw = cp.get(section, "UnlockTime", fallback="0")
        try:
            achieved = int(achieved_raw) == 1
        except ValueError:
            achieved = achieved_raw.strip().lower() in ("1", "true", "yes")
        try:
            unlock_time = int(unlock_raw)
        except ValueError:
            unlock_time = 0
        result[section] = {"achieved": achieved, "unlock_time": unlock_time}
    return result


def unlocked_set(achievements: dict[str, dict]) -> set[str]:
    return {name for name, data in achievements.items() if data["achieved"]}


def progress(ini_path: str = DEFAULT_INI, map_path: str = DEFAULT_MAP) -> tuple[int, int]:
    """Return (unlocked, total) campaign progress using the map as the catalog."""
    titles = load_titles(map_path)
    achievements = parse_achievements(ini_path)
    unlocked = {n for n, d in achievements.items() if d["achieved"]}
    catalog = list(titles) if titles else list(achievements)
    got = sum(1 for n in catalog if n in unlocked)
    return got, len(catalog)


def fmt_time(unix_ts: int) -> str:
    if not unix_ts:
        return "unknown time"
    return datetime.fromtimestamp(unix_ts).strftime("%Y-%m-%d %H:%M:%S")


def bo2_running() -> list[str]:
    """Return the list of matching BO2 process names currently running.

    Catches the game binaries directly (t6sp/t6mp/t6zm, incl. Plutonium's
    t6mp.exe/t6zm.exe) and also Plutonium's launcher during the brief window
    before the game exe spawns -- but only when that launcher's command line
    targets BO2 (t6), so it won't false-positive for other Plutonium games.
    """
    found = []
    for proc in psutil.process_iter(["name", "cmdline"]):
        try:
            name = (proc.info.get("name") or "").lower()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        if name.startswith(BO2_PROCESS_PREFIXES):
            found.append(name)
        elif name.startswith(PLUTONIUM_LAUNCHERS):
            try:
                cmd = " ".join(proc.info.get("cmdline") or []).lower()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                cmd = ""
            if "t6" in cmd:
                found.append(name)
    return found


def windows_toast(title: str, message: str) -> None:
    """Best-effort native Windows 10/11 toast. Never raises."""
    ps = f"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom, ContentType = WindowsRuntime] | Out-Null
$template = @"
<toast>
  <visual>
    <binding template="ToastGeneric">
      <text>{title}</text>
      <text>{message}</text>
    </binding>
  </visual>
  <audio src="ms-winsoundevent:Notification.Default"/>
</toast>
"@
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml($template)
$toast = New-Object Windows.UI.Notifications.ToastNotification $xml
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("BO2AchievementWatcher").Show($toast)
"""
    try:
        subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        pass  # toast is a nicety; console output is the source of truth


def show_popup(title: str, desc: str = "") -> bool:
    """Launch the Steam-style overlay popup (detached). True if started.

    When frozen by PyInstaller there is no separate .py to run, so we relaunch
    our own exe with the "popup" subcommand; the entry point dispatches it to
    bo2_popup.run_popup() before any GUI is created.
    """
    flags = (getattr(subprocess, "DETACHED_PROCESS", 0)
             | getattr(subprocess, "CREATE_NO_WINDOW", 0))

    if is_frozen():
        cmd = [sys.executable, "popup", title, desc]
        cwd = os.path.dirname(os.path.abspath(sys.executable))
    else:
        if not os.path.exists(POPUP_SCRIPT):
            return False
        pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        if not os.path.exists(pythonw):
            pythonw = "pythonw"
        cmd = [pythonw, POPUP_SCRIPT, title, desc]
        cwd = os.path.dirname(POPUP_SCRIPT)

    try:
        subprocess.Popen(
            cmd,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
            close_fds=True,
        )
        return True
    except Exception:
        return False


def notify(name: str, title: str, ts: int, use_toast: bool, desc: str = "") -> None:
    label = title if title != name else name
    print(f"\a* Achievement unlocked: {label}  ({fmt_time(ts)})", flush=True)
    if use_toast:
        # Prefer the Steam-style overlay; fall back to a Windows toast if the
        # popup can't be launched for any reason.
        if not show_popup(label, desc):
            windows_toast("BO2 Achievement Unlocked", f"{label}\n{fmt_time(ts)}")


def status_text(ini_path: str = DEFAULT_INI, map_p: str = DEFAULT_MAP) -> str:
    """Full campaign checklist report as a single string (shared by CLI + GUI)."""
    achievements = parse_achievements(ini_path)
    titles = load_titles(map_p)
    running = bo2_running()

    # The full catalog comes from the map; the INI tells us what's unlocked.
    catalog = list(titles) if titles else sorted(achievements)
    if not catalog:
        return (f"No achievement data found at:\n  {ini_path}\n"
                "The game may not have written any stats yet.")

    unlocked = {n for n, d in achievements.items() if d["achieved"]}
    total = len(catalog)
    got = sum(1 for n in catalog if n in unlocked)

    run_s = ("yes (" + ", ".join(sorted(set(running))) + ")") if running else "no"
    out = [
        f"Source file : {ini_path}",
        f"Game running: {run_s}",
        f"Progress    : {got}/{total}" + ("" if titles else "  (map file missing; showing INI entries only)"),
        "-" * 72,
    ]

    # Unlocked first (with unlock time), then still-locked, in catalog order.
    def add(name: str, done: bool, ts: int = 0) -> None:
        mark = "[X]" if done else "[ ]"
        suffix = f" {fmt_time(ts)}" if done and ts else ""
        out.append(f"  {mark} {title_of(titles, name):32}{suffix}".rstrip())
        desc = desc_of(titles, name)
        if desc:
            out.append(textwrap.fill(desc, width=72,
                                     initial_indent=" " * 8, subsequent_indent=" " * 8))

    for name in [n for n in catalog if n in unlocked]:
        add(name, True, achievements[name]["unlock_time"])
    for name in [n for n in catalog if n not in unlocked]:
        add(name, False)

    # Any unlocked apiname not present in the map (shouldn't happen, but be safe).
    for name in sorted(unlocked - set(catalog)):
        add(name, True, achievements[name]["unlock_time"])
    return "\n".join(out)


def cmd_status(args: argparse.Namespace) -> int:
    text = status_text(args.ini, args.map)
    print(text)
    return 1 if text.startswith("No achievement data") else 0


def rarity_text(ini_path: str = DEFAULT_INI, map_p: str = DEFAULT_MAP) -> str:
    """All achievements sorted by global unlock % (rarest first), as a string."""
    titles = load_titles(map_p)
    if not titles:
        return "No achievement map found. Run menu option 6 (Refresh title data) first."
    achievements = parse_achievements(ini_path)
    unlocked = {n for n, d in achievements.items() if d["achieved"]}

    rows: list[tuple[float, str, bool]] = []
    for name, info in titles.items():
        try:
            pct = float(info.get("percent"))
        except (TypeError, ValueError):
            pct = float("inf")
        rows.append((pct, info.get("title", name), name in unlocked))
    rows.sort(key=lambda r: r[0])  # lowest % = rarest, first

    total = len(rows)
    got = sum(1 for r in rows if r[2])
    out = [
        f"BO2 achievement rarity  (rarest first)      Progress: {got}/{total}",
        "Global % = share of all Steam players who have it. Lower = rarer.",
        "-" * 72,
    ]
    for pct, title, done in rows:
        mark = "[X]" if done else "[ ]"
        pct_s = f"{pct:5.1f}%" if pct != float("inf") else "  n/a"
        out.append(f"  {mark} {pct_s}  {title}")
    return "\n".join(out)


def cmd_rarity(args: argparse.Namespace) -> int:
    """List all achievements sorted by global unlock % (rarest first)."""
    text = rarity_text(args.ini, args.map)
    print(text)
    return 1 if text.startswith("No achievement map") else 0


def cmd_watch(args: argparse.Namespace) -> int:
    use_toast = not args.no_toast
    titles = load_titles(args.map)
    print(f"Watching {args.ini}")
    print(f"Polling every {POLL_SECONDS:.0f}s. Press Ctrl+C to stop.\n")

    known = unlocked_set(parse_achievements(args.ini))
    print(f"Baseline: {len(known)} achievement(s) already unlocked.")
    was_running = bool(bo2_running())
    if was_running:
        print("BO2 is currently running.")

    try:
        while True:
            time.sleep(POLL_SECONDS)

            running = bo2_running()
            is_running = bool(running)
            if is_running != was_running:
                if is_running:
                    print(f"\n> BO2 started ({', '.join(sorted(set(running)))}).", flush=True)
                else:
                    print("\n. BO2 stopped.", flush=True)
                was_running = is_running

            current = unlocked_set(parse_achievements(args.ini))
            new = current - known
            if new:
                all_ach = parse_achievements(args.ini)
                for name in sorted(new):
                    notify(name, title_of(titles, name),
                           all_ach.get(name, {}).get("unlock_time", 0), use_toast,
                           desc_of(titles, name))
                known = current
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0


def reset_progress(ini_path: str = DEFAULT_INI) -> tuple[bool, str]:
    """Back up (timestamped) then delete achievements.ini. Returns (ok, message)."""
    running = bo2_running()
    if running:
        return False, ("BO2 is still running -- close the game first, then reset again.\n"
                       f"  Detected: {', '.join(sorted(set(running)))}")
    if not os.path.exists(ini_path):
        return True, "Nothing to reset: achievements.ini does not exist (already empty)."

    backup = f"{ini_path}.bak_{datetime.now():%Y%m%d_%H%M%S}"
    shutil.copy2(ini_path, backup)
    os.remove(ini_path)
    return True, (f"Reset complete. Progress cleared (0/35).\n"
                  f"  Backup saved: {backup}\n"
                  "  The game recreates a fresh file on next launch.")


def cmd_reset(args: argparse.Namespace) -> int:
    """Back up (timestamped) then delete achievements.ini to reset progress."""
    ok, message = reset_progress(args.ini)
    print(message)
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    # Windows consoles may use a non-UTF8 code page (e.g. cp1252); never crash
    # on an unencodable glyph, just replace it.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass

    parser = argparse.ArgumentParser(description="BO2 (CODEX emu) achievement watcher")
    parser.add_argument("--ini", default=DEFAULT_INI,
                        help=f"path to achievements.ini (default: {DEFAULT_INI})")
    parser.add_argument("--map", default=DEFAULT_MAP,
                        help=f"path to bo2_achievements.json title map (default: {DEFAULT_MAP})")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="list currently unlocked achievements")
    sub.add_parser("rarity", help="list achievements by global rarity (rarest first)")
    watch = sub.add_parser("watch", help="watch for new unlocks live")
    watch.add_argument("--no-toast", action="store_true",
                       help="disable Windows toast notifications (console only)")
    sub.add_parser("reset", help="back up and clear all achievement progress")

    args = parser.parse_args(argv)
    if args.command == "status":
        return cmd_status(args)
    if args.command == "rarity":
        return cmd_rarity(args)
    if args.command == "watch":
        return cmd_watch(args)
    if args.command == "reset":
        return cmd_reset(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
