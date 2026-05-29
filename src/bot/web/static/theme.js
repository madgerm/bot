(function () {
  var STORAGE_KEY = "bot-theme";
  var MODES = ["light", "dark", "system"];

  function systemDark() {
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  }

  function resolve(mode) {
    if (mode === "system" || MODES.indexOf(mode) < 0) {
      return systemDark() ? "dark" : "light";
    }
    return mode;
  }

  function applyResolved(resolved) {
    var root = document.documentElement;
    root.classList.toggle("dark", resolved === "dark");
    root.dataset.themeResolved = resolved;
  }

  function getStored() {
    try {
      return localStorage.getItem(STORAGE_KEY) || "system";
    } catch (_e) {
      return "system";
    }
  }

  function setStored(mode) {
    try {
      localStorage.setItem(STORAGE_KEY, mode);
    } catch (_e) {
      /* ignore */
    }
    document.documentElement.dataset.theme = mode;
    applyResolved(resolve(mode));
    updateToggleUi(mode);
  }

  function cycleMode(current) {
    var idx = MODES.indexOf(current);
    if (idx < 0) idx = 2;
    return MODES[(idx + 1) % MODES.length];
  }

  function updateToggleUi(mode) {
    var btn = document.getElementById("theme-toggle");
    if (!btn) return;
    var labels = { light: "Hell", dark: "Dunkel", system: "System" };
    var icons = { light: "☀", dark: "☾", system: "◐" };
    btn.title = "Theme: " + (labels[mode] || mode) + " (klicken zum Wechseln)";
    btn.setAttribute("aria-label", btn.title);
    var icon = btn.querySelector("[data-theme-icon]");
    if (icon) icon.textContent = icons[mode] || "◐";
    var label = btn.querySelector("[data-theme-label]");
    if (label) label.textContent = labels[mode] || mode;
  }

  function initToggle() {
    var btn = document.getElementById("theme-toggle");
    if (!btn || btn.dataset.themeBound) return;
    btn.dataset.themeBound = "1";
    btn.addEventListener("click", function () {
      setStored(cycleMode(getStored()));
    });
    updateToggleUi(getStored());
  }

  window.botTheme = {
    get: getStored,
    set: setStored,
    resolve: resolve,
    apply: applyResolved,
  };

  document.documentElement.dataset.theme = getStored();
  applyResolved(resolve(getStored()));

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initToggle);
  } else {
    initToggle();
  }

  window
    .matchMedia("(prefers-color-scheme: dark)")
    .addEventListener("change", function () {
      if (getStored() === "system") {
        applyResolved(resolve("system"));
      }
    });
})();
