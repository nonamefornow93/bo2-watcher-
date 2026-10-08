# BO2 Achievement Toolkit

An unofficial Windows tool for **Call of Duty: Black Ops II** that watches your
**campaign** achievements live and pops a Steam-style "Achievement Unlocked"
overlay (with sound) the moment you earn one — plus a floating status pill, a
full checklist, a rarity ranking, and a one-click progress reset.

It works by reading the **CODEX Steam-emulator's local achievement store**, so
it tracks unlocks that Steam itself never shows for this build.

> **Who this is for:** players running the **CODEX offline/emulator build** of
> Black Ops II (the one that stores progress in
> `C:\Users\Public\Documents\Steam\CODEX\202970\achievements.ini`).
> A normal Steam purchase reports achievements through Steam instead, and this
> tool does **not** read those.

---

## Features

- **Launch Campaign** — starts the game (via `sp.cmd`/`t6sp.exe`) and begins
  auto-tracking in one click.
- **Live watching** — polls the achievement file every few seconds; new unlocks
  fire a **Steam-style popup** with your own sound, and the header progress
  (`10/35`) updates in real time.
- **Floating status pill** — a tiny always-on-top label: green = running,
  red = not, with live progress. Drag to move, right-click to close.
- **Campaign checklist** — all 35 achievements with descriptions and unlock times.
- **Rarity ranking** — every achievement sorted by global unlock % (rarest first).
- **Zombies guide** — a reference checklist for the Zombies achievements.
- **Reset progress** — backs up (timestamped `.bak`) then clears the file. Refuses
  to run while the game is open.
- **Portable** — no hardcoded paths. On **first launch you pick your game folder**;
  it's remembered in `%APPDATA%\BO2AchievementToolkit\config.json`.

---

## Install (easy way)

1. Grab **`BO2-Toolkit-Setup.exe`** from the [Releases](../../releases) page.
2. Run it. It installs per-user (no admin needed) and adds Start-menu + desktop
   shortcuts and an uninstaller.
3. Open **BO2 Achievement Toolkit**. On first launch, browse to your Black Ops II
   game folder (the one containing `t6sp.exe`). Done.

Prefer no install? The PyInstaller **one-folder** build in `dist\BO2Toolkit\`
runs standalone — just launch `BO2Toolkit.exe`.

---

## Using it

| Button | What it does |
|---|---|
| **Launch Campaign** | Starts the game and turns on live tracking automatically. |
| **Launch Zombies (Plutonium)** | Opens Plutonium for Zombies (see note below). |
| **Start / Stop Live Watching** | Toggles the background watcher + popups. |
| **Show Floating Label** | Pops the always-on-top status pill. |
| **Test Unlock Popup** | Previews the unlock overlay + sound. |
| **Campaign Checklist / Rarity Ranking / Zombies Guide** | Prints those reports. |
| **Reset Progress…** | Backs up and clears campaign progress to 0/35. |
| **Settings…** | Change the game folder; shows the achievement file path. |

### Zombies note (important)

Zombies is a **separate Steam app (212910)** under a **different emulator**, so
its unlocks are **not** written to the file this tool reads. There is therefore
**no auto-popup for Zombies** — the Zombies Guide is a manual checklist only.
The offline Zombies build also crashes on modern Windows 11, so the recommended
way to play it is **Plutonium** (free and maintained). Plutonium does not report
CODEX/Steam achievements either.

---

## Build from source

**Requirements**

- Windows 10/11
- Python 3.11+ (tested on 3.13)
- `python -m pip install psutil pyinstaller`
- [Inno Setup 6](https://jrsoftware.org/isinfo.php) — only needed to build the
  `Setup.exe` installer.

**Build**

```bat
build.bat
```

This produces:

- `dist\BO2Toolkit\BO2Toolkit.exe` — the portable app (PyInstaller one-folder).
- `installer-output\BO2-Toolkit-Setup.exe` — the installer (Inno Setup).

`app.ico` is generated from `bo2_icon.png` with Pillow if you ever need to
rebuild it:

```bat
python -c "from PIL import Image; Image.open('bo2_icon.png').convert('RGBA').save('app.ico', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])"
```

---

## Project layout

```
bo2_toolkit.py             Entry point: GUI, plus popup/label/CLI subcommands
bo2_gui.py                 Tkinter main window
bo2_config.py              Config + bundled-resource path helpers (portable)
bo2_achievement_watcher.py Reads/parses the CODEX achievements.ini; status/rarity/reset/watch
bo2_popup.py               Steam-style unlock overlay (icon + sound + slide animation)
bo2_status_label.py        Floating always-on-top status pill
bo2_achievements.json      apiname -> {title, description, percent} for all 35 campaign achievements
bo2_zombies_achievements.json / BO2 Zombies Achievements.txt   Zombies reference data
build_achievement_map.py   Dev tool: rebuilds the campaign map from public Steam stats
build_zombies_map.py       Dev tool: rebuilds the Zombies reference
build.bat / installer.iss  Build the app + installer
```

The bundled icon (`bo2_icon.png`) and unlock sound (`bo2_popup_sound.mp3`) are
included as app assets; the icon is derived from the game's own executable.

---

## How it works

The CODEX emulator writes one INI section per achievement to
`…\Steam\CODEX\202970\achievements.ini` (`Achieved=0/1`, `UnlockTime`, …). The
tool parses that file, joins each API name with the friendly title/description/
global-% from `bo2_achievements.json`, and diffs it against the last-seen set to
detect new unlocks. **No Steam API, no injection, no game files are modified.**

---

## Disclaimer

This is an **unofficial fan tool**. It is **not** affiliated with, endorsed by,
or sponsored by Activision Publishing, Inc. or Treyarch. *Call of Duty* and
*Call of Duty: Black Ops II* are trademarks of Activision Publishing, Inc.
Use at your own risk; it reads a local file only and never touches online play.

## License

[MIT](LICENSE)
