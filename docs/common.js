"use strict";
// NBA、桌球頁共用：工具函式、防暴雷播放器、換風格

const STOP_BEFORE_END = 1.5;     // 結尾前幾秒自動停，避免 YouTube 片尾推薦
const SKINS = ["C", "D", "E"];

// 兩隊顏色太像（例如老鷹、公牛都是紅）就把主隊改深灰
function colorDist(a, b) {
  const rgb = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  const [x, y] = [rgb(a), rgb(b)];
  return Math.hypot(x[0] - y[0], x[1] - y[1], x[2] - y[2]);
}

const $ = (sel, el = document) => el.querySelector(sel);

// ---------------------------------------------------------------- 資料
async function getJSON(path) {
  const r = await fetch(`${path}?t=${Date.now()}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json();
}

function fmtUpdated(iso) {
  return new Intl.DateTimeFormat("zh-TW", {
    timeZone: "Asia/Taipei", month: "numeric", day: "numeric",
    hour: "2-digit", minute: "2-digit", hour12: false,
  }).format(new Date(iso));
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
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

async function openPlayer(li, video, opts = {}) {
  const ratio = opts.startRatio ?? 0;
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
  // ratio = 從影片的幾 % 開始播（NBA 0.5、桌球 0）；video.half = 影片本身只有下半場
  const halfAt = () => (video.half ? 0 : Math.floor((duration || 0) * ratio));
  const fromZero = video.half || !ratio;
  $(".fromstart", wrap).hidden = fromZero;
  if ($(".half", wrap)) $(".half", wrap).hidden = fromZero;
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
      start: fromZero || !duration ? 0 : halfAt(),
    },
    events: {
      onReady: () => {
        if (!duration) {
          duration = player.getDuration() || 0;
          if (duration && !fromZero) player.seekTo(halfAt(), true);
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
  if ($(".half", wrap)) $(".half", wrap).onclick = () => seek(halfAt());
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
  try { sessionStorage.setItem("skin", root.dataset.skin); } catch {}
};
