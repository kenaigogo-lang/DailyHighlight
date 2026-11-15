#!/usr/bin/env python3
"""探測：哪些 YouTube 頻道的 NBA 精華在指定地區（預設台灣）可以播放、可以嵌入。

用法：YOUTUBE_API_KEY=xxx python3 scripts/probe_sources.py [--date 2026-11-13] [--region TW]
每次約用 100×搜尋次數 + 少量單位的額度。只用來研究，不影響網站資料。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch  # noqa: E402


def api(path: str, key: str, **q):
    return fetch.get_json(fetch.YT_API + path + "?" + urllib.parse.urlencode(q), {"X-Goog-Api-Key": key})


def playable(item: dict, region: str) -> tuple[bool, str]:
    cd = item.get("contentDetails", {})
    st = item.get("status", {})
    rr = cd.get("regionRestriction") or {}
    if "allowed" in rr and region not in rr["allowed"]:
        return False, f"只允許 {len(rr['allowed'])} 區，不含 {region}"
    if region in rr.get("blocked", []):
        return False, f"封鎖 {region}（共封鎖 {len(rr['blocked'])} 區）"
    if not st.get("embeddable", True):
        return False, "禁止嵌入"
    return True, "OK"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="2026-11-13")
    ap.add_argument("--region", default="TW")
    ap.add_argument("--games", type=int, default=4, help="搜尋幾場")
    args = ap.parse_args()
    key = os.environ["YOUTUBE_API_KEY"].strip()
    d = date.fromisoformat(args.date)

    games = fetch.fetch_games(d)
    print(f"== {d} 共 {len(games)} 場，搜尋前 {args.games} 場；地區 {args.region}\n")

    # 1) 目前網站用的 NBA 官方影片
    day_file = fetch.DATA_DIR / f"{d.isoformat()}.json"
    if day_file.exists():
        ids = [g["video"]["id"] for g in json.loads(day_file.read_text())["games"] if g.get("video")]
        data = api("videos", key, part="contentDetails,status,snippet", id=",".join(ids[:50]))
        print("== 目前使用的 NBA 官方影片")
        for it in data.get("items", []):
            ok, why = playable(it, args.region)
            print(f"  {'✅' if ok else '❌'} {why:30} {it['snippet']['title'][:70]}")
        print()

    # 2) 搜尋其他頻道
    by_channel: dict[str, list] = defaultdict(list)
    after = (d - timedelta(days=0)).isoformat() + "T00:00:00Z"
    before = (d + timedelta(days=3)).isoformat() + "T00:00:00Z"
    for g in games[: args.games]:
        q = f"{g['away']['name']} vs {g['home']['name']} highlights"
        res = api("search", key, part="snippet", q=q, type="video", maxResults=25,
                  publishedAfter=after, publishedBefore=before, regionCode=args.region)
        vids = [it["id"]["videoId"] for it in res.get("items", [])]
        if not vids:
            continue
        det = api("videos", key, part="contentDetails,status,snippet", id=",".join(vids))
        for it in det.get("items", []):
            ok, why = playable(it, args.region)
            sn = it["snippet"]
            by_channel[(sn["channelId"], sn["channelTitle"])].append(
                (ok, why, fetch.iso_duration_seconds(it["contentDetails"]["duration"]), sn["title"], q))

    print("== 搜尋到的頻道（可播放數 / 影片數）")
    rows = sorted(by_channel.items(), key=lambda kv: (-sum(v[0] for v in kv[1]), -len(kv[1])))
    for (cid, title), vids in rows:
        n_ok = sum(v[0] for v in vids)
        n_games = len({v[4] for v in vids})
        print(f"\n[{n_ok}/{len(vids)} 可播, 涵蓋 {n_games} 場] {title}  ({cid})")
        for ok, why, dur, t, _ in vids[:6]:
            print(f"    {'✅' if ok else '❌'} {dur//60:>3}分 {why:24} {t[:80]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
