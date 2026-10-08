#!/usr/bin/env python3
"""Build the BO2 apiname -> {title, description} map.

Data sources (both keyless, both maintained by Steam, both sorted by global
unlock percentage):
  * ISteamUserStats/GetGlobalAchievementPercentagesForApp -> apiname + percent
  * steamcommunity.com/stats/202970/achievements/          -> title + desc + percent

Because both lists are percent-sorted, we join them index-by-index and VERIFY
that the percentage of each pair matches. Any mismatch aborts the build rather
than emitting a wrong mapping. Writes bo2_achievements.json next to this file.
"""
from __future__ import annotations

import json
import re
import html
import sys
import urllib.request

APPID = "202970"
UA = {"User-Agent": "Mozilla/5.0 (BO2 achievement map builder)"}


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def get_api() -> list[tuple[str, float]]:
    url = ("https://api.steampowered.com/ISteamUserStats/"
           "GetGlobalAchievementPercentagesForApp/v0002/"
           f"?gameid={APPID}&format=json")
    d = json.loads(fetch(url))
    return [(a["name"], float(a["percent"])) for a in d["achievementpercentages"]["achievements"]]


def get_community() -> list[tuple[str, str, float]]:
    html_text = fetch(f"https://steamcommunity.com/stats/{APPID}/achievements/").decode("utf-8", "replace")
    rows: list[tuple[str, str, float]] = []
    # Each achievement lives in an <div class="achieveRow ..."> ... </div> block.
    for block in re.findall(r'achieveTxtHolder.*?</div>\s*</div>', html_text, re.S):
        pct = re.search(r'achievePercent">([0-9.]+)%', block)
        title = re.search(r'<h3>(.*?)</h3>', block, re.S)
        desc = re.search(r'<h5>(.*?)</h5>', block, re.S)
        if not (pct and title):
            continue
        rows.append((
            html.unescape(title.group(1)).strip(),
            html.unescape(desc.group(1)).strip() if desc else "",
            float(pct.group(1)),
        ))
    return rows


def main() -> int:
    api = get_api()
    com = get_community()
    print(f"API entries: {len(api)}   community entries: {len(com)}")
    if len(api) != len(com):
        print("ERROR: list length mismatch -- refusing to build.", file=sys.stderr)
        return 1

    mapping: dict[str, dict] = {}
    mismatches = 0
    for (name, api_pct), (title, desc, com_pct) in zip(api, com):
        if abs(api_pct - com_pct) > 0.05:
            mismatches += 1
            print(f"  PCT MISMATCH  {name}  api={api_pct}  com={com_pct}  title={title!r}")
        mapping[name] = {"title": title, "description": desc, "percent": api_pct}

    if mismatches:
        print(f"\nERROR: {mismatches} percentage mismatches -- order differs, "
              "refusing to emit a possibly-wrong map.", file=sys.stderr)
        return 1

    out = "bo2_achievements.json"
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"appid": APPID, "count": len(mapping), "achievements": mapping}, fh, indent=2, ensure_ascii=False)
    print(f"Verified {len(mapping)} achievements (all percentages align). Wrote {out}")
    for name, v in mapping.items():
        print(f"  {name:32} -> {v['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
