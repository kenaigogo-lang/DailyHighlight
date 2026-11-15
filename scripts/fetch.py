#!/usr/bin/env python3
"""每日 NBA 精華資料抓取。

由 GitHub Actions 每天執行（台灣時間 15:00、16:00）：
  1. 從 ESPN 抓目標日期所有比賽、box score、逐球紀錄
  2. 計算精彩度（只在這裡算，不寫進輸出檔）並排序
  3. 依 SOURCES 順序找每場在台灣可播放的精華（優先下半場專用版）
  4. 寫入 docs/data/YYYY-MM-DD.json 與 docs/data/index.json

已經「完整」（所有比賽結束且影片都找到）的日期不會再重抓，
沒抓齊的日期會在之後的執行中自動補找，最多回補 BACKFILL_DAYS 天。

只用 Python 標準函式庫，不需要安裝任何套件。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "docs" / "data"

ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={d}"
ESPN_SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={id}"

YT_API = "https://www.googleapis.com/youtube/v3/"
REGION = "TW"              # 影片必須能在這個地區播放

# 影片來源，依優先順序。kind:
#   "second_half" = 只有下半場（3rd+4th）的影片，從 0 秒開始播
#   "full"        = 全場精華，網頁從中間開始播
# NBA 官方頻道的精華在台灣被封鎖（只開放 24 區），所以放最後、只在可播時使用。
SOURCES = [
    {"channel": "UC_X_2gCH9tvEKBwW8sibCtg", "name": "TRAV13SO100", "kind": "second_half"},
    {"channel": "UC0LrZO9wORIqn_aRJtKdgfA", "name": "GAMETIME HIGHLIGHTS", "kind": "full"},
    {"channel": "UCS7kvhJx431xCKuSgkBaUWw", "name": "Ximo Pierto", "kind": "full"},
    {"channel": "UCWJ2lWNubArHWmf3FIHbfcQ", "name": "NBA", "kind": "full"},
]
VALID_SRCS = {x["name"] for x in SOURCES}

ET_TZ = ZoneInfo("America/New_York")
BACKFILL_DAYS = 7          # 往回補找幾天
YT_MAX_PAGES = 10          # 每個頻道最多翻幾頁上傳清單（每頁 50 支、1 單位額度）
DONE_STATES = {"post"}     # ESPN status.type.state
SKIP_NAMES = {"STATUS_POSTPONED", "STATUS_CANCELED", "STATUS_CANCELLED", "STATUS_SUSPENDED"}

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]

UA = "Mozilla/5.0 (compatible; DailyHighlight/1.0)"


# ---------------------------------------------------------------- HTTP

def get(url: str, headers: dict | None = None, tries: int = 4) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            # 4xx（金鑰錯誤等）除了 404/429 不重試；YouTube RSS 偶爾會亂回 404/500
            if i == tries - 1 or (400 <= e.code < 500 and e.code not in (404, 429)):
                raise
        except (urllib.error.URLError, TimeoutError):
            if i == tries - 1:
                raise
        time.sleep(2 * (i + 1))
    raise RuntimeError("unreachable")


def get_json(url: str, headers: dict | None = None):
    return json.loads(get(url, headers))


# ---------------------------------------------------------------- ESPN

def clock_seconds(clock: str) -> float:
    """'2:00' -> 120, '16.5' -> 16.5"""
    clock = (clock or "0").strip()
    if ":" in clock:
        m, s = clock.split(":", 1)
        return int(m) * 60 + float(s)
    try:
        return float(clock)
    except ValueError:
        return 0.0


def margin_at_two_minutes(plays: list, final_period: int, final_margin: int) -> int:
    """最後一節（含延長賽）剩 2:00 時的分差。沒有逐球資料就用最終分差。"""
    last = None
    for p in plays:
        if (p.get("period") or {}).get("number") != final_period:
            continue
        if clock_seconds((p.get("clock") or {}).get("displayValue", "0")) >= 120:
            last = p
        else:
            break
    if last is None:
        return final_margin
    try:
        return abs(int(last["homeScore"]) - int(last["awayScore"]))
    except (KeyError, TypeError, ValueError):
        return final_margin


def excitement_key(final_margin: int, margin_2min: int, ot_periods: int) -> float:
    """越小越精彩。延長賽每一節額外加分（減值）。"""
    return final_margin + 0.7 * margin_2min - 6 * ot_periods


def parse_boxscore(summary: dict) -> dict:
    """整理成前端好用的格式：每隊的球員數據 + 各節比分。"""
    teams = []
    comp = summary["header"]["competitions"][0]
    linescores = {
        c["team"]["abbreviation"]: [l.get("displayValue", "") for l in c.get("linescores", [])]
        for c in comp["competitors"]
    }
    for t in summary.get("boxscore", {}).get("players", []):
        abbr = t["team"]["abbreviation"]
        st = t["statistics"][0]
        players = []
        for a in st.get("athletes", []):
            ath = a.get("athlete", {})
            players.append({
                "name": ath.get("shortName") or ath.get("displayName", ""),
                "pos": (ath.get("position") or {}).get("abbreviation", ""),
                "starter": bool(a.get("starter")),
                "dnp": bool(a.get("didNotPlay")),
                "reason": a.get("reason", ""),
                "stats": a.get("stats", []),
            })
        teams.append({
            "abbr": abbr,
            "labels": st.get("labels", []),
            "players": players,
            "totals": st.get("totals", []),
            "linescore": linescores.get(abbr, []),
        })
    return {"teams": teams}


def fetch_games(d: date) -> list[dict]:
    sb = get_json(ESPN_SCOREBOARD.format(d=d.strftime("%Y%m%d")))
    games = []
    for ev in sb.get("events", []):
        comp = ev["competitions"][0]
        status = ev["status"]["type"]
        side = {c["homeAway"]: c for c in comp["competitors"]}
        home, away = side["home"], side["away"]
        g = {
            "id": ev["id"],
            "start": ev["date"],
            "home": {"abbr": home["team"]["abbreviation"], "name": home["team"]["name"]},
            "away": {"abbr": away["team"]["abbreviation"], "name": away["team"]["name"]},
            "state": "final" if status["state"] in DONE_STATES else (
                "skipped" if status["name"] in SKIP_NAMES else "pending"),
            "note": (comp.get("notes") or [{}])[0].get("headline", "") if comp.get("notes") else "",
            "video": None,
            "boxscore": None,
            "_key": None,
        }
        if g["state"] == "final":
            summary = get_json(ESPN_SUMMARY.format(id=ev["id"]))
            final_margin = abs(int(home["score"]) - int(away["score"]))
            final_period = int(ev["status"].get("period") or 4)
            m2 = margin_at_two_minutes(summary.get("plays", []), final_period, final_margin)
            g["_key"] = excitement_key(final_margin, m2, max(0, final_period - 4))
            g["boxscore"] = parse_boxscore(summary)
        games.append(g)
    return games


# ---------------------------------------------------------------- YouTube

def iso_duration_seconds(s: str) -> int:
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", s or "")
    if not m:
        return 0
    d, h, mi, se = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + se


def yt_uploads(key: str, channel_id: str, since: datetime) -> list[dict]:
    """翻某頻道的上傳清單，直到早於 since。"""
    headers = {"X-Goog-Api-Key": key}
    playlist = "UU" + channel_id[2:]
    videos, token = [], ""
    for _ in range(YT_MAX_PAGES):
        q = {"part": "snippet", "playlistId": playlist, "maxResults": 50}
        if token:
            q["pageToken"] = token
        data = get_json(YT_API + "playlistItems?" + urllib.parse.urlencode(q), headers)
        stop = False
        for it in data.get("items", []):
            sn = it["snippet"]
            pub = datetime.fromisoformat(sn["publishedAt"].replace("Z", "+00:00"))
            if pub < since:
                stop = True
                continue
            videos.append({"id": sn["resourceId"]["videoId"], "title": sn["title"], "published": pub})
        token = data.get("nextPageToken", "")
        if stop or not token:
            break
    return videos


def yt_details(key: str, ids: list[str]) -> dict[str, dict]:
    """影片長度 + 是否能在 REGION 播放、能否嵌入。"""
    out = {}
    for i in range(0, len(ids), 50):
        q = {"part": "contentDetails,status", "id": ",".join(ids[i:i + 50])}
        data = get_json(YT_API + "videos?" + urllib.parse.urlencode(q), {"X-Goog-Api-Key": key})
        for it in data.get("items", []):
            cd, st = it.get("contentDetails", {}), it.get("status", {})
            rr = cd.get("regionRestriction") or {}
            ok = st.get("embeddable", True) and st.get("privacyStatus", "public") == "public"
            if "allowed" in rr and REGION not in rr["allowed"]:
                ok = False
            if REGION in rr.get("blocked", []):
                ok = False
            out[it["id"]] = {"duration": iso_duration_seconds(cd.get("duration", "")), "playable": ok}
    return out


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9 ]", " ", s.upper())).strip()


SECOND_HALF_RE = re.compile(r"\b3RD 4TH\b|\b3RD AND 4TH\b|\bSECOND HALF\b|\b2ND HALF\b")


def title_kind(title: str) -> str | None:
    t = norm(title)
    if SECOND_HALF_RE.search(t):
        return "second_half"
    if "FULL GAME HIGHLIGHTS" in t:
        return "full"
    return None


def match_candidates(game: dict, game_date: date, videos: list[dict], kind: str) -> list[dict]:
    """標題要含兩隊隊名、類型相符，並在開賽後 2 天內上傳；寫了比賽日期的優先，EXTENDED 優先。"""
    away, home = norm(game["away"]["name"]), norm(game["home"]["name"])
    date_str = norm(f"{MONTHS[game_date.month - 1]} {game_date.day}, {game_date.year}")
    start = datetime.fromisoformat(game["start"].replace("Z", "+00:00"))
    cands = []
    for v in videos:
        t = norm(v["title"])
        if title_kind(v["title"]) != kind:
            continue
        if f" {away} " not in f" {t} " or f" {home} " not in f" {t} ":
            continue
        if not (start <= v["published"] <= start + timedelta(days=2)):
            continue
        cands.append(((date_str in t), t.startswith("EXTENDED"), v))
    cands.sort(key=lambda c: (c[0], c[1]), reverse=True)
    return [c[2] for c in cands]


def find_videos(key: str, need: list[tuple[date, dict]]) -> None:
    """依 SOURCES 順序替每場找第一支「台灣可播」的影片，直接寫進 game["video"]。"""
    earliest = min(datetime.fromisoformat(g["start"].replace("Z", "+00:00")) for _, g in need)
    remaining = list(need)
    for src in SOURCES:
        if not remaining:
            break
        videos = yt_uploads(key, src["channel"], earliest)
        picks = {}
        for d, g in remaining:
            c = match_candidates(g, d, videos, src["kind"])
            if c:
                picks[g["id"]] = c
        det = yt_details(key, list({v["id"] for c in picks.values() for v in c})) if picks else {}
        still = []
        for d, g in remaining:
            ok = [v for v in picks.get(g["id"], []) if det.get(v["id"], {}).get("playable")]
            if ok:
                v = ok[0]
                g["video"] = {"id": v["id"], "duration": det[v["id"]]["duration"],
                              "half": src["kind"] == "second_half", "src": src["name"]}
            else:
                still.append((d, g))
        print(f"  來源 {src['name']}: 上傳 {len(videos)} 支，這次配到 {len(remaining) - len(still)} 場")
        remaining = still


# ---------------------------------------------------------------- 主流程

def target_dates(now_utc: datetime) -> list[date]:
    """主要日期 = 美東時間往前推 12 小時的那天（台灣 15:00 執行 → 美國昨天）。"""
    main = (now_utc.astimezone(ET_TZ) - timedelta(hours=12)).date()
    return [main - timedelta(days=i) for i in range(BACKFILL_DAYS)]


def load_day(d: date) -> dict | None:
    p = DATA_DIR / f"{d.isoformat()}.json"
    return json.loads(p.read_text()) if p.exists() else None


def valid_video(v: dict | None) -> bool:
    return bool(v) and v.get("src") in VALID_SRCS


def is_complete(day: dict) -> bool:
    return all(g["state"] == "skipped" or (g["state"] == "final" and valid_video(g["video"])) for g in day["games"])


def build_day(d: date, prev: dict | None) -> tuple[dict, list[dict]]:
    """回傳 (day 資料, 需要找影片的比賽清單)。"""
    games = fetch_games(d)
    games.sort(key=lambda g: (g["_key"] is None, g["_key"] if g["_key"] is not None else 0, g["start"]))
    old_videos = {g["id"]: g["video"] for g in (prev or {}).get("games", []) if valid_video(g.get("video"))}
    need = []
    for g in games:
        g.pop("_key", None)
        if g["id"] in old_videos:
            g["video"] = old_videos[g["id"]]
        elif g["state"] == "final":
            need.append(g)
    return {"date": d.isoformat(), "games": games}, need


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="只處理指定日期 YYYY-MM-DD（美國日期）")
    ap.add_argument("--force", action="store_true", help="已完整的日期也重抓")
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    dates = [date.fromisoformat(args.date)] if args.date else target_dates(now)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    todo: list[tuple[date, dict, list]] = []
    for d in dates:
        prev = load_day(d)
        if prev and is_complete(prev) and not args.force:
            print(f"{d}: 已完整，略過")
            continue
        day, need = build_day(d, prev)
        if not day["games"]:
            print(f"{d}: 沒有比賽")
            continue
        todo.append((d, day, need))

    need_all = [(d, g) for d, _, need in todo for g in need]
    yt_error = None
    key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if need_all:
        if not key:
            yt_error = RuntimeError("沒有 YOUTUBE_API_KEY")
            print("❌ 沒有 YOUTUBE_API_KEY，無法找影片")
        else:
            try:
                print(f"YouTube：替 {len(need_all)} 場找影片（地區 {REGION}）")
                find_videos(key, need_all)
            except Exception as e:  # 影片找不到不影響比分寫入，下次執行會再補
                yt_error = e
                print(f"❌ YouTube 查詢失敗：{e}")

    for d, day, _ in todo:
        day["complete"] = is_complete(day)
        day["updated"] = now.isoformat(timespec="seconds")
        (DATA_DIR / f"{d.isoformat()}.json").write_text(
            json.dumps(day, ensure_ascii=False, separators=(",", ":")))
        n_final = sum(g["state"] == "final" for g in day["games"])
        n_video = sum(bool(g["video"]) for g in day["games"])
        print(f"{d}: {len(day['games'])} 場，已結束 {n_final}，有影片 {n_video}")

    # index.json：列出所有已有資料的日期（新到舊）
    all_days = sorted((p.stem for p in DATA_DIR.glob("????-??-??.json")), reverse=True)
    (DATA_DIR / "index.json").write_text(json.dumps({"dates": all_days}, separators=(",", ":")))
    return 1 if yt_error else 0


if __name__ == "__main__":
    sys.exit(main())
