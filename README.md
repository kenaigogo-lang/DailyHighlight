# 🏀 NBA 每日精華（DailyHighlight）

每天自動整理前一天（美國時間）所有 NBA 比賽的官方精華影片，**依精彩程度排序**，**畫面上完全不暴雷**。

## 功能

- 影片來源：只用**在台灣可播放**的影片（NBA 官方精華在台灣被封鎖）。依 `scripts/fetch.py` 的 `SOURCES` 順序：
  1. GAMETIME HIGHLIGHTS 的 Full Game Highlights（約 9 分鐘，從中間開始播）
  2. Ximo Pierto、NBA 官方（備用）
- 每支影片都會用 YouTube API 檢查地區限制與能否嵌入；`scripts/probe_sources.py`（Actions「探測可播放的影片來源」）可重新評估各頻道
- 點「▶ 看下半場」直接從影片中段開始播，可用「⏪ 30 秒／下半場／從頭看」微調
- 精彩度排序：越精彩越上面，排序依據只在後端計算，前端看不到任何分數
- 防暴雷：不使用 YouTube 縮圖、不顯示影片長度、暫停與片尾時用自己的畫面蓋住 YouTube 推薦影片
- Box score：預設收合，點開前會再確認一次（因為會看到比分）
- 回看最近 7 天
- 每 20 分鐘自動檢查（NBA 與桌球同一個流程；GitHub 排程常延遲或跳過，建議另用 cron-job.org 觸發）；還沒上架的影片會在之後的執行自動補抓，頁面上會顯示還缺幾場

## 精彩度怎麼算

`scripts/fetch.py` 的 `excitement_key()`，數字越小越精彩：

```
最終分差 + 0.7 × 最後一節剩 2:00 時的分差 − 6 × 延長賽節數
```

## 架構

```
GitHub Actions（.github/workflows/update.yml）
  └─ scripts/fetch.py
       ├─ ESPN 公開 API：賽程、比分、box score、逐球紀錄
       ├─ YouTube Data API：各來源頻道上傳清單 + 台灣可播檢查
       └─ 寫入 docs/data/YYYY-MM-DD.json、docs/data/index.json
GitHub Pages（docs/）
  └─ index.html + app.js + style.css，只讀 JSON，純靜態
```

- 已完整（全部比賽結束且都有影片）的日期不會再重抓
- 每次執行約使用 YouTube API 額度 10～40 單位（每日免費 10,000）

## 設定

1. **YouTube API 金鑰**：Settings → Secrets and variables → Actions → 新增 `YOUTUBE_API_KEY`
2. **GitHub Pages**：Settings → Pages → Source 選「Deploy from a branch」，Branch 選 `main`、資料夾選 `/docs`
3. **第一次手動執行**：Actions → 「更新每日精華」→ Run workflow

## 本機測試

```bash
YOUTUBE_API_KEY=xxx python3 scripts/fetch.py            # 自動決定日期
YOUTUBE_API_KEY=xxx python3 scripts/fetch.py --date 2026-11-13
cd docs && python3 -m http.server 8000                   # 開 http://localhost:8000
```

沒設金鑰時只會更新比分，不會找影片。
