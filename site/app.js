const layers = [...document.querySelectorAll("[data-layer]")];
const metaEl = document.querySelector(".meta");
const artistEl = document.querySelector("[data-artist]");
const statusEl = document.querySelector("[data-status]");
const fullscreenButton = document.querySelector("[data-fullscreen-button]");
const infoButton = document.querySelector("[data-info-button]");
const infoOverlay = document.querySelector("[data-info-overlay]");
const infoClose = document.querySelector("[data-info-close]");
const portfolioLink = document.querySelector("[data-portfolio-link]");
const CONTROLS_HIDE_DELAY_MS = 3200;

let minuteMap = new Map();
let activeLayer = 0;
let timerId = null;
let controlsTimerId = null;
let controlsPinned = false;
let infoPanelOpen = false;

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

function visibleControls() {
  return [fullscreenButton, infoButton, portfolioLink].filter((control) => control && !control.hidden);
}

function setPortfolioLink(record) {
  if (record?.portfolioUrl) {
    const label = record.creditType === "artist_made" ? "View artist portfolio" : "View artist info";
    portfolioLink.href = record.portfolioUrl;
    portfolioLink.textContent = label;
    portfolioLink.hidden = false;
    portfolioLink.setAttribute("aria-label", `${label}: ${record.artistName ?? record.artist}`);
    return;
  }

  portfolioLink.hidden = true;
  portfolioLink.classList.remove("is-visible");
  portfolioLink.removeAttribute("href");
  portfolioLink.removeAttribute("aria-label");
}

function creditLabel(record) {
  if (!record?.artistName) {
    return "";
  }
  if (record.creditType === "ai_inspired") {
    return `AI-generated · Inspired by ${record.artistName}`;
  }
  if (record.creditType === "artist_made") {
    return `By ${record.artistName}`;
  }
  return "";
}

function showStatus(message) {
  statusEl.textContent = message;
  statusEl.hidden = !message;
}

function updateFullscreenButton() {
  if (!fullscreenButton) {
    return;
  }

  const isFullscreen = Boolean(document.fullscreenElement);
  fullscreenButton.classList.toggle("is-fullscreen", isFullscreen);
  fullscreenButton.setAttribute(
    "aria-label",
    isFullscreen ? "Wyłącz pełny ekran" : "Włącz pełny ekran",
  );
}

function hideControls() {
  if (controlsPinned) {
    return;
  }
  visibleControls().forEach((control) => control.classList.remove("is-visible"));
}

function showControls() {
  const controls = visibleControls();
  if (!controls.length) {
    return;
  }

  controls.forEach((control) => control.classList.add("is-visible"));
  window.clearTimeout(controlsTimerId);
  controlsTimerId = window.setTimeout(hideControls, CONTROLS_HIDE_DELAY_MS);
}

function pinControls() {
  controlsPinned = true;
  showControls();
}

function releaseControls() {
  if (infoPanelOpen) {
    return;
  }
  controlsPinned = false;
  showControls();
}

function bindPinnedControl(control) {
  if (!control) {
    return;
  }

  control.addEventListener("pointerenter", pinControls);
  control.addEventListener("pointerleave", releaseControls);
  control.addEventListener("focus", pinControls);
  control.addEventListener("blur", releaseControls);
}

function openInfoPanel() {
  if (!infoOverlay || !infoButton) {
    return;
  }
  infoPanelOpen = true;
  controlsPinned = true;
  infoOverlay.hidden = false;
  infoButton.setAttribute("aria-expanded", "true");
  showControls();
  infoClose?.focus();
}

function closeInfoPanel() {
  if (!infoOverlay || !infoButton) {
    return;
  }
  infoPanelOpen = false;
  controlsPinned = false;
  infoOverlay.hidden = true;
  infoButton.setAttribute("aria-expanded", "false");
  infoButton.focus();
  showControls();
}

function setupInfoPanel() {
  if (!infoButton || !infoOverlay) {
    return;
  }

  infoButton.addEventListener("click", () => {
    if (infoPanelOpen) {
      closeInfoPanel();
    } else {
      openInfoPanel();
    }
  });
  infoClose?.addEventListener("click", closeInfoPanel);
  infoOverlay.addEventListener("click", (event) => {
    if (event.target === infoOverlay) {
      closeInfoPanel();
    }
  });
  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && infoPanelOpen) {
      closeInfoPanel();
    }
  });
}

async function toggleFullscreen() {
  if (!document.fullscreenEnabled) {
    return;
  }

  try {
    if (document.fullscreenElement) {
      await document.exitFullscreen();
    } else {
      await document.documentElement.requestFullscreen();
    }
  } catch (error) {
    showStatus("Nie udało się przełączyć trybu pełnego ekranu.");
  }
}

function setupFullscreen() {
  if (fullscreenButton && document.fullscreenEnabled) {
    fullscreenButton.hidden = false;
    fullscreenButton.addEventListener("click", toggleFullscreen);
    document.addEventListener("fullscreenchange", updateFullscreenButton);
    updateFullscreenButton();
  }
}

function setupControls() {
  setupFullscreen();
  setupInfoPanel();
  bindPinnedControl(fullscreenButton);
  bindPinnedControl(infoButton);
  bindPinnedControl(portfolioLink);
  window.addEventListener("pointermove", showControls, { passive: true });
  window.addEventListener("touchstart", showControls, { passive: true });
  window.addEventListener("keydown", showControls);
  showControls();
}

function renderMinute(hhmm) {
  const record = minuteMap.get(hhmm);

  if (!record?.image) {
    metaEl.hidden = true;
    setPortfolioLink(null);
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

  const credit = creditLabel(record);
  if (credit) {
    artistEl.textContent = credit;
    metaEl.hidden = false;
  } else {
    artistEl.textContent = "";
    metaEl.hidden = true;
  }
  setPortfolioLink(record);
  showStatus("");
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
    setupControls();
    const response = await fetch("minutes.json", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const data = await response.json();
    minuteMap = new Map(data.minutes.map((record) => [record.hhmm, record]));
    renderMinute(currentHHMM());
    scheduleTick();
  } catch (error) {
    metaEl.hidden = true;
    artistEl.textContent = "Nie udało się wczytać minutes.json.";
    showStatus(error.message);
  }
}

init();
