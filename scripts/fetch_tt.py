#!/usr/bin/env python3
"""桌球（WTT／ITTF 大賽）精華資料抓取。

收錄賽事：WTT 大滿貫、冠軍賽、球星挑戰賽、總決賽、ITTF 世界盃、世錦賽（個人）、奧運、亞運、亞洲錦標賽
收錄比賽：男女單打，32 強起；32/16 強只收日本、台灣選手與陳熠，八強起全收。

資料來源（WTT 官網讀取的公開靜態檔，不需偽裝來源）：
  - 行事曆：www.worldtabletennis.com/assets/json/{年}_eventcalendar.json
  - 賽事結束後：websitearchivedresults/{id}/officialresult/officialresult.json（完整）
  - 賽事進行中：websitestaticapifiles/{id}/{id}_take_10_official_results.json（最新 10 場，需頻繁輪詢累積）
影片：WTT 官方 YouTube 頻道（台灣可播），用 YouTube Data API 配對並檢查地區限制。

輸出：docs/data/tt/{eventId}.json、docs/data/tt/index.json
"""

from __future__ import annotations

import gzip
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch  # noqa: E402  共用：get、YouTube API 工具、norm
from tt_names import zh_name  # noqa: E402

try:
    import brotli  # type: ignore
except ImportError:  # 靜態檔是 br 壓縮；沒有 brotli 時改要 gzip
    brotli = None

DATA_DIR = fetch.ROOT / "docs" / "data" / "tt"
CAL_URL = "https://www.worldtabletennis.com/assets/json/{y}_eventcalendar.json"
FD = "https://wtt-web-frontdoor-cthahjeqhbh6aqe3.a01.azurefd.net"
ARCHIVE_URL = FD + "/websitearchivedresults/{i}/officialresult/officialresult.json"
LATEST_URL = FD + "/websitestaticapifiles/{i}/{i}_take_10_official_results.json"

WTT_CHANNEL = "UC9ckyA_A3MfXUa0ttxMoIZw"
YT_MAX_PAGES = 30
WINDOW_DAYS = 30            # 結束後多久內還會補找影片
FOCUS_ORGS = {"JPN", "TPE"}
FOCUS_NAMES = {"CHEN YI"}   # 陳熠
ROUNDS = ["R32", "R16", "QF", "SF", "F"]
EARLY = {"R32", "R16"}

TYPE_ZH = {
    "WTT Grand Smash": "大滿貫", "WTT Champions": "冠軍賽", "WTT Star Contender": "球星挑戰賽",
    "WTT Finals": "總決賽", "Singles World Cup": "世界盃",
}
NAME_RULES = [  # (正規式, 中文類型)，比對賽事名稱
    (re.compile(r"Olympic", re.I), "奧運"),
    (re.compile(r"\bAsian Games\b", re.I), "亞運"),
    (re.compile(r"World Table Tennis Championships(?!.*Team)", re.I), "世錦賽"),
    (re.compile(r"Asian Championships(?!.*(Youth|Junior|Cadet|Team))", re.I), "亞錦賽"),
]


# ---------------------------------------------------------------- 讀取

def get_json_any(url: str):
    """WTT 靜態檔會回 br/gzip 壓縮。"""
    enc = "gzip, br" if brotli else "gzip"
    req = urllib.request.Request(url, headers={"User-Agent": fetch.UA, "Accept-Encoding": enc})
    with urllib.request.urlopen(req, timeout=30) as r:
        body, ce = r.read(), (r.headers.get("Content-Encoding") or "").lower()
    if ce == "br":
        body = brotli.decompress(body)
    elif ce == "gzip":
        body = gzip.decompress(body)
    return json.loads(body)


def try_json(url: str):
    try:
        return get_json_any(url)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    except json.JSONDecodeError:  # 不存在的年份會回官網 HTML
        return None


def event_type_zh(row: dict) -> str | None:
    if row.get("EventType") in TYPE_ZH:
        return TYPE_ZH[row["EventType"]]
    name = row.get("EventName") or ""
    if "Youth" in name or "Veteran" in name or "Masters" in name:
        return None
    for rx, zh in NAME_RULES:
        if rx.search(name):
            return zh
    return None


def load_calendar(now: datetime) -> list[dict]:
    events = {}
    for y in sorted({now.year - 1, now.year, now.year + 1}):
        cal = try_json(CAL_URL.format(y=y))
        for blk in cal or []:
            for r in blk.get("rows", []):
                tz = event_type_zh(r)
                if not tz or not r.get("EventId"):
                    continue
                events[r["EventId"]] = {
                    "id": r["EventId"],
                    "name": (r.get("EventName") or "").strip(),
                    "type": tz,
                    "city": r.get("City") or "",
                    "start": r["StartDateTime"][:10],
                    "end": r["EndDateTime"][:10],
                }
    return list(events.values())


