"use strict";
// 桌球分頁：一站賽事 → 男單／女單 → 依輪次解鎖（防暴雷）→ 每輪依精彩度排序

const ROUNDS = ["R32", "R16", "QF", "SF", "F"];
const ROUND_ZH = { R32: "32 強", R16: "16 強", QF: "8 強", SF: "4 強", F: "決賽" };
const EV_ZH = { MS: "男單", WS: "女單" };
const STATUS_ZH = { live: "進行中", done: "已結束", upcoming: "即將開始" };
const CITY_ZH = {
  Frankfurt: "法蘭克福", Montpellier: "蒙佩利爾", Muscat: "馬斯喀特", Tashkent: "塔什干", "Hong Kong": "香港",
  Doha: "杜哈", Chennai: "清奈", Singapore: "新加坡", Chongqing: "重慶", Ljubljana: "盧布爾雅那",
  "São José dos Campos": "聖若澤", Yokohama: "橫濱", Astana: "阿斯塔納", Macao: "澳門", Macau: "澳門",
  Malmö: "馬爾默", Malmo: "馬爾默", Beijing: "北京", "Las Vegas": "拉斯維加斯", Nagoya: "名古屋",
  London: "倫敦", Busan: "釜山", Incheon: "仁川", Paris: "巴黎", "Los Angeles": "洛杉磯",
};
// IOC 國碼 → 國旗（flagcdn 用 ISO 兩碼）與代表色（D 主題用）
const ORG = {
  JPN: ["jp", "#bc002d"], TPE: ["tw", "#1f3a93"], CHN: ["cn", "#de2910"], KOR: ["kr", "#003478"],
  HKG: ["hk", "#de2910"], SGP: ["sg", "#ef3340"], IND: ["in", "#ff9933"], GER: ["de", "#222222"],
  FRA: ["fr", "#002395"], SWE: ["se", "#006aa7"], BRA: ["br", "#009c3b"], POR: ["pt", "#046a38"],
  SLO: ["si", "#005da4"], CRO: ["hr", "#171796"], DEN: ["dk", "#c8102e"], AUT: ["at", "#c8102e"],
  ROU: ["ro", "#002b7f"], POL: ["pl", "#dc143c"], ESP: ["es", "#aa151b"], ITA: ["it", "#008c45"],
  ENG: ["gb-eng", "#cf142b"], GBR: ["gb", "#012169"], USA: ["us", "#3c3b6e"], CAN: ["ca", "#d80621"],
  EGY: ["eg", "#ce1126"], NGR: ["ng", "#008751"], THA: ["th", "#2d2a4a"], MAS: ["my", "#010066"],
  IRI: ["ir", "#239f40"], KAZ: ["kz", "#00afca"], UZB: ["uz", "#0099b5"], TUR: ["tr", "#e30a17"],
  SVK: ["sk", "#0b4ea2"], CZE: ["cz", "#11457e"], HUN: ["hu", "#477050"], BEL: ["be", "#222222"],
  NED: ["nl", "#ae1c28"], LUX: ["lu", "#00a1de"], AUS: ["au", "#012169"], NZL: ["nz", "#012169"],
  CHI: ["cl", "#0039a6"], ARG: ["ar", "#74acdf"], PUR: ["pr", "#0050f0"], MEX: ["mx", "#006847"],
  RUS: ["", "#444b59"], AIN: ["", "#444b59"], UKR: ["ua", "#0057b7"], SRB: ["rs", "#c6363c"],
  GRE: ["gr", "#0d5eaf"], MON: ["mc", "#ce1126"], QAT: ["qa", "#8a1538"], KSA: ["sa", "#006c35"],
  VIE: ["vn", "#da251d"], PRK: ["kp", "#024fa2"], NOR: ["no", "#ba0c2f"], FIN: ["fi", "#002f6c"],
};
const flag = (org) => (ORG[org] && ORG[org][0] ? `https://flagcdn.com/w80/${ORG[org][0]}.png` : "");
const orgColor = (org) => (ORG[org] ? ORG[org][1] : "#3a3f4b");

let index = { events: [], next: [] };
let current = null;   // 目前賽事 id
let curEv = "MS";
let event = null;

function cityOf(e) {
  if (CITY_ZH[e.city]) return CITY_ZH[e.city];
  const hit = Object.keys(CITY_ZH).find((c) => e.name.includes(c));  // 行事曆沒填城市時從名稱找
  return hit ? CITY_ZH[hit] : (e.city || "");
}

