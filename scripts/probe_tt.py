#!/usr/bin/env python3
"""桌球（WTT）可行性探測：比分資料來源 + YouTube 精華在台灣能否播放。只用來研究。"""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch  # noqa: E402

H = {"Referer": "https://www.worldtabletennis.com/", "Origin": "https://www.worldtabletennis.com",
     "Accept": "application/json, text/plain, */*"}
FD = "https://wtt-web-frontdoor-cthahjeqhbh6aqe3.a01.azurefd.net"
VM = "https://wtt-website-api-vm-frontdoor-hhaec5epbhdyfugz.a01.azurefd.net"
LIVE = "https://liveeventsapi.worldtabletennis.com"


def try_get(url: str):
    try:
        raw = fetch.get(url, H, tries=2)
        try:
            return json.loads(raw), len(raw)
        except json.JSONDecodeError:
            return raw[:300].decode("utf-8", "replace"), len(raw)
    except Exception as e:  # noqa: BLE001
        return f"ERR {e}", 0


def show(label: str, url: str, n: int = 900):
    data, size = try_get(url)
    print(f"\n--- {label}\n    {url}\n    size={size}")
    s = json.dumps(data, ensure_ascii=False)[:n] if not isinstance(data, str) else data[:n]
    print("    " + s)
    return data


def find_events(obj) -> list[dict]:
    """在不知道結構的 JSON 裡找出像賽事的 dict（有 id 和名稱）。"""
    out = []
    def walk(x):
        if isinstance(x, dict):
            keys = {k.lower() for k in x}
            if any("eventid" == k or k == "id" for k in keys) and any("name" in k for k in keys):
                out.append(x)
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(obj)
    return out


def section_data() -> None:
    print("=" * 70 + "\n== A. 比分資料來源\n" + "=" * 70)
    y = datetime.now(timezone.utc).year
    cands = [
        ("賽事清單(靜態)", f"{FD}/websitestaticapifiles/general/wtt_all_events_only_name.json"),
        ("年度行事曆", f"https://www.worldtabletennis.com/assets/json/{y}_eventcalendar.json"),
        ("賽事清單(primary)", f"{VM}/primary/api/cms/GetAllEventsOnlyWithEventName"),
        ("即將舉行", f"{FD}/websitestaticapifiles/general/wtt_upcoming_only_events_list.json"),
    ]
    events = []
    for label, url in cands:
        d = show(label, url, 600)
        if not isinstance(d, str):
            events += find_events(d)
    # 找最近的 Smash / Champions / Finals
    def name(e):
        for k, v in e.items():
            if "name" in k.lower() and isinstance(v, str):
                return v
        return ""
    def eid(e):
        for k in ("EventId", "eventId", "eventID", "Id", "id"):
            if k in e:
                return e[k]
        return None
    big = [e for e in events if any(w in name(e) for w in ("Smash", "Champions", "Finals"))]
    seen, uniq = set(), []
    for e in big:
        if eid(e) not in seen:
            seen.add(eid(e))
            uniq.append(e)
    print(f"\n大型賽事候選 {len(uniq)} 筆（顯示 id 最大的 12 筆）：")
    uniq.sort(key=lambda e: int(eid(e)) if str(eid(e)).isdigit() else 0, reverse=True)
    for e in uniq[:12]:
        print("   ", eid(e), "|", name(e), "|", {k: v for k, v in e.items() if "date" in k.lower() or "start" in k.lower()})

    # 對近期幾站試抓成績
    for e in uniq[:6]:
        i = eid(e)
        print(f"\n### 試抓成績 EventId={i} {name(e)}")
        for label, url in [
            ("OfficialResult(vm)", f"{VM}/liveeventsapi/api/cms/GetOfficialResult?EventId={i}&include_match_card=false&take=5"),
            ("OfficialResult(live)", f"{LIVE}/api/cms/GetOfficialResult?EventId={i}&include_match_card=false&take=5"),
            ("EventSchedule(vm)", f"{VM}/liveeventsapi/api/cms/GetEventSchedule?EventId={i}"),
            ("archived", f"{FD}/websitearchivedresults/{i}/official_result.json"),
        ]:
            d = show(label, url, 1500)
            if not isinstance(d, str) and d:
                break


def section_video() -> None:
    print("\n" + "=" * 70 + "\n== B. YouTube 精華（台灣）\n" + "=" * 70)
    key = os.environ["YOUTUBE_API_KEY"].strip()
    hk = {"X-Goog-Api-Key": key}
    api = lambda p, **q: fetch.get_json(fetch.YT_API + p + "?" + urllib.parse.urlencode(q), hk)  # noqa: E731

    since = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat(timespec="seconds").replace("+00:00", "Z")
    chans = Counter()
    names = {}
    for q in ["WTT Champions highlights", "WTT Smash highlights", "Harimoto highlights WTT", "Lin Yun-Ju highlights WTT", "Hina Hayata highlights"]:
        res = api("search", part="snippet", q=q, type="video", maxResults=25, publishedAfter=since, regionCode="TW")
        for it in res.get("items", []):
            sn = it["snippet"]
            chans[sn["channelId"]] += 1
            names[sn["channelId"]] = sn["channelTitle"]
    print("\n搜尋結果最多的頻道：")
    for cid, n in chans.most_common(8):
        print(f"   {n:3} {names[cid]}  ({cid})")

    for cid, _ in chans.most_common(4):
        vids, token = [], ""
        for _ in range(4):
            q = {"part": "snippet", "playlistId": "UU" + cid[2:], "maxResults": 50}
            if token:
                q["pageToken"] = token
            d = api("playlistItems", **q)
            vids += [(it["snippet"]["resourceId"]["videoId"], it["snippet"]["title"], it["snippet"]["publishedAt"]) for it in d.get("items", [])]
            token = d.get("nextPageToken", "")
            if not token:
                break
        stat = {}
        for i in range(0, len(vids), 50):
            d = api("videos", part="contentDetails,status", id=",".join(v[0] for v in vids[i:i + 50]))
            for it in d.get("items", []):
                cd, st = it["contentDetails"], it["status"]
                rr = cd.get("regionRestriction") or {}
                ok = st.get("embeddable", True) and not ("allowed" in rr and "TW" not in rr["allowed"]) and "TW" not in rr.get("blocked", [])
                stat[it["id"]] = (ok, fetch.iso_duration_seconds(cd["duration"]), cd.get("definition"), rr)
        n_ok = sum(1 for v in vids if stat.get(v[0], (False,))[0])
        print(f"\n[{names[cid]}] 最近 {len(vids)} 支，台灣可播 {n_ok} 支")
        for vid, t, pub in vids[:25]:
            ok, dur, dfn, rr = stat.get(vid, (None, 0, "", {}))
            why = "" if ok else (f"allowed={len(rr.get('allowed', []))}區" if "allowed" in rr else f"blocked={rr.get('blocked', [])[:5]}" if rr else "不可嵌入/未知")
            print(f"   {'✅' if ok else '❌'} {pub[:10]} {dur//60:>3}:{dur%60:02d} {dfn} {why:16} {t[:95]}")


if __name__ == "__main__":
    if "data" in sys.argv[1:] or len(sys.argv) == 1:
        section_data()
    if "video" in sys.argv[1:] or len(sys.argv) == 1:
        section_video()
