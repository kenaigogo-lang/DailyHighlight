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


def raw_get(url: str):
    """處理 gzip 壓縮；回傳 (json 或 None, 說明)。"""
    import gzip, zlib, urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": fetch.UA, "Accept-Encoding": "gzip", **H})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body, enc = r.read(), (r.headers.get("Content-Encoding") or "")
    except Exception as e:  # noqa: BLE001
        return None, f"ERR {e}"
    for dec in (lambda b: b, gzip.decompress, zlib.decompress):
        try:
            return json.loads(dec(body)), f"ok enc={enc} size={len(body)}"
        except Exception:  # noqa: BLE001
            continue
    return None, f"無法解碼 enc={enc} size={len(body)} head={body[:8]!r}"


def walk_dicts(x):
    if isinstance(x, dict):
        yield x
        for v in x.values():
            yield from walk_dicts(v)
    elif isinstance(x, list):
        for v in x:
            yield from walk_dicts(v)


def section_data() -> None:
    print("=" * 70 + "\n== A. 比分資料來源\n" + "=" * 70)
    cal, info = raw_get("https://www.worldtabletennis.com/assets/json/2026_eventcalendar.json")
    rows = [r for blk in cal for r in blk.get("rows", [])] if isinstance(cal, list) else []
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    big = [r for r in rows if any(w in (r.get("EventName") or "") for w in ("Smash", "Champions", "Finals"))
           and "Youth" not in (r.get("EventName") or "")]
    print(f"行事曆 {info}，共 {len(rows)} 筆，大型賽事 {len(big)} 筆：")
    for r in sorted(big, key=lambda r: r["StartDateTime"]):
        print(f"   {r['EventId']} | {r['StartDateTime'][:10]}~{r['EndDateTime'][:10]} | {r.get('EventType')} | {r['EventName']}")
    done = [r for r in big if datetime.fromisoformat(r["EndDateTime"]) < now]
    done.sort(key=lambda r: r["EndDateTime"], reverse=True)
    for r in done[:2]:
        i = r["EventId"]
        print(f"\n### 已結束：{i} {r['EventName']}")
        best = None
        for label, url in [
            ("archived officialresult", f"{FD}/websitearchivedresults/{i}/officialresult/officialresult.json"),
            ("live(vm) match_card", f"{VM}/liveeventsapi/api/cms/GetOfficialResult?EventId={i}&include_match_card=true&take=1000"),
            ("live(eastasia)", f"https://wtt-website-live-events-api-prod-cmfzgabgbzhphabb.eastasia-01.azurewebsites.net/api/cms/GetOfficialResult?EventId={i}&include_match_card=true&take=1000"),
            ("static take10", f"{FD}/websitestaticapifiles/{i}/{i}_take_10_official_results.json"),
        ]:
            d, info = raw_get(url)
            n = len(d) if isinstance(d, list) else (1 if d else 0)
            print(f"   {label:24} {info}  筆數={n}")
            if d and best is None:
                best = d
        if not best:
            continue
        items = best if isinstance(best, list) else [best]
        print("   第一筆 keys:", list(items[0].keys())[:40] if isinstance(items[0], dict) else type(items[0]))
        print("   第一筆內容:", json.dumps(items[0], ensure_ascii=False)[:2500])
        subs, rounds, orgs = Counter(), Counter(), Counter()
        for dct in walk_dicts(items):
            for k, v in dct.items():
                kl = k.lower()
                if isinstance(v, str) and len(v) < 40:
                    if kl in ("subeventname", "subeventtype", "subeventdescription"):
                        subs[v] += 1
                    elif "round" in kl or kl in ("phase", "stagename"):
                        rounds[v] += 1
                    elif kl in ("organisationcode", "orgcode", "countrycode", "nationality", "organizationcode"):
                        orgs[v] += 1
        print("   項目:", subs.most_common(12))
        print("   輪次:", rounds.most_common(15))
        print("   國籍(前15):", orgs.most_common(15))


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