function placeName(e) {
  return `${e.type} ${cityOf(e)}`.trim();
}

function fmtRange(e) {
  const f = (s) => `${+s.slice(5, 7)}/${+s.slice(8, 10)}`;
  return `${f(e.start)}–${f(e.end)}`;
}

function fmtStart(iso) {
  if (!iso) return "";
  return new Intl.DateTimeFormat("zh-TW", {
    timeZone: "Asia/Taipei", month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false,
  }).format(new Date(iso)) + "（台灣）";
}

function showEmpty(msg) {
  const el = $("#empty");
  el.textContent = msg;
  el.hidden = !msg;
}

// ---- 解鎖狀態（每位觀眾自己的瀏覽器記住，清掉就重新鎖上）
function unlockKey() { return `tt-unlock:${current}:${curEv}`; }
function unlocked() {
  try { return Math.max(0, Math.min(ROUNDS.length - 1, parseInt(localStorage.getItem(unlockKey()) || "0", 10))); } catch { return 0; }
}
function setUnlocked(n) {
  try { localStorage.setItem(unlockKey(), String(n)); } catch {}
}

// ---------------------------------------------------------------- 初始化
async function init() {
  try {
    index = await getJSON("data/tt/index.json");
  } catch {
    showEmpty("還沒有資料，等第一次自動更新後就會出現。");
    return;
  }
  if (!index.events.length) {
    showEmpty("目前沒有收錄的賽事。");
    renderSummary(null);
    return;
  }
  window.addEventListener("hashchange", route);
  route();
}

function route() {
  const [id, ev] = location.hash.slice(1).split("/");
  const ids = index.events.map((e) => String(e.id));
  // 預設：最近一站「有比賽」的賽事
  const first = index.events.find((e) => e.n > 0) || index.events[0];
  load(ids.includes(id) ? id : String(first.id), ev === "WS" ? "WS" : "MS");
}

function renderEvents() {
  const nav = $("#events");
  nav.innerHTML = "";
  for (const e of index.events.slice(0, 8)) {
    const b = document.createElement("button");
    b.className = "date-chip";
    b.type = "button";
    const city = cityOf(e);
    b.innerHTML = `${esc(city || e.type)}<small>${esc(e.type)}${e.status === "live" ? " · 進行中" : ""}</small>`;
    b.title = e.name;
    b.setAttribute("aria-current", String(e.id) === current ? "true" : "false");
    b.onclick = () => { location.hash = `${e.id}/${curEv}`; };
    nav.append(b);
  }
}

function renderEvTabs() {
  const nav = $("#evtabs");
  nav.innerHTML = "";
  for (const ev of ["MS", "WS"]) {
    const b = document.createElement("button");
    b.className = "date-chip";
    b.type = "button";
    b.textContent = EV_ZH[ev];
    b.setAttribute("aria-current", ev === curEv ? "true" : "false");
    b.onclick = () => { location.hash = `${current}/${ev}`; };
    nav.append(b);
  }
}

function renderSummary(e) {
  const parts = [];
  if (e) {
    parts.push(`<b>${esc(placeName(e))}</b>`, fmtRange(e), STATUS_ZH[e.status] || "");
    if (e.updated) parts.push(`更新於 ${fmtUpdated(e.updated)}`);
  }
  const nx = (index.next || [])[0];
  if (nx) parts.push(`下一站：${esc(placeName(nx))} ${fmtRange(nx)}`);
  $("#summary").innerHTML = parts.filter(Boolean).join(" · ") + " ·";
}

async function load(id, ev) {
  const changedEvent = id !== current;
  current = id;
  curEv = ev;
  renderEvents();
  renderEvTabs();
  closeAllPlayers();
  showEmpty("");
  if (changedEvent || !event) {
    $("#rounds").innerHTML = "";
    try {
      event = await getJSON(`data/tt/${id}.json`);
    } catch {
      showEmpty("資料讀取失敗，請稍後再試。");
      return;
    }
    if (id !== current) return;
  }
  renderSummary(event);
  renderRounds();
}

