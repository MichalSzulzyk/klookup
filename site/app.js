const minuteLink = document.querySelector("[data-minute-link]");
const layers = [...document.querySelectorAll("[data-layer]")];
const timeEl = document.querySelector("[data-time]");
const artistEl = document.querySelector("[data-artist]");
const statusEl = document.querySelector("[data-status]");

let minuteMap = new Map();
let activeLayer = 0;
let timerId = null;

function currentHHMM() {
  const params = new URLSearchParams(window.location.search);
  const override = params.get("minute");
  if (override && /^\d{4}$/.test(override)) {
    return override;
  }

  const now = new Date();
  return `${String(now.getHours()).padStart(2, "0")}${String(now.getMinutes()).padStart(2, "0")}`;
}

function nextHHMM(hhmm) {
  const hour = Number(hhmm.slice(0, 2));
  const minute = Number(hhmm.slice(2));
  const total = (hour * 60 + minute + 1) % 1440;
  return `${String(Math.floor(total / 60)).padStart(2, "0")}${String(total % 60).padStart(2, "0")}`;
}

function millisecondsToNextMinute() {
  const now = new Date();
  return (60 - now.getSeconds()) * 1000 - now.getMilliseconds();
}

function preload(record) {
  if (!record?.image) {
    return;
  }
  const image = new Image();
  if (record.srcset) {
    image.srcset = record.srcset;
    image.sizes = record.sizes ?? "100vw";
  }
  image.src = record.image;
}

function setLink(record) {
  if (record?.portfolioUrl) {
    minuteLink.href = record.portfolioUrl;
    minuteLink.target = "_blank";
    minuteLink.rel = "noopener noreferrer";
    return;
  }

  minuteLink.removeAttribute("href");
  minuteLink.removeAttribute("target");
  minuteLink.removeAttribute("rel");
}

function showStatus(message) {
  statusEl.textContent = message;
  statusEl.hidden = !message;
}

function renderMinute(hhmm) {
  const record = minuteMap.get(hhmm);
  timeEl.textContent = record?.label ?? `${hhmm.slice(0, 2)}:${hhmm.slice(2)}`;

  if (!record?.image) {
    artistEl.textContent = "Ta minuta nie ma jeszcze obrazu.";
    setLink(null);
    showStatus("Brak pliku dla tej minuty. Dodaj wygenerowany obraz albo blank minute.");
    return;
  }

  const nextLayer = (activeLayer + 1) % layers.length;
  const image = layers[nextLayer];
  image.alt = record.artistName ? `${record.label}, ${record.artistName}` : record.label;
  image.onerror = () => {
    if (record.fallbackImage && !image.src.endsWith(record.fallbackImage)) {
      image.removeAttribute("srcset");
      image.removeAttribute("sizes");
      image.src = record.fallbackImage;
    }
  };
  if (record.srcset) {
    image.srcset = record.srcset;
    image.sizes = record.sizes ?? "100vw";
  } else {
    image.removeAttribute("srcset");
    image.removeAttribute("sizes");
  }
  image.src = record.image;
  image.classList.add("is-active");
  layers[activeLayer].classList.remove("is-active");
  activeLayer = nextLayer;

  artistEl.textContent = record.artistName ?? "Blank minute";
  setLink(record);
  showStatus(record.portfolioUrl ? "" : "Portfolio dla tego artysty nie jest jeszcze uzupełnione.");
  preload(minuteMap.get(nextHHMM(hhmm)));
}

function scheduleTick() {
  window.clearTimeout(timerId);
  timerId = window.setTimeout(() => {
    renderMinute(currentHHMM());
    scheduleTick();
  }, millisecondsToNextMinute() + 50);
}

async function init() {
  try {
    const response = await fetch("minutes.json", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const data = await response.json();
    minuteMap = new Map(data.minutes.map((record) => [record.hhmm, record]));
    renderMinute(currentHHMM());
    scheduleTick();
  } catch (error) {
    timeEl.textContent = "--:--";
    artistEl.textContent = "Nie udało się wczytać minutes.json.";
    showStatus(error.message);
  }
}

init();
