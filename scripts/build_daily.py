#!/usr/bin/env python3
"""把 data/cache_*.json（YouTube 原始資料）整理成網頁用的資料。不需要 API 金鑰。

輸出（格式相同，由 docs/list.js 顯示）：
  docs/data/zby.json    張博雅：每場比賽（日期・賽事）底下列出各項目／輪次的比賽影片，加一支訪問
  docs/data/climb.json  攀登：每站賽事底下列出女子抱石／先鋒的準決賽、決賽精華片段（依章節切出起訖時間）

網頁上只顯示這裡產生的標籤，不顯示 YouTube 標題（標題常寫成績或冠軍）。
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data"
OUT = ROOT / "docs" / "data"


def load(name: str) -> dict:
    p = CACHE / name
    return json.loads(p.read_text())["videos"] if p.exists() else {}


def pub(v: dict) -> datetime:
    return datetime.fromisoformat(v["published"].replace("Z", "+00:00"))


def write(name: str, data: dict) -> None:
    p = OUT / name
    old = json.loads(p.read_text()) if p.exists() else None
    if old and {k: v for k, v in old.items() if k != "updated"} == data:
        return
    data["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    p.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))


# ======================================================================== 張博雅
COMPS = [  # (正規式, 顯示名稱)；由上而下比對，先中先贏。
    # 地方／單站賽事放前面：標題常順帶提到「亞運前熱身」「達標亞運」，不能因此歸到亞運
    (r"新北.{0,4}公開賽|新北國際|臺北公開賽|台北公開賽", "新北國際田徑公開賽"),
    (r"秋季盃", "秋季盃"),
    (r"全大運|全國大專運動會|全国大专运动会", "全大運"),
    (r"大專校院田徑公開賽", "全國大專田徑公開賽"),
    (r"全運會", "全運會"),
    (r"全田錦|全國田徑錦標賽", "全國田徑錦標賽"),
    (r"臺灣省田徑|台灣省田徑", "臺灣省田徑錦標賽"),
    (r"澳門", "澳門亞洲城市田徑邀請賽"),
    (r"日本大學|日本大学", "日本大學田徑公開賽"),
    (r"木南|Kinami", "木南道孝紀念賽（日本）"),
    (r"室內田[徑径]大[獎奖]賽|室内田径大奖赛|Indoor (Track and Field|Athletics) Grand ?Prix", "中國室內田徑大獎賽"),
    (r"全[國国]田[徑径]大[獎奖]賽|Athletics Grand Prix", "中國田徑大獎賽"),
    (r"鑽石聯賽|钻石联赛|Diamond League", "鑽石聯賽"),
    (r"亞洲室內田徑|室內田径亚锦|室内田径亚锦|Asian Indoor Athletics|天津室內", "亞洲室內田徑錦標賽"),
    (r"世界室內|World Indoor", "世界室內田徑錦標賽"),
    (r"世界田徑錦標賽|世錦賽|World Athletics Championships", "世界田徑錦標賽"),
    (r"亞洲田徑錦標賽|亞錦賽|Asian Athletics Championships", "亞洲田徑錦標賽"),
    (r"亞運|アジア大会|Asian Games", "亞運"),
    (r"奧運|Olympic", "奧運"),
]
# 一年只辦一次的賽事：同名同年就是同一場（影片可能賽後幾個月才上傳）
YEARLY = {"新北國際田徑公開賽", "秋季盃", "全大運", "全國大專田徑公開賽", "全運會", "全國田徑錦標賽", "臺灣省田徑錦標賽",
          "澳門亞洲城市田徑邀請賽", "日本大學田徑公開賽", "木南道孝紀念賽（日本）", "亞洲室內田徑錦標賽", "世界室內田徑錦標賽",
          "世界田徑錦標賽", "亞洲田徑錦標賽", "亞運", "奧運"}
GENERIC_COMP = re.compile(r"([一-鿿A-Za-z0-9]{2,16}?(?:錦標賽|公開賽|邀請賽|運動會|大獎賽|聯賽|盃|Championships|Grand Prix|Games))")
DISCIPLINES = [
    (r"60\s*(公尺|米|m|M|メートル)?\s*(女子)?\s*(跨欄|栏|欄|ハードル|H\b|Hurdles)", "60 公尺跨欄"),
    (r"100\s*(公尺|米|m|M|メートル)?\s*(女子)?\s*(跨欄|栏|欄|ハードル|H\b|Hurdles)|女子100欄|百米欄|百米跨欄", "100 公尺跨欄"),
    (r"4\s*[x×]\s*100", "4×100 公尺接力"),
    (r"200\s*(公尺|米|m|M)", "200 公尺"),
    (r"(?<![0-9])100\s*(公尺|米|m|M)(?!\s*(跨欄|栏|欄|H))|百米", "100 公尺"),
]
ROUND_RE = [(r"預賽|预赛|分組|heat|Heats|晉級", "預賽"), (r"準決賽|半決賽|semi", "準決賽"), (r"計時決賽|決賽|决赛|final|Final", "決賽")]
INTERVIEW_RE = re.compile(r"受訪|直呼|展望|期許|不氣餒|豁達|狀態|心情|專訪|談|稱|讚|新聞|感言|記者會|失落|interview", re.I)
NEWS_CHANNELS = {"TSNA", "鏡新聞", "鏡報", "公視新聞網", "公視台語台新聞", "中央社攝影看世界", "緯來新聞網", "緯來體育台", "WOWSight.tw", "原視新聞網 TITV News"}
RACE_CHANNELS = {"GAGADAN": 5, "愛爾達體育家族 ELTA Sports": 4, "Sport.taiwan": 4, "运动与艺术": 3, "下港老郭": 2,
                 "翊起跑步翊起騎車": 2, "運動部 Taiwan Sports": 2, "SPORTIFY MEDIA": 1, "TrackHer": 2, "運動筆記": 1}
PREVIEW_RE = re.compile(r"なるか|に注目|注目！|Preview|直逼|驚き|鬼ごっこ", re.I)  # 賽前預告、別人的比賽
COMMENTARY_CHANNELS = {"ENG電子報", "夢幻女神館", "Japan Coverage", "JP Info TV", "Japani"}  # 圖文評論、非比賽畫面
TITLE_DATE = re.compile(r"(20\d\d)[/.\-年]?(\d{1,2})[/.\-月]?(\d{1,2})")


def first(pats, text):
    for rx, name in pats:
        if re.search(rx, text, re.I):
            return name
    return None


def zby_comp(t: str) -> str | None:
    c = first(COMPS, t)
    if c:
        return c
    m = GENERIC_COMP.search(t)
    return m.group(1) if m else None


def zby_date(v: dict) -> str:
    m = TITLE_DATE.search(v["title"])
    if m:
        try:
            return datetime(int(m[1]), int(m[2]), int(m[3])).date().isoformat()
        except ValueError:
            pass
    return pub(v).date().isoformat()


def build_zby() -> None:
    vids = load("cache_zby.json")
    clips = []
    for vid, v in vids.items():
        t = v["title"]
        if not v["playable"] or v["duration"] < 25 or v["duration"] > 25 * 60:
            continue
        comp = zby_comp(t)
        if not comp or PREVIEW_RE.search(t) or v["channel"].strip() in COMMENTARY_CHANNELS:
            continue  # 看不出是哪場比賽的（粉絲剪輯、評論等）不收
        disc, rnd = first(DISCIPLINES, t), first(ROUND_RE, t)
        if not disc and re.search(r"跨欄|跨栏|栏|欄|hurdle|ハードル", t, re.I):  # 只寫「跨欄」沒寫距離：室內是 60、室外是 100
            disc = "60 公尺跨欄" if "室內" in comp else "100 公尺跨欄"
        interview = bool(INTERVIEW_RE.search(t)) or v["channel"].strip() in NEWS_CHANNELS
        if not interview and not disc:
            continue
        clips.append({"id": vid, "t": t, "ch": v["channel"], "dur": v["duration"], "date": zby_date(v),
                      "comp": comp, "disc": disc, "round": rnd, "interview": interview})

    # 同一個賽事名稱、日期相差 30 天內 → 同一場比賽（有些影片賽後幾週才上傳）
    clips.sort(key=lambda c: c["date"])
    events: list[dict] = []
    for c in clips:
        ev = next((e for e in events if e["comp"] == c["comp"] and (
                   (c["comp"] in YEARLY and e["start"][:4] == c["date"][:4])
                   or abs((datetime.fromisoformat(e["end"]) - datetime.fromisoformat(c["date"])).days) <= 30)), None)
        if not ev:
            ev = {"comp": c["comp"], "start": c["date"], "end": c["date"], "clips": []}
            events.append(ev)
        ev["end"] = max(ev["end"], c["date"])
        ev["clips"].append(c)

    def race_score(c):
        return (RACE_CHANNELS.get(c["ch"], 0), 1 if 60 <= c["dur"] <= 15 * 60 else 0, c["dur"])

    disc_order = [d for _, d in DISCIPLINES]
    round_order = ["預賽", "準決賽", "決賽", None]
    out = []
    for ev in events:
        race_days = sorted(c["date"] for c in ev["clips"] if not c["interview"])
        if not race_days:
            continue
        ev["start"] = race_days[0]  # 比賽日期以比賽影片為準；賽前的備戰訪問不算
        ev["clips"] = [c for c in ev["clips"] if not c["interview"] or c["date"] >= race_days[0]]
        races: dict[tuple, list] = {}
        for c in ev["clips"]:
            if not c["interview"]:
                races.setdefault((c["disc"], c["round"]), []).append(c)
        # 沒標輪次的影片：如果和同項目有標輪次的影片同一天，多半是重複的就略過；不同天則保留（可能是另一輪）
        for (d, r) in list(races):
            if r is None:
                labeled_days = {c["date"] for k, cs in races.items() if k[0] == d and k[1] for c in cs}
                if labeled_days:
                    keep = [c for c in races[(d, r)] if c["date"] not in labeled_days]
                    if keep:
                        races[(d, r)] = keep
                    else:
                        del races[(d, r)]
        items = []
        for (d, r), cs in sorted(races.items(), key=lambda kv: (disc_order.index(kv[0][0]), round_order.index(kv[0][1]))):
            best = sorted(cs, key=race_score, reverse=True)
            extra = "" if r else ("（另一段影片）" if any(k[0] == d and k[1] for k in races) else "")
            items.append({"label": f"{d}{' ' + r if r else ''}{extra}", "kind": "race",
                          "video": {"id": best[0]["id"], "duration": best[0]["dur"]},
                          "alts": [{"id": c["id"], "duration": c["dur"]} for c in best[1:3]]})
        ivs = sorted((c for c in ev["clips"] if c["interview"]), key=lambda c: (1 if INTERVIEW_RE.search(c["t"]) else 0, -abs(c["dur"] - 120)), reverse=True)
        if ivs:
            items.append({"label": "賽後訪問", "kind": "interview", "warn": True,
                          "video": {"id": ivs[0]["id"], "duration": ivs[0]["dur"]}})
        if not any(i["kind"] == "race" for i in items):
            continue  # 只有訪問、沒有比賽畫面的不列
        out.append({"key": f"{ev['comp']}-{ev['start']}", "date": ev["start"],
                    "name": ev["comp"], "items": items})
    out.sort(key=lambda e: e["date"], reverse=True)
    write("zby.json", {"title": "張博雅", "events": out})
    print(f"張博雅：{len(clips)} 支可用影片 → {len(out)} 場比賽")


# ======================================================================== 攀登
CH_LINE = re.compile(r"^\s*\(?((?:\d{1,2}:)?\d{1,2}:\d{2})\)?\s*[-–—:]?\s*(.+?)\s*$", re.M)
ROUND_TITLE = re.compile(r"^(Women's|Men's)?\s*(Boulder|Lead)\s+(semi-finals?|finals?)\s*\|\s*(.+?)\s+(20\d\d)\s*$", re.I)
CITY_ZH = {"Keqiao": "柯橋", "Wujiang": "吳江", "Bern": "伯恩", "Comunidad de Madrid": "馬德里", "Madrid": "馬德里",
           "Prague": "布拉格", "Innsbruck": "因斯布魯克", "Chamonix": "夏慕尼", "Koper": "科佩爾", "Salt Lake City": "鹽湖城",
           "Santiago": "聖地牙哥", "Seoul": "首爾", "Fukuoka": "福岡", "Briançon": "布里昂松", "Villars": "維拉爾",
           "Shanghai": "上海", "Paris": "巴黎", "Los Angeles": "洛杉磯", "Jakarta": "雅加達"}
DISC_ZH = {"boulder": "抱石", "lead": "先鋒"}
NOT_COMP = re.compile(r"Athlete(s)? of the Week|Interview with|Visiting|workshop|INSIDE the|Understanding|ART of|ACROSS INDIA|They said|Get to know|Meet the|Behind the scenes", re.I)


def secs(ts: str) -> int:
    parts = [int(x) for x in ts.split(":")]
    return parts[0] * 3600 + parts[1] * 60 + parts[2] if len(parts) == 3 else parts[0] * 60 + parts[1]


def build_climb() -> None:
    vids = load("cache_climb.json")
    # 1) 從完整轉播的標題找出每站賽事（城市、日期、有哪些項目）；青年賽、速度、團體、帕拉不收
    events: dict[str, dict] = {}
    for v in vids.values():
        m = ROUND_TITLE.match(v["title"].strip())
        if not m or re.search(r"U1\d|Youth|Para|Speed|Team", v["title"], re.I):
            continue
        city = m[4].strip()
        e = events.setdefault(city, {"city": city, "year": m[5], "start": pub(v), "end": pub(v), "discs": set(), "final_day": {}})
        e["start"], e["end"] = min(e["start"], pub(v)), max(e["end"], pub(v))
        disc = m[2].lower()
        e["discs"].add(disc)
        if m[3].lower().startswith("final") and (m[1] or "").lower() != "men's":  # 女子決賽（先鋒是男女同場）
            e["final_day"][disc] = pub(v)

    # 2) 台灣可播的精華集（6～30 分鐘），依說明欄章節切出女子準決賽／決賽
    out = {c: [] for c in events}
    episodes = []
    for vid, v in vids.items():
        if not v["playable"] or not (360 <= v["duration"] <= 30 * 60) or NOT_COMP.search(v["title"]):
            continue
        text = v["title"] + "\n" + v["description"]
        city = next((c for c in events if c in text), None)
        if not city:  # 說明沒寫城市就用日期判斷
            city = next((c for c, e in events.items() if e["start"] - timedelta(days=1) <= pub(v) <= e["end"] + timedelta(days=2)), None)
        if not city:
            continue
        episodes.append((city, vid, v))
        chs = [(secs(a), b) for a, b in CH_LINE.findall(v["description"])]
        for i, (t0, label) in enumerate(chs):
            lab = label.lower()
            m = re.search(r"(women's\s+)?(boulder|lead)\s+(semi-finals?|finals?)\s+highlights", lab)
            if not m:
                continue
            women = bool(m[1])
            if not women and "men's" in lab:
                continue  # 男子片段不收
            disc, rnd = m[2], ("準決賽" if m[3].startswith("semi") else "決賽")
            if not women and rnd == "決賽":
                continue  # 沒標性別的決賽多半是男子或混合，不收
            t1 = chs[i + 1][0] if i + 1 < len(chs) else v["duration"]
            out[city].append({"disc": disc, "round": rnd, "mixed": not women, "pub": v["published"],
                              "video": {"id": vid, "duration": v["duration"], "start": t0, "end": t1}})
        # 標題是女子決賽、章節只標了準決賽（說明欄被截斷）→ 準決賽之後就是決賽
        tm = re.search(r"women.?s (boulder|lead) final", v["title"], re.I)
        if tm:
            d = tm[1].lower()
            semi = [(i, c) for i, c in enumerate(chs) if re.search(r"women.?s\s+" + d + r"\s+semi", c[1], re.I)]
            has_final = any(re.search(r"women.?s\s+" + d + r"\s+final", c[1], re.I) for c in chs)
            if semi and not has_final and semi[0][0] + 1 < len(chs):
                out[city].append({"disc": d, "round": "決賽", "mixed": False, "pub": v["published"],
                                  "video": {"id": vid, "duration": v["duration"], "start": chs[semi[0][0] + 1][0]}})

    # 3) 沒有章節可切的：用女子決賽當天～隔天的精華集整集（可能含男子）
    for city, e in events.items():
        for disc, day in e["final_day"].items():
            if any(s["disc"] == disc and s["round"] == "決賽" for s in out[city]):
                continue
            cands = [(c, vid, v) for c, vid, v in episodes if c == city
                     and day - timedelta(hours=6) <= pub(v) <= day + timedelta(days=1, hours=12)
                     and (disc in (v["title"] + v["description"]).lower() or "final" in v["title"].lower())]
            if cands:
                _, vid, v = sorted(cands, key=lambda x: ("final" in x[2]["title"].lower(), "women" in (x[2]["title"] + x[2]["description"]).lower()), reverse=True)[0]
                out[city].append({"disc": disc, "round": "決賽", "mixed": True, "pub": v["published"], "whole": True,
                                  "video": {"id": vid, "duration": v["duration"]}})

    result = []
    for city, segs in out.items():
        e = events[city]
        items = []
        for disc in ("boulder", "lead"):
            for rnd in ("準決賽", "決賽"):
                cand = [s for s in segs if s["disc"] == disc and s["round"] == rnd]
                if not cand:
                    continue
                s = sorted(cand, key=lambda s: (s.get("whole", False), s["mixed"], s["pub"]))[0]
                if s.get("whole"):
                    label = f"女子{DISC_ZH[disc]} 準決賽＋決賽（整集精華，含男子）"
                else:
                    label = f"女子{DISC_ZH[disc]} {rnd}" + ("（男女合併）" if s["mixed"] else "")
                items.append({"label": label, "kind": "seg", "video": s["video"]})
        if not items:
            continue
        name = f"{CITY_ZH.get(city, city)} {e['year']}"
        result.append({"key": f"{city}-{e['year']}", "date": e["start"].date().isoformat(), "end": e["end"].date().isoformat(),
                       "name": name, "sub": "World Climbing Series ・ " + "／".join(DISC_ZH[d] for d in sorted(e["discs"])),
                       "items": items})
    result.sort(key=lambda e: e["date"], reverse=True)
    write("climb.json", {"title": "攀登", "events": result})
    print(f"攀登：{len(events)} 站賽事 → {len(result)} 站有可播片段，共 {sum(len(e['items']) for e in result)} 段")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    build_zby()
    build_climb()
    sys.exit(0)
