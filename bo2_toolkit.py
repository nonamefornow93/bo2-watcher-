#!/usr/bin/env python3
"""BO2 Achievement Toolkit -- application entry point.

Running with no arguments starts the Tkinter GUI. The frozen exe also
relaunches itself with a subcommand for its detached helpers:

    bo2_toolkit popup "Title" "description"   # Steam-style unlock overlay
    bo2_toolkit label                          # floating status pill

The watcher's CLI (status/rarity/watch/reset) is passed through too, which is
handy when running from source.
"""
from __future__ import annotations

import multiprocessing
import sys


def _dispatch(argv: list[str]) -> int | None:
    """Handle a subcommand, or return None to fall through to the GUI."""
    if not argv:
        return None
    cmd = argv[0].lower()

    if cmd == "popup":
        from bo2_popup import run_popup
        title = argv[1] if len(argv) > 1 else "Achievement"
        desc = argv[2] if len(argv) > 2 else ""
        run_popup(title, desc)
        return 0

    if cmd == "label":
        from bo2_status_label import run_label
        run_label()
        return 0

    if cmd in ("status", "rarity", "watch", "reset"):
        from bo2_achievement_watcher import main as watcher_main
        return watcher_main(argv)

    return None


def main() -> None:
    multiprocessing.freeze_support()
    rc = _dispatch(sys.argv[1:])
    if rc is not None:
        raise SystemExit(rc)
    from bo2_gui import run_gui
    run_gui()


if __name__ == "__main__":
    main()
