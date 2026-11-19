#!/usr/bin/env python3
"""可行性探測：運動攀登（IFSC / World Climbing）與張博雅（田徑跨欄）。只用來研究。

一律用一般請求（只有 User-Agent），不偽裝成官網。
"""

from __future__ import annotations

import gzip
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch  # noqa: E402

KEY = os.environ.get("YOUTUBE_API_KEY", "").strip()
HK = {"X-Goog-Api-Key": KEY}
CHAPTER_RE = re.compile(r"^\s*\(?(\d{1,2}:)?\d{1,2}:\d{2}\)?\s+\S", re.M)


def yt(path: str, **q):
    return fetch.get_json(fetch.YT_API + path + "?" + urllib.parse.urlencode(q), HK)


def plain(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": fetch.UA, "Accept-Encoding": "gzip", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body, ce, code = r.read(), (r.headers.get("Content-Encoding") or ""), r.status
    except Exception as e:  # noqa: BLE001
        return f"ERR {e}", None
    if ce == "gzip":
        body = gzip.decompress(body)
    try:
        return f"{code} JSON", json.loads(body)
    except Exception:  # noqa: BLE001
        return f"{code} 非 JSON size={len(body)} 開頭={body[:100]!r}", None


def details(ids: list[str]) -> dict:
    out = {}
    for i in range(0, len(ids), 50):
        d = yt("videos", part="contentDetails,status,snippet", id=",".join(ids[i:i + 50]))
        for it in d.get("items", []):
            cd, st, sn = it["contentDetails"], it["status"], it["snippet"]
            rr = cd.get("regionRestriction") or {}
            ok = st.get("embeddable", True) and not ("allowed" in rr and "TW" not in rr["allowed"]) and "TW" not in rr.get("blocked", [])
            why = "" if ok else (f"allowed={len(rr.get('allowed', []))}區" if "allowed" in rr else f"blocked含TW" if rr else "不可嵌入")
            out[it["id"]] = {"ok": ok, "why": why, "dur": fetch.iso_duration_seconds(cd["duration"]),
                             "chapters": len(CHAPTER_RE.findall(sn.get("description", ""))),
                             "desc": sn.get("description", "")}
    return out


def climb() -> None:
    print("=" * 70 + "\n== A. 攀登成績資料（一般請求）\n" + "=" * 70)
    for label, url in [
        ("results 首頁", "https://ifsc.results.info/"),
        ("api seasons", "https://ifsc.results.info/api/v1/"),
        ("api season 2026", "https://ifsc.results.info/api/v1/seasons/38"),
        ("api events", "https://ifsc.results.info/api/v1/events/1405"),
        ("worldclimbing 行事曆", "https://www.worldclimbing.com/calendar"),
    ]:
        info, d = plain(url)
        print(f"   {label:20} {info[:160]}")
        if d is not None:
            print("      ", json.dumps(d, ensure_ascii=False)[:400])

    print("\n" + "=" * 70 + "\n== B. 攀登影片（台灣）\n" + "=" * 70)
    since = (datetime.now(timezone.utc) - timedelta(days=200)).isoformat(timespec="seconds").replace("+00:00", "Z")
    chans, names = Counter(), {}
    for q in ["World Climbing boulder women final", "IFSC lead women final", "World Climbing semi-final women boulder",
              "Ai Mori lead final", "Seo Chaehyun lead", "Miho Nonaka boulder"]:
        res = yt("search", part="snippet", q=q, type="video", maxResults=25, publishedAfter=since, regionCode="TW")
        for it in res.get("items", []):
            chans[it["snippet"]["channelId"]] += 1
            names[it["snippet"]["channelId"]] = it["snippet"]["channelTitle"]
    print("搜尋結果最多的頻道：")
    for cid, n in chans.most_common(6):
        print(f"   {n:3} {names[cid]} ({cid})")
    top = chans.most_common(1)[0][0]
    vids, token = [], ""
    for _ in range(8):
        q = {"part": "snippet", "playlistId": "UU" + top[2:], "maxResults": 50}
        if token:
            q["pageToken"] = token
        d = yt("playlistItems", **q)
        vids += [(it["snippet"]["resourceId"]["videoId"], it["snippet"]["title"], it["snippet"]["publishedAt"][:10]) for it in d.get("items", [])]
        token = d.get("nextPageToken", "")
        if not token:
            break
    det = details([v[0] for v in vids])
    long_ = [v for v in vids if det.get(v[0], {}).get("dur", 0) >= 600]
    print(f"\n[{names[top]}] 最近 {len(vids)} 支；台灣可播 {sum(1 for v in vids if det.get(v[0], {}).get('ok'))}；10 分鐘以上 {len(long_)} 支")
    kinds = Counter()
    for vid, t, pub in vids:
        tl = t.lower()
        k = ("final" if "final" in tl and "semi" not in tl else "semi" if "semi" in tl else "qual" if "qualif" in tl else "other")
        k += "/highlight" if "highlight" in tl else ""
        k += "/women" if "women" in tl else "/men" if " men" in f" {tl}" else ""
        kinds[k] += 1
    print("   類型統計：", kinds.most_common(12))
    print("   10 分鐘以上的影片：")
    for vid, t, pub in long_[:30]:
        x = det[vid]
        print(f"   {'✅' if x['ok'] else '❌'} {pub} {x['dur']//60:>4}分 章節{x['chapters']:>3} {x['why']:10} {t[:90]}")
    ex = next((v for v in long_ if det[v[0]]["chapters"] >= 5), None)
    if ex:
        print("\n   章節範例：", ex[1])
        print("   " + "\n   ".join(det[ex[0]]["desc"].splitlines()[:25]))


def athlete() -> None:
    print("\n" + "=" * 70 + "\n== C. 張博雅影片搜尋（台灣）\n" + "=" * 70)
    since = (datetime.now(timezone.utc) - timedelta(days=365)).isoformat(timespec="seconds").replace("+00:00", "Z")
    seen = {}
    for q in ["張博雅 跨欄", "張博雅 100公尺跨欄", "Zhang Bo-Ya hurdles", "Chang Po-Ya hurdles", "張博雅 60公尺跨欄"]:
        res = yt("search", part="snippet", q=q, type="video", maxResults=25, publishedAfter=since, regionCode="TW", relevanceLanguage="zh-Hant")
        n = 0
        for it in res.get("items", []):
            vid = it["id"]["videoId"]
            if vid not in seen:
                seen[vid] = (it["snippet"]["title"], it["snippet"]["channelTitle"], it["snippet"]["publishedAt"][:10])
                n += 1
        print(f"   「{q}」新增 {n} 支")
    det = details(list(seen))
    rel = {k: v for k, v in seen.items() if re.search(r"張博雅|Bo-?Ya|Po-?Ya", v[0], re.I)}
    print(f"\n共 {len(seen)} 支；標題含她名字 {len(rel)} 支；其中台灣可播 {sum(1 for k in rel if det.get(k, {}).get('ok'))}")
    print("頻道分布：", Counter(v[1] for v in rel.values()).most_common(10))
    for k, (t, ch, pub) in sorted(rel.items(), key=lambda kv: kv[1][2], reverse=True)[:30]:
        x = det.get(k, {})
        print(f"   {'✅' if x.get('ok') else '❌'} {pub} {x.get('dur', 0)//60:>3}:{x.get('dur', 0)%60:02d} {ch[:16]:16} {t[:80]}")


if __name__ == "__main__":
    parts = sys.argv[1:] or ["climb", "athlete"]
    if "climb" in parts:
        climb()
    if "athlete" in parts:
        athlete()
