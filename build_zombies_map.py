#!/usr/bin/env python3
"""Build the BO2 Zombies achievement reference checklist.

Zombies achievements live in the separate Steam app "Call of Duty: Black Ops II
- Zombies" (appid 212910), NOT the campaign app (202970).

We read title+description+percent straight from the community stats page (each
row is internally consistent) and derive the map pack from the description's
leading "In <map>," phrase. We deliberately do NOT join the keyless
global-percentages API by name: this app has many tied percentages, and within
ties the two endpoints order items differently, which scrambles the pairing.

Writes bo2_zombies_achievements.json and prints a checklist grouped by map.
"""
from __future__ import annotations

import json
import re
import html
import sys
import urllib.request

APPID = "212910"
UA = {"User-Agent": "Mozilla/5.0 (BO2 zombies checklist builder)"}

# Map (from "In <map>,") -> display pack label.
MAP_TO_PACK = {
    "tranzit": "Base - TranZit / Green Run",
    "green run": "Base - TranZit / Green Run",
    "diner turned": "Base - Nuketown Zombies (Diner Turned)",
    "nuketown": "Base - Nuketown Zombies",
    "die rise": "Revolution (Die Rise)",
    "mob of the dead": "Uprising (Mob of the Dead)",
    "buried": "Vengeance (Buried)",
    "origins": "Apocalypse (Origins)",
}


def fetch(url: str) -> bytes:
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read()


def get_community() -> list[dict]:
    text = fetch(f"https://steamcommunity.com/stats/{APPID}/achievements/").decode("utf-8", "replace")
    rows: list[dict] = []
    for block in re.findall(r'achieveTxtHolder.*?</div>\s*</div>', text, re.S):
        pct = re.search(r'achievePercent">([0-9.]+)%', block)
        title = re.search(r"<h3>(.*?)</h3>", block, re.S)
        desc = re.search(r"<h5>(.*?)</h5>", block, re.S)
        if not (pct and title):
            continue
        description = html.unescape(desc.group(1)).strip() if desc else ""
        m = re.match(r"\s*In\s+([^,]+),", description, re.I)
        map_name = m.group(1).strip().lower() if m else ""
        rows.append({
            "title": html.unescape(title.group(1)).strip(),
            "description": description,
            "percent": float(pct.group(1)),
            "map": m.group(1).strip() if m else "?",
            "pack": MAP_TO_PACK.get(map_name, "Other"),
        })
    return rows


def main() -> int:
    rows = get_community()
    print(f"Fetched {len(rows)} zombies achievements from app {APPID}")

    unknown = [r for r in rows if r["pack"] == "Other"]
    if unknown:
        print(f"WARNING: {len(unknown)} rows had no recognizable map:", file=sys.stderr)
        for r in unknown:
            print(f"  {r['title']!r} :: {r['description']!r}", file=sys.stderr)

    out = "bo2_zombies_achievements.json"
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"appid": APPID, "count": len(rows), "achievements": rows}, fh, indent=2, ensure_ascii=False)
    print(f"Wrote {out}\n")

    # Group by pack, ordered by the natural DLC release order.
    order = [
        "Base - TranZit / Green Run",
        "Base - Nuketown Zombies (Diner Turned)",
        "Base - Nuketown Zombies",
        "Revolution (Die Rise)",
        "Uprising (Mob of the Dead)",
        "Vengeance (Buried)",
        "Apocalypse (Origins)",
        "Other",
    ]
    for pack in order:
        group = [r for r in rows if r["pack"] == pack]
        if not group:
            continue
        print(f"\n### {pack}  ({len(group)})")
        for r in sorted(group, key=lambda x: -x["percent"]):
            print(f"  - {r['title']}  [{r['percent']}%]")
            print(f"      {r['description']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
