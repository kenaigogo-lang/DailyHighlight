#!/usr/bin/env python3
"""每日收集：張博雅相關影片（YouTube 搜尋）與 World Climbing 頻道影片。

只負責把 YouTube 的原始資料（標題、頻道、長度、說明、台灣能否播放）存進 data/cache_*.json；
整理成網頁用的資料由 build_daily.py 負責（不需要 API 金鑰，可在本機反覆調整規則）。

額度：張博雅每天 2～5 次搜尋（每次 100 單位）；攀登只讀上傳清單（每頁 1 單位）。
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch  # noqa: E402

CACHE_DIR = fetch.ROOT / "data"
ZBY_CACHE = CACHE_DIR / "cache_zby.json"
CLIMB_CACHE = CACHE_DIR / "cache_climb.json"

ZBY_NAME_RE = re.compile(r"張博雅|张博雅|Bo-?\s?Ya\b|Po-?\s?Ya\b", re.I)
ZBY_QUERIES_DAILY = ["張博雅 跨欄", "Zhang Bo-Ya hurdles"]
ZBY_QUERIES_FULL = ZBY_QUERIES_DAILY + ["張博雅 100公尺跨欄", "Chang Po-Ya hurdles", "張博雅 田徑", "張博雅 決賽", "張博雅 預賽"]

CLIMB_CHANNEL = "UC2MGuhIaOP6YLpUx106kTQw"   # World Climbing（原 IFSC）
CLIMB_SINCE = "2026-01-01T00:00:00+00:00"


def yt(key: str, path: str, **q):
    return fetch.get_json(fetch.YT_API + path + "?" + urllib.parse.urlencode(q), {"X-Goog-Api-Key": key})


def load(p: Path) -> dict:
    return json.loads(p.read_text()) if p.exists() else {"videos": {}}


def save(p: Path, d: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=0, sort_keys=True))


def add_details(key: str, cache: dict, ids: list[str], with_desc: bool) -> None:
    for i in range(0, len(ids), 50):
        d = yt(key, "videos", part="snippet,contentDetails,status", id=",".join(ids[i:i + 50]))
        for it in d.get("items", []):
            sn, cd, st = it["snippet"], it["contentDetails"], it["status"]
            rr = cd.get("regionRestriction") or {}
            ok = (st.get("embeddable", True) and st.get("privacyStatus", "public") == "public"
                  and not ("allowed" in rr and "TW" not in rr["allowed"]) and "TW" not in rr.get("blocked", []))
            v = {"title": sn["title"], "channel": sn["channelTitle"], "published": sn["publishedAt"],
                 "duration": fetch.iso_duration_seconds(cd.get("duration", "")), "playable": bool(ok)}
            if with_desc:
                v["description"] = sn.get("description", "")
            cache["videos"][it["id"]] = v


def collect_zby(key: str) -> None:
    cache = load(ZBY_CACHE)
    now = datetime.now(timezone.utc)
    first = not cache["videos"]
    queries = ZBY_QUERIES_FULL if first else ZBY_QUERIES_DAILY
    since = now - timedelta(days=365 if first else 7)
    found = set()
    for q in queries:
        res = yt(key, "search", part="snippet", q=q, type="video", maxResults=50, order="date",
                 publishedAfter=since.isoformat(timespec="seconds").replace("+00:00", "Z"), regionCode="TW")
        for it in res.get("items", []):
            if ZBY_NAME_RE.search(it["snippet"]["title"]):
                found.add(it["id"]["videoId"])
    new = [i for i in found if i not in cache["videos"]]
    add_details(key, cache, new, with_desc=False)
    cache["updated"] = now.isoformat(timespec="seconds")
    save(ZBY_CACHE, cache)
    print(f"張博雅：搜尋 {len(queries)} 次，命中 {len(found)} 支，新增 {len(new)} 支，快取共 {len(cache['videos'])} 支")


def collect_climb(key: str) -> None:
    cache = load(CLIMB_CACHE)
    since = datetime.fromisoformat(CLIMB_SINCE)
    if cache["videos"]:  # 之後只抓新的
        latest = max(datetime.fromisoformat(v["published"].replace("Z", "+00:00")) for v in cache["videos"].values())
        since = max(since, latest - timedelta(days=3))
    vids = fetch.yt_uploads(key, CLIMB_CHANNEL, since, max_pages=40)
    new = [v["id"] for v in vids if v["id"] not in cache["videos"]]
    add_details(key, cache, new, with_desc=True)
    cache["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    save(CLIMB_CACHE, cache)
    print(f"攀登：上傳清單 {len(vids)} 支，新增 {len(new)} 支，快取共 {len(cache['videos'])} 支")


def main() -> int:
    key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not key:
        print("❌ 沒有 YOUTUBE_API_KEY")
        return 1
    parts = sys.argv[1:] or ["zby", "climb"]
    err = 0
    for name, fn in (("zby", collect_zby), ("climb", collect_climb)):
        if name in parts:
            try:
                fn(key)
            except Exception as e:  # noqa: BLE001
                print(f"❌ {name} 收集失敗：{e}")
                err = 1
    return err


if __name__ == "__main__":
    sys.exit(main())
