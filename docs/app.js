"use strict";

// ---------------------------------------------------------------- 設定
const SECOND_HALF_RATIO = 0.8;   // 從影片的幾 % 開始播（大約第四節）
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
const WEEK = ["日", "一", "二", "三", "四", "五", "六"];
const BOX_COLS = [
  ["MIN", "時間"], ["PTS", "得分"], ["REB", "籃板"], ["AST", "助攻"], ["STL", "抄截"],
  ["BLK", "阻攻"], ["FG", "投籃"], ["3PT", "三分"], ["FT", "罰球"], ["TO", "失誤"], ["+/-", "+/-"],
];

const logo = (abbr) => `https://a.espncdn.com/i/teamlogos/nba/500/${abbr.toLowerCase()}.png`;
const zh = (t) => TEAM_ZH[t.abbr] || t.name;


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
  $("#summary").innerHTML = parts.join(" · ") + " ·";

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
    play.onclick = () => openPlayer(li, g.video, { startRatio: SECOND_HALF_RATIO });
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



init();