# ---------------------------------------------------------------- 比賽整理

ROUND_TEXT = [("round of 32", "R32"), ("round of 16", "R16"), ("quarterfinal", "QF"),
              ("semifinal", "SF"), ("final", "F")]


def parse_round(desc: str) -> str | None:
    parts = [p.strip().lower() for p in desc.split(" - ")]
    seg = parts[1] if len(parts) > 1 else desc.lower()
    for k, v in ROUND_TEXT:
        if seg.startswith(k):
            return v
    return None  # 64 強、資格賽等不收


def parse_utc(s: str | None) -> str | None:
    """'11/08/2026 17:30:00' → ISO UTC"""
    if not s:
        return None
    try:
        return datetime.strptime(s, "%m/%d/%Y %H:%M:%S").replace(tzinfo=timezone.utc).isoformat()
    except ValueError:
        return None


def is_focus(p: dict) -> bool:
    return p["org"] in FOCUS_ORGS or " ".join(p["name"].upper().split()) in FOCUS_NAMES


def parse_match(raw: dict) -> dict | None:
    mc = raw.get("match_card") or {}
    sub = (mc.get("subEventName") or "").lower()
    if "singles" not in sub:
        return None
    ev = "WS" if sub.startswith("women") else "MS"
    rnd = parse_round(mc.get("subEventDescription") or "")
    if not rnd:
        return None
    comps = mc.get("competitiors") or []
    if len(comps) != 2 or any(c.get("irm") for c in comps):  # 退賽／未賽不收
        return None
    players = [{"name": c.get("competitiorName", ""), "org": c.get("competitiorOrg", "")} for c in comps]
    if rnd in EARLY and not any(is_focus(p) for p in players):
        return None
    games = []
    for g in (mc.get("resultsGameScores") or mc.get("gameScores") or "").split(","):
        m = re.fullmatch(r"\s*(\d+)-(\d+)\s*", g)
        if m and (m[1], m[2]) != ("0", "0"):
            games.append([int(m[1]), int(m[2])])
    if not games:
        return None
    for p in players:
        z = zh_name(p["name"])
        if z:
            p["zh"] = z
    return {
        "id": raw.get("documentCode") or mc.get("documentCode"),
        "ev": ev,
        "round": rnd,
        "start": parse_utc((mc.get("matchDateTime") or {}).get("startDateUTC")),
        "p": players,
        "games": games,
        "video": None,
    }


def excitement(m: dict) -> float:
    """越小越精彩：局數差距、總得分差、deuce 局數。"""
    wa = sum(1 for a, b in m["games"] if a > b)
    wb = len(m["games"]) - wa
    pts = sum(a - b for a, b in m["games"])
    deuce = sum(1 for a, b in m["games"] if max(a, b) > 11)
    return abs(wa - wb) * 8 + abs(pts) * 0.25 - deuce * 2.5


# ---------------------------------------------------------------- 影片

def name_tokens(name: str) -> tuple[list[str], list[str]]:
    """'LIN Yun-Ju' → 全部字詞 ['LIN','YUN','JU']，姓 ['LIN']（開頭全大寫的字）。"""
    words = name.replace("-", " ").split()
    fam = []
    for w in words:
        if w.isupper() and len(w) > 1:
            fam.append(w)
        else:
            break
    return [fetch.norm(w) for w in words], [fetch.norm(w) for w in (fam or words[:1])]


def has_words(title: str, words: list[str]) -> bool:
    t = f" {title} "
    return all(f" {w} " in t for w in words)


def match_video(m: dict, videos: list[dict]) -> dict | None:
    """標題要含兩位選手名字、MS/WS，並在比賽開始後 5 天內上傳。精華優先，其次 FULL MATCH。"""
    if not m["start"]:
        return None
    start = datetime.fromisoformat(m["start"])
    cands = []
    for strict in (True, False):  # 先比對全名，找不到再只比對姓
        for v in videos:
            t = fetch.norm(v["title"])
            if f" {m['ev']} " not in f" {t} ":
                continue
            if not (start - timedelta(hours=1) <= v["published"] <= start + timedelta(days=5)):
                continue
            ok = all(has_words(t, name_tokens(p["name"])[0 if strict else 1]) for p in m["p"])
            if ok:
                cands.append((t.startswith("FULL MATCH"), v))
        if cands:
            break
    cands.sort(key=lambda c: c[0])  # 精華（False）排前面
    return [c[1] for c in cands] or None


