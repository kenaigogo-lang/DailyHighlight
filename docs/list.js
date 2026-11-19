"use strict";
// 攀登、張博雅共用：一張卡片＝一場比賽／一站賽事，卡片內每個按鈕播放一段影片。
// 設定寫在 <body data-src="data/xxx.json" data-a="#色" data-h="#色">。

const SRC = document.body.dataset.src;
const COLOR_A = document.body.dataset.a || "#333";
const COLOR_H = document.body.dataset.h || "#555";

function fmtDay(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  return `${y}/${m}/${d}`;
}

function showEmpty(msg) {
  const el = $("#empty");
  el.textContent = msg;
  el.hidden = !msg;
}

async function init() {
  let data;
  try {
    data = await getJSON(SRC);
  } catch {
    showEmpty("還沒有資料，等第一次自動更新後就會出現。");
    return;
  }
  $("#summary").innerHTML = [`共 <b>${data.events.length}</b> 場`, data.updated ? `更新於 ${fmtUpdated(data.updated)}` : ""]
    .filter(Boolean).join(" · ") + " ·";
  const list = $("#games");
  if (!data.events.length) showEmpty("目前沒有影片。");
  for (const ev of data.events) list.append(renderEvent(ev));
}

function renderEvent(ev) {
  const li = $("#tpl-event").content.firstElementChild.cloneNode(true);
  li.style.setProperty("--a", COLOR_A);
  li.style.setProperty("--h", COLOR_H);
  const md = ev.date.slice(5).split("-").map(Number).join("/");
  $(".stub", li).textContent = md;
  $(".ev-name", li).textContent = ev.name;
  $(".ev-sub", li).textContent = ev.sub || "";
  $(".time", li).textContent = ev.end && ev.end !== ev.date ? `${fmtDay(ev.date)}–${fmtDay(ev.end).slice(5)}` : fmtDay(ev.date);
  const box = $(".items", li);
  for (const it of ev.items) {
    const wrap = document.createElement("span");
    wrap.className = "item";
    const b = document.createElement("button");
    b.type = "button";
    b.className = it.kind === "interview" ? "btn ghost" : "btn primary";
    b.textContent = it.kind === "interview" ? "🎤 " + it.label : "▶ " + it.label;
    const versions = [it.video, ...(it.alts || [])];
    let vi = 0;
    b.onclick = () => {
      if (it.warn && !b.dataset.ok && !confirm("訪問通常會直接講到成績，確定要看嗎？")) return;
      b.dataset.ok = "1";
      openPlayer(li, versions[vi], { startRatio: 0, button: b });
    };
    wrap.append(b);
    if (versions.length > 1) {  // 同一輪有好幾支影片：可以換一支（例如配錯或畫質不好）
      const sw = document.createElement("button");
      sw.type = "button";
      sw.className = "btn small swap";
      sw.title = "換另一支影片";
      sw.textContent = `↻ ${vi + 1}/${versions.length}`;
      sw.onclick = () => {
        vi = (vi + 1) % versions.length;
        sw.textContent = `↻ ${vi + 1}/${versions.length}`;
        openPlayer(li, versions[vi], { startRatio: 0, button: b });
      };
      wrap.append(sw);
    }
    box.append(wrap);
  }
  return li;
}

init();
