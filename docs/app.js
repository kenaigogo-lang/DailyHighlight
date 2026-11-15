"use strict";

// ---------------------------------------------------------------- 設定
const SECOND_HALF_RATIO = 0.5;   // 從影片的幾 % 開始播
const STOP_BEFORE_END = 1.5;     // 結尾前幾秒自動停，避免 YouTube 片尾推薦
const DATES_SHOWN = 7;

const TEAM_ZH = {
  ATL: "老鷹", BOS: "塞爾提克", BKN: "籃網", CHA: "黃蜂", CHI: "公牛", CLE: "騎士",
  DAL: "獨行俠", DEN: "金塊", DET: "活塞", GS: "勇士", HOU: "火箭", IND: "溜馬",
  LAC: "快艇", LAL: "湖人", MEM: "灰熊", MIA: "熱火", MIL: "公鹿", MIN: "灰狼",
  NO: "鵜鶘", NY: "尼克", OKC: "雷霆", ORL: "魔術", PHI: "76人", PHX: "太陽",
  POR: "拓荒者", SAC: "國王", SA: "馬刺", TOR: "暴龍", UTAH: "爵士", WSH: "巫師",
};
// 各隊代表色（D 球衣撞色主題用）
const TEAM_COLOR = {
  ATL: "#e03a3e", BOS: "#007a33", BKN: "#2b2b2b", CHA: "#1d1160", CHI: "#ce1141", CLE: "#860038",
  DAL: "#00538c", DEN: "#0e2240", DET: "#c8102e", GS: "#1d428a", HOU: "#ce1141", IND: "#002d62",
  LAC: "#c8102e", LAL: "#552583", MEM: "#5d76a9", MIA: "#98002e", MIL: "#00471b", MIN: "#0c2340",
  NO: "#0c2340", NY: "#f58426", OKC: "#007ac1", ORL: "#0077c0", PHI: "#006bb6", PHX: "#e56020",
  POR: "#e03a3e", SAC: "#5a2d81", SA: "#5b6670", TOR: "#ce1141", UTAH: "#002b5c", WSH: "#002b5c",
};
const SKINS = ["C", "D", "E"];
// 兩隊顏色太像（例如老鷹、公牛都是紅）就把主隊改深灰
function colorDist(a, b) {
  const rgb = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  const [x, y] = [rgb(a), rgb(b)];
  return Math.hypot(x[0] - y[0], x[1] - y[1], x[2] - y[2]);
}
const WEEK = ["日", "一", "二", "三", "四", "五", "六"];
const BOX_COLS = [
  ["MIN", "時間"], ["PTS", "得分"], ["REB", "籃板"], ["AST", "助攻"], ["STL", "抄截"],
  ["BLK", "阻攻"], ["FG", "投籃"], ["3PT", "三分"], ["FT", "罰球"], ["TO", "失誤"], ["+/-", "+/-"],
];

const $ = (sel, el = document) => el.querySelector(sel);
const logo = (abbr) => `https://a.espncdn.com/i/teamlogos/nba/500/${abbr.toLowerCase()}.png`;
const zh = (t) => TEAM_ZH[t.abbr] || t.name;

