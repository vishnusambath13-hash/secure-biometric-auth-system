// =============================================================================
// hud_animation.js — HUD Visual Animations
// Secure UAV Command Authorization System
// =============================================================================
// Manages:
//   • Live clock display
//   • Telemetry simulation (battery, signal, altitude)
//   • Rotating HUD ring tick labels
//   • Radar blip randomisation
// =============================================================================

(function () {
  "use strict";

  // -------------------------------------------------------------------------
  // Live Clock
  // -------------------------------------------------------------------------
  function updateClock() {
    const el = document.getElementById("hud-clock");
    if (!el) return;
    const now = new Date();
    const pad = (n) => String(n).padStart(2, "0");
    el.textContent =
      `${now.getUTCFullYear()}-${pad(now.getUTCMonth() + 1)}-${pad(now.getUTCDate())} ` +
      `${pad(now.getUTCHours())}:${pad(now.getUTCMinutes())}:${pad(now.getUTCSeconds())} UTC`;
  }
  setInterval(updateClock, 1000);
  updateClock();

  // -------------------------------------------------------------------------
  // Telemetry Simulation
  // -------------------------------------------------------------------------
  const telemetry = {
    battery:  { value: 87, min: 5,  max: 100, drift: 0.05, bar: "bar-battery",  val: "val-battery",  unit: "%",   low: 20  },
    signal:   { value: 94, min: 60, max: 100, drift: 1.0,  bar: "bar-signal",   val: "val-signal",   unit: "%",   low: 70  },
    altitude: { value: 142, min: 0, max: 500, drift: 3.0,  bar: "bar-altitude", val: "val-altitude", unit: "m",   low: -1  },
  };

  function updateTelemetry() {
    for (const [key, t] of Object.entries(telemetry)) {
      // Random walk
      t.value += (Math.random() - 0.5) * t.drift * 2;
      t.value  = Math.max(t.min, Math.min(t.max, t.value));

      const barEl = document.getElementById(t.bar);
      const valEl = document.getElementById(t.val);
      if (!barEl || !valEl) continue;

      const pct = ((t.value - t.min) / (t.max - t.min)) * 100;
      barEl.style.width = pct + "%";

      const isLow = t.low > 0 && t.value < t.low;
      barEl.classList.toggle("low", isLow);

      valEl.textContent = Math.round(t.value) + t.unit;
    }
  }

  // Battery drains slowly
  setInterval(() => { telemetry.battery.value -= 0.01; }, 3000);
  setInterval(updateTelemetry, 800);
  updateTelemetry();

  // -------------------------------------------------------------------------
  // Radar blip randomisation — occasionally spawn new blips
  // -------------------------------------------------------------------------
  function spawnBlip() {
    const container = document.querySelector(".radar-container");
    if (!container) return;

    // Max 4 blips at a time
    const existing = container.querySelectorAll(".radar-blip-dynamic");
    if (existing.length >= 4) {
      existing[0].remove();
    }

    const blip = document.createElement("div");
    blip.className = "radar-blip radar-blip-dynamic";

    // Random position within the radar circle
    const angle  = Math.random() * 2 * Math.PI;
    const radius = Math.random() * 42;   // percent within circle
    const cx = 50 + radius * Math.cos(angle);
    const cy = 50 + radius * Math.sin(angle);

    blip.style.left             = cx + "%";
    blip.style.top              = cy + "%";
    blip.style.animationDelay   = "0s";
    blip.style.animationDuration = (2 + Math.random() * 2) + "s";

    container.appendChild(blip);
  }
  setInterval(spawnBlip, 2800);

  // -------------------------------------------------------------------------
  // HUD ring rotation tick labels (purely decorative)
  // -------------------------------------------------------------------------
  function initRingLabels() {
    const ringEl = document.getElementById("hud-ring-labels");
    if (!ringEl) return;

    const angles = [0, 45, 90, 135, 180, 225, 270, 315];
    angles.forEach((deg) => {
      const span = document.createElement("span");
      span.className = "ring-tick";
      span.textContent = String(deg).padStart(3, "0");
      span.style.setProperty("--angle", deg + "deg");
      ringEl.appendChild(span);
    });
  }
  initRingLabels();

  // -------------------------------------------------------------------------
  // Panel glow pulse on hover (adds a temporary glow class)
  // -------------------------------------------------------------------------
  document.querySelectorAll(".hud-panel").forEach((panel) => {
    panel.addEventListener("mouseenter", () => panel.classList.add("panel-active"));
    panel.addEventListener("mouseleave", () => panel.classList.remove("panel-active"));
  });

})();