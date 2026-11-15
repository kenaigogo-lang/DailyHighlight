#!/usr/bin/env python3
"""探測：哪些 YouTube 頻道的 NBA 精華在指定地區（預設台灣）可以播放、可以嵌入。

用法：YOUTUBE_API_KEY=xxx python3 scripts/probe_sources.py [--date 2026-11-13] [--region TW]
每次約用 100×搜尋次數 + 少量單位的額度。只用來研究，不影響網站資料。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.parse
from collections import defaultdict
from datetime import date, datetime, timedelta
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


def coverage(key: str, channels: list[str], days: list[date], region: str) -> None:
    """檢查每個頻道對這幾天所有比賽的覆蓋率（用上傳清單，很省額度）。"""
    all_games = [(d, g) for d in days for g in fetch.fetch_games(d) if g["state"] == "final"]
    earliest = min(datetime.fromisoformat(g["start"].replace("Z", "+00:00")) for _, g in all_games)
    print(f"== 覆蓋率：{days[-1]}～{days[0]} 共 {len(all_games)} 場已結束比賽，地區 {region}\n")
    for cid in channels:
        playlist = "UU" + cid[2:]
        vids, token = [], ""
        for _ in range(10):
            q = {"part": "snippet", "playlistId": playlist, "maxResults": 50}
            if token:
                q["pageToken"] = token
            data = api("playlistItems", key, **q)
            stop = False
            for it in data.get("items", []):
                sn = it["snippet"]
                pub = datetime.fromisoformat(sn["publishedAt"].replace("Z", "+00:00"))
                if pub < earliest:
                    stop = True
                    continue
                vids.append({"id": sn["resourceId"]["videoId"], "title": sn["title"], "published": pub})
            token = data.get("nextPageToken", "")
            if stop or not token:
                break
        name = data["items"][0]["snippet"]["channelTitle"] if data.get("items") else cid
        # 每支影片的可播放狀態
        ok_ids = set()
        for i in range(0, len(vids), 50):
            det = api("videos", key, part="contentDetails,status", id=",".join(v["id"] for v in vids[i:i + 50]))
            for it in det.get("items", []):
                if playable(it, region)[0]:
                    ok_ids.add(it["id"])
        full = second = 0
        miss = []
        for d, g in all_games:
            a, h = fetch.norm(g["away"]["name"]), fetch.norm(g["home"]["name"])
            mine = [v for v in vids if f" {a} " in f" {fetch.norm(v['title'])} " and f" {h} " in f" {fetch.norm(v['title'])} "
                    and v["published"] >= datetime.fromisoformat(g["start"].replace("Z", "+00:00"))
                    and v["published"] <= datetime.fromisoformat(g["start"].replace("Z", "+00:00")) + timedelta(days=2)
                    and v["id"] in ok_ids]
            has_full = any("FULL GAME" in fetch.norm(v["title"]) for v in mine)
            has_2nd = any(re.search(r"3RD\s*4TH|3RD AND 4TH|SECOND HALF|2ND HALF", fetch.norm(v["title"]).replace("+", " ")) for v in mine)
            full += has_full
            second += has_2nd
            if not has_full:
                miss.append(f"{d} {g['away']['abbr']}@{g['home']['abbr']}")
        print(f"[{name}] 影片 {len(vids)} 支、台灣可播 {len(ok_ids)} 支")
        print(f"    全場精華 {full}/{len(all_games)} 場，下半場(3rd+4th) {second}/{len(all_games)} 場")
        if miss:
            print(f"    缺全場：{', '.join(miss[:12])}{' …' if len(miss) > 12 else ''}")
        sample = [v["title"] for v in vids[:4]]
        for t in sample:
            print(f"    例：{t[:90]}")
        print()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="2026-11-13")
    ap.add_argument("--region", default="TW")
    ap.add_argument("--games", type=int, default=4, help="搜尋幾場")
    ap.add_argument("--channels", default="", help="逗號分隔的頻道 ID：改做覆蓋率檢查")
    ap.add_argument("--days", type=int, default=6, help="覆蓋率檢查往回幾天")
    args = ap.parse_args()
    key = os.environ["YOUTUBE_API_KEY"].strip()
    d = date.fromisoformat(args.date)
    if args.channels:
        coverage(key, [c.strip() for c in args.channels.split(",") if c.strip()],
                 [d - timedelta(days=i) for i in range(args.days)], args.region)
        return 0

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