def find_videos(key: str, need: list[dict], since: datetime) -> None:
    videos = fetch.yt_uploads(key, WTT_CHANNEL, since, max_pages=YT_MAX_PAGES)
    picks = {m["id"]: match_video(m, videos) for m in need}
    ids = list({v["id"] for c in picks.values() if c for v in c})
    det = fetch.yt_details(key, ids) if ids else {}
    found = 0
    for m in need:
        for v in picks.get(m["id"]) or []:
            d = det.get(v["id"])
            if d and d["playable"] and d["duration"] >= 60:  # 排除 Shorts
                m["video"] = {"id": v["id"], "duration": d["duration"], "src": "WTT",
                              "full": fetch.norm(v["title"]).startswith("FULL MATCH")}
                found += 1
                break
    print(f"  WTT 頻道 {len(videos)} 支，這次配到 {found}/{len(need)} 場")


# ---------------------------------------------------------------- 主流程

def status_of(ev: dict, today: str) -> str:
    if today < ev["start"]:
        return "upcoming"
    if today <= ev["end"]:
        return "live"
    return "done"


def main() -> int:
    now = datetime.now(timezone.utc)
    today = now.date().isoformat()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    events = load_calendar(now)
    print(f"行事曆：收錄類型賽事 {len(events)} 站")

    lo = (now - timedelta(days=WINDOW_DAYS)).date().isoformat()
    hi = (now + timedelta(days=1)).date().isoformat()
    active = [e for e in events if e["start"] <= hi and e["end"] >= lo]
    error = None
    key = os.environ.get("YOUTUBE_API_KEY", "").strip()

    for ev in sorted(active, key=lambda e: e["start"]):
        path = DATA_DIR / f"{ev['id']}.json"
        prev = json.loads(path.read_text()) if path.exists() else None
        if prev and prev.get("complete"):
            continue
        st = status_of(ev, today)
        if st == "upcoming":
            continue
        print(f"== {ev['id']} {ev['name']}（{st}）")
        try:
            archive = try_json(ARCHIVE_URL.format(i=ev["id"]))
            raw = archive if archive else (try_json(LATEST_URL.format(i=ev["id"])) or [])
        except Exception as e:  # noqa: BLE001
            error = e
            print(f"  ❌ 成績讀取失敗：{e}")
            continue
        matches = {m["id"]: m for m in (prev or {}).get("matches", [])}
        added = 0
        for r in raw:
            m = parse_match(r)
            if not m:
                continue
            old = matches.get(m["id"])
            if old and old.get("video"):
                m["video"] = old["video"]
            if not old:
                added += 1
            matches[m["id"]] = m
        ms = list(matches.values())
        print(f"  {'完整成績' if archive else '最新 10 場'}：收錄 {len(ms)} 場（新增 {added}）")

        need = [m for m in ms if not m.get("video")]
        # 進行中的賽事每次都找影片；已結束的每小時找一次就好（省 YouTube 額度）
        if need and key and (st == "live" or now.minute < 20 or os.environ.get("TT_FORCE_VIDEO")):
            try:
                since = datetime.fromisoformat(ev["start"]).replace(tzinfo=timezone.utc) - timedelta(days=1)
                find_videos(key, need, since)
            except Exception as e:  # noqa: BLE001
                error = e
                print(f"  ❌ YouTube 查詢失敗：{e}")

        # 同一輪內依精彩度排序（分數只在這裡用，不寫進檔案）
        ms.sort(key=lambda m: (m["ev"], ROUNDS.index(m["round"]), excitement(m)))
        expired = today > (datetime.fromisoformat(ev["end"]) + timedelta(days=WINDOW_DAYS)).date().isoformat()
        complete = bool(archive) and (all(m.get("video") for m in ms) or expired)
        out = {**ev, "status": st, "archived": bool(archive), "complete": complete, "matches": ms}
        if prev and {k: v for k, v in prev.items() if k != "updated"} == out:
            continue  # 沒變化就不寫，避免無意義的 commit
        out["updated"] = now.isoformat(timespec="seconds")
        path.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))

    # index.json：有資料的賽事（新到舊）＋即將開始的下一站
    have = []
    for p in DATA_DIR.glob("*.json"):
        if p.name == "index.json":
            continue
        d = json.loads(p.read_text())
        if not d["matches"] and d["status"] == "done":
            continue  # 已結束但官方沒有成績資料的賽事不列出
        have.append({**{k: d[k] for k in ("id", "name", "type", "city", "start", "end", "status")}, "n": len(d["matches"])})
    upcoming = sorted((e for e in events if e["start"] > today), key=lambda e: e["start"])[:1]
    idx = {"events": sorted(have, key=lambda e: e["start"], reverse=True),
           "next": [{**e, "status": "upcoming"} for e in upcoming]}
    (DATA_DIR / "index.json").write_text(json.dumps(idx, ensure_ascii=False, separators=(",", ":")))
    return 1 if error else 0


if __name__ == "__main__":
    sys.exit(main())