// ---------------------------------------------------------------- 輪次
function renderRounds() {
  const box = $("#rounds");
  box.innerHTML = "";
  const ms = event.matches.filter((m) => m.ev === curEv);
  if (!event.matches.length) {
    showEmpty(event.status === "live"
      ? "比賽進行中，32 強還沒開打或還沒有收錄的比賽，晚點再來看。"
      : "這一站沒有可用的成績資料（官方未提供），所以暫時無法顯示。");
    return;
  }
  const open = unlocked();
  ROUNDS.forEach((r, i) => {
    const sec = document.createElement("section");
    sec.className = "round";
    const h = document.createElement("h2");
    h.className = "round-title";
    h.textContent = ROUND_ZH[r];
    sec.append(h);
    if (i > open) {
      sec.classList.add("locked");
      if (i === open + 1) {
        const b = document.createElement("button");
        b.className = "btn unlock";
        b.type = "button";
        b.textContent = `🔓 解鎖${ROUND_ZH[r]}（會知道誰晉級）`;
        b.onclick = () => {
          setUnlocked(i);
          renderRounds();
          box.children[i].scrollIntoView({ behavior: "smooth", block: "start" });
        };
        sec.append(b);
      } else {
        const p = document.createElement("p");
        p.className = "lock-note";
        p.textContent = "🔒 先解鎖前一輪";
        sec.append(p);
      }
      box.append(sec);
      return;
    }
    const list = ms.filter((m) => m.round === r);
    if (!list.length) {
      const p = document.createElement("p");
      p.className = "lock-note";
      p.textContent = event.status === "live" ? "這一輪還沒有收錄的比賽（可能尚未開打）。"
        : (r === "R32" || r === "R16") ? "這一輪沒有日本、台灣選手或陳熠的比賽。" : "沒有資料。";
      sec.append(p);
    } else {
      const ol = document.createElement("ol");
      ol.className = "games";
      list.forEach((m, k) => ol.append(renderMatch(m, k + 1)));
      sec.append(ol);
    }
    box.append(sec);
  });
}

function renderMatch(m, rank) {
  const li = $("#tpl-match").content.firstElementChild.cloneNode(true);
  $(".rank", li).textContent = rank;
  $(".stub", li).textContent = `No.${rank}`;
  li.dataset.rank = rank;
  const ca = orgColor(m.p[0].org), cb = orgColor(m.p[1].org);
  li.style.setProperty("--a", ca);
  li.style.setProperty("--h", colorDist(ca, cb) < 90 ? "#26282e" : cb);
  ["away", "home"].forEach((side, i) => {
    const p = m.p[i];
    const el = $(`.team.${side}`, li);
    const img = $("img", el);
    if (flag(p.org)) { img.src = flag(p.org); img.alt = p.org; img.className = "flagimg"; } else img.remove();
    $(".name", el).innerHTML = `${esc(p.zh || p.name)}<small>${p.zh ? esc(p.name) + " · " : ""}${esc(p.org)}</small>`;
  });
  $(".time", li).textContent = fmtStart(m.start);
  $(".tag", li).textContent = `${EV_ZH[m.ev]} ${ROUND_ZH[m.round]}`;

  const play = $(".play", li);
  const status = $(".status", li);
  if (m.video) {
    if (m.video.full) play.textContent = "▶ 看全場（無精華版）";
    play.onclick = () => openPlayer(li, m.video, { startRatio: 0 });
  } else {
    play.remove();
    status.textContent = "⏳ 影片還沒上架（會自動補抓）";
  }
  $(".box", li).onclick = () => toggleScore(li, m);
  return li;
}

function toggleScore(li, m) {
  const el = $(".boxscore", li);
  const btn = $(".box", li);
  if (!el.hidden) {
    el.hidden = true;
    btn.textContent = "⚠️ 查看比分";
    return;
  }
  if (!el.dataset.ok && !confirm("會直接顯示比分和勝負，確定要看嗎？")) return;
  el.dataset.ok = "1";
  if (!el.innerHTML) {
    const n = m.games.length;
    const won = [0, 1].map((i) => m.games.filter((g) => g[i] > g[1 - i]).length);
    const head = Array.from({ length: n }, (_, i) => `<th>第 ${i + 1} 局</th>`).join("");
    const rows = [0, 1].map((i) => `<tr><td>${esc(m.p[i].zh || m.p[i].name)}</td>${m.games.map((g) =>
      `<td${g[i] > g[1 - i] ? ' class="pts"' : ""}>${g[i]}</td>`).join("")}<td class="pts">${won[i]}</td></tr>`).join("");
    el.innerHTML = `<div class="scroll"><table><thead><tr><th>選手</th>${head}<th>局數</th></tr></thead><tbody>${rows}</tbody></table></div>`;
  }
  el.hidden = false;
  btn.textContent = "收起比分";
}

init();