// ---------------------------------------------------------------- 資料
async function getJSON(path) {
  const r = await fetch(`${path}?t=${Date.now()}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json();
}

function fmtDateChip(iso) {
  const d = new Date(iso + "T12:00:00");
  return `${d.getMonth() + 1}/${d.getDate()}<small>(${WEEK[d.getDay()]})</small>`;
}

function fmtTipoff(iso) {
  return new Intl.DateTimeFormat("zh-TW", {
    timeZone: "Asia/Taipei", month: "numeric", day: "numeric",
    hour: "2-digit", minute: "2-digit", hour12: false,
  }).format(new Date(iso)) + " 開打（台灣）";
}

function fmtUpdated(iso) {
  return new Intl.DateTimeFormat("zh-TW", {
    timeZone: "Asia/Taipei", month: "numeric", day: "numeric",
    hour: "2-digit", minute: "2-digit", hour12: false,
  }).format(new Date(iso));
}

// ---------------------------------------------------------------- 畫面
let dates = [];
let current = null;

async function init() {
  try {
    dates = (await getJSON("data/index.json")).dates || [];
  } catch {
    dates = [];
  }
  if (!dates.length) {
    showEmpty("還沒有資料，等第一次自動更新後就會出現。");
    return;
  }
  window.addEventListener("hashchange", () => load(pickDate()));
  load(pickDate());
}

function pickDate() {
  const h = location.hash.slice(1);
  return dates.includes(h) ? h : dates[0];
}

function renderDates() {
  const nav = $("#dates");
  nav.innerHTML = "";
  for (const d of dates.slice(0, DATES_SHOWN)) {
    const b = document.createElement("button");
    b.className = "date-chip";
    b.type = "button";
    b.innerHTML = fmtDateChip(d);
    b.setAttribute("aria-current", d === current ? "true" : "false");
    b.title = `美國時間 ${d}`;
    b.onclick = () => { location.hash = d; };
    nav.append(b);
  }
}

function showEmpty(msg) {
  const el = $("#empty");
  el.textContent = msg;
  el.hidden = false;
}

async function load(date) {
  current = date;
  renderDates();
  closeAllPlayers();
  $("#games").innerHTML = "";
  $("#empty").hidden = true;
  let day;
  try {
    day = await getJSON(`data/${date}.json`);
  } catch {
    showEmpty("資料讀取失敗，請稍後再試。");
    return;
  }
  if (date !== current) return;

  const games = day.games;
  const total = games.length;
  const withVideo = games.filter((g) => g.video).length;
  const skipped = games.filter((g) => g.state === "skipped").length;
  const waiting = total - withVideo - skipped;
  const parts = [`美國 ${date.slice(5).replace("-", "/")} · 共 <b>${total}</b> 場`, `<b>${withVideo}</b> 場有影片`];
  if (waiting > 0) parts.push(`<span class="waiting">⏳ ${waiting} 場影片還沒上架</span>`);
  if (skipped > 0) parts.push(`${skipped} 場延期／取消`);
  parts.push(`更新於 ${fmtUpdated(day.updated)}`);
  $("#summary").innerHTML = parts.join(" · ");

  const list = $("#games");
  let rank = 0;
  for (const g of games) {
    list.append(renderGame(g, g.state === "final" ? ++rank : null));
  }
}

function renderGame(g, rank) {
  const li = $("#tpl-game").content.firstElementChild.cloneNode(true);
  $(".rank", li).textContent = rank ?? "–";
  $(".stub", li).textContent = rank ? `No.${rank}` : "—";
  if (rank) li.dataset.rank = rank; else li.dataset.pending = "1";
  const ca = TEAM_COLOR[g.away.abbr] || "#333", ch = TEAM_COLOR[g.home.abbr] || "#555";
  li.style.setProperty("--a", ca);
  li.style.setProperty("--h", colorDist(ca, ch) < 90 ? "#26282e" : ch);
  for (const side of ["away", "home"]) {
    const t = g[side];
    const el = $(`.team.${side}`, li);
    $("img", el).src = logo(t.abbr);
    $(".name", el).innerHTML = `${zh(t)}<small>${t.name}</small>`;
  }
  $(".time", li).textContent = fmtTipoff(g.start);
  $(".tag", li).textContent = g.note || "";

  const play = $(".play", li);
  const status = $(".status", li);
  const box = $(".box", li);
  if (g.state === "final" && g.video) {
    play.onclick = () => openPlayer(li, g.video);
  } else {
    play.remove();
    status.textContent =
      g.state === "skipped" ? "延期／取消" :
      g.state === "pending" ? "⏳ 比賽尚未結束" :
      "⏳ 影片還沒上架（會自動補抓）";
  }
  if (g.boxscore) {
    box.onclick = () => toggleBox(li, g);
  } else {
    box.remove();
  }
  return li;
}

// ---------------------------------------------------------------- Box score（含比分，要二次確認）
function toggleBox(li, g) {
  const el = $(".boxscore", li);
  const btn = $(".box", li);
  if (!el.hidden) {
    el.hidden = true;
    btn.textContent = "⚠️ 查看數據（含比分）";
    return;
  }
  if (!el.dataset.ok && !confirm("數據會直接顯示比分，確定要看嗎？")) return;
  el.dataset.ok = "1";
  if (!el.innerHTML) el.innerHTML = boxHTML(g);
  el.hidden = false;
  btn.textContent = "收起數據";
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function boxHTML(g) {
  const teams = g.boxscore.teams;
  const byAbbr = Object.fromEntries(teams.map((t) => [t.abbr, t]));
  const order = [g.away.abbr, g.home.abbr].map((a) => byAbbr[a]).filter(Boolean);

  // 各節比分
  const n = Math.max(...order.map((t) => t.linescore.length));
  const head = Array.from({ length: n }, (_, i) => `<th>${i < 4 ? i + 1 : "OT" + (n > 5 ? i - 3 : "")}</th>`).join("");
  const rows = order.map((t) => {
    const sum = t.linescore.reduce((a, b) => a + (parseInt(b, 10) || 0), 0);
    return `<tr><td>${esc(TEAM_ZH[t.abbr] || t.abbr)}</td>${t.linescore.map((x) => `<td>${esc(x)}</td>`).join("")}<td class="pts">${sum}</td></tr>`;
  }).join("");
  let html = `<div class="scroll"><table><thead><tr><th></th>${head}<th>總分</th></tr></thead><tbody>${rows}</tbody></table></div>`;

  // 球員數據
  for (const t of order) {
    const idx = BOX_COLS.map(([k]) => t.labels.indexOf(k));
    const th = BOX_COLS.map(([, zhLabel]) => `<th>${zhLabel}</th>`).join("");
    let body = "";
    let benchMarked = false;
    for (const p of t.players) {
      let cls = "";
      if (!p.starter && !benchMarked) { cls = "bench-start"; benchMarked = true; }
      if (p.dnp) {
        body += `<tr class="dnp ${cls}"><td>${esc(p.name)}</td><td colspan="${BOX_COLS.length}" style="text-align:left">${esc(p.reason || "未上場")}</td></tr>`;
        continue;
      }
      const cells = idx.map((i, c) => `<td${BOX_COLS[c][0] === "PTS" ? ' class="pts"' : ""}>${esc(i >= 0 ? p.stats[i] : "")}</td>`).join("");
      body += `<tr class="${cls}"><td>${esc(p.name)}<span class="pos">${esc(p.pos)}</span></td>${cells}</tr>`;
    }
    if (t.totals && t.totals.length) {
      body += `<tr class="total"><td>全隊</td>${idx.map((i) => `<td>${esc(i >= 0 ? t.totals[i] : "")}</td>`).join("")}</tr>`;
    }
    html += `<h3><img src="${logo(t.abbr)}" alt="">${esc(TEAM_ZH[t.abbr] || t.abbr)}</h3>
      <div class="scroll"><table><thead><tr><th>球員</th>${th}</tr></thead><tbody>${body}</tbody></table></div>`;
  }
  return html;
}

// ---------------------------------------------------------------- 播放器（防暴雷）
let ytReady = null;
function loadYT() {
  if (ytReady) return ytReady;
  ytReady = new Promise((resolve) => {
    window.onYouTubeIframeAPIReady = resolve;
    const s = document.createElement("script");
    s.src = "https://www.youtube.com/iframe_api";
    document.head.append(s);
  });
  return ytReady;
}

const players = new Set();

function closeAllPlayers() {
  for (const p of [...players]) p.close();
}

async function openPlayer(li, video) {
  closeAllPlayers();
  const wrap = $(".player", li);
  const frame = $(".frame", wrap);
  const cover = $(".cover", wrap);
  const coverBtn = $(".cover-btn", wrap);
  const coverText = $(".cover-text", wrap);
  const playBtn = $(".play", li);
  wrap.hidden = false;
  playBtn.disabled = true;

  const showCover = (text, btn = true) => {
    cover.hidden = false;
    coverText.textContent = text;
    coverBtn.hidden = !btn;
  };
  showCover("載入中…", false);

  await loadYT();
  const ytEl = document.createElement("div");
  $(".yt", wrap).replaceWith(ytEl);
  ytEl.className = "yt";

  // iPhone 不支援把一般元素全螢幕，這時改用 YouTube 播放器自己的全螢幕鈕
  const canOwnFullscreen = !!(document.fullscreenEnabled || document.webkitFullscreenEnabled);
  let duration = video.duration || 0;
  // video.half = 這支影片本身就只有下半場（3rd+4th），從 0 秒開始
  const halfAt = () => (video.half ? 0 : Math.floor((duration || 0) * SECOND_HALF_RATIO));
  $(".fromstart", wrap).hidden = !!video.half;
  let timer = null;
  let stoppedAtEnd = false;
  let started = false;

  const sound = $(".sound", wrap);
  sound.hidden = true;
  const showSoundHint = () => {
    sound.hidden = false;
    sound.textContent = "🔇 靜音播放中，點這裡開聲音";
    sound.onclick = () => {
      player.unMute();
      player.setVolume(100);
      setTimeout(() => {
        if (player.isMuted && player.isMuted()) {
          sound.textContent = "🔇 請點影片畫面，再按左下角的喇叭開聲音";
        } else {
          sound.hidden = true;
        }
      }, 600);
    };
  };
  // 最後手段：讓使用者直接點 YouTube 自己的播放鈕
  const revealYouTube = () => { if (!started) cover.hidden = true; };

  const player = new YT.Player(ytEl, {
    videoId: video.id,
    playerVars: {
      autoplay: 1, playsinline: 1, rel: 0, iv_load_policy: 3,
      modestbranding: 1, fs: canOwnFullscreen ? 0 : 1,
      start: video.half || !duration ? 0 : halfAt(),
    },
    events: {
      onReady: () => {
        if (!duration) {
          duration = player.getDuration() || 0;
          if (duration && !video.half) player.seekTo(halfAt(), true);
        }
        player.playVideo();
        // iPhone 等會擋「有聲自動播放」：改成靜音播放（一定允許），再讓使用者開聲音
        setTimeout(() => {
          if (started) return;
          player.mute();
          player.playVideo();
          showSoundHint();
          setTimeout(revealYouTube, 2500);
        }, 1200);
      },
      onStateChange: (e) => {
        const S = YT.PlayerState;
        if (e.data === S.PLAYING) {
          started = true;
          stoppedAtEnd = false;
          cover.hidden = true;
        } else if (e.data === S.PAUSED) {
          if (!stoppedAtEnd) showCover("已暫停");
        } else if (e.data === S.ENDED) {
          stoppedAtEnd = true;
          showCover("播完了");
        }
      },
    },
  });

  // 結尾前自動停止，片尾推薦就不會出現
  timer = setInterval(() => {
    if (!sound.hidden && player.isMuted && !player.isMuted()) sound.hidden = true;
    if (!player.getCurrentTime || !duration) return;
    const t = player.getCurrentTime();
    if (!stoppedAtEnd && t >= duration - STOP_BEFORE_END && player.getPlayerState() === YT.PlayerState.PLAYING) {
      stoppedAtEnd = true;
      player.pauseVideo();
      showCover("播完了");
    }
  }, 250);

  const seek = (t) => {
    stoppedAtEnd = false;
    player.seekTo(Math.max(0, t), true);
    player.playVideo();
  };
  coverBtn.onclick = () => {
    if (stoppedAtEnd) seek(halfAt());
    else player.playVideo();
    // 如果瀏覽器不讓外部按鈕播放，就把 YouTube 自己的播放鈕露出來
    setTimeout(() => {
      if (player.getPlayerState() !== YT.PlayerState.PLAYING) cover.hidden = true;
    }, 1000);
  };
  $(".back30", wrap).onclick = () => seek(player.getCurrentTime() - 30);
  $(".half", wrap).onclick = () => seek(halfAt());
  $(".fromstart", wrap).onclick = () => seek(0);
  const fsBtn = $(".fs", wrap);
  fsBtn.hidden = !canOwnFullscreen;
  fsBtn.onclick = () => {
    if (document.fullscreenElement || document.webkitFullscreenElement) {
      (document.exitFullscreen || document.webkitExitFullscreen).call(document);
    } else {
      (frame.requestFullscreen || frame.webkitRequestFullscreen).call(frame);
    }
  };

  const handle = {
    close() {
      clearInterval(timer);
      try { player.destroy(); } catch {}
      const fresh = document.createElement("div");
      fresh.className = "yt";
      const cur = $(".yt, iframe", frame);
      if (cur) cur.replaceWith(fresh);
      wrap.hidden = true;
      playBtn.disabled = false;
      players.delete(handle);
    },
  };
  $(".close", wrap).onclick = () => handle.close();
  players.add(handle);
  wrap.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

// 換風格按鈕：依序切換 C → D → E
document.getElementById("skin-btn").onclick = () => {
  const root = document.documentElement;
  root.dataset.skin = SKINS[(SKINS.indexOf(root.dataset.skin) + 1) % SKINS.length];
};

init();
