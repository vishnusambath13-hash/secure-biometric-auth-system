// =============================================================================
// command_console.js — Command Button Handling & API Communication
// Secure UAV Command Authorization System
// =============================================================================
// Responsibilities:
//   • Bind click handlers to all command buttons
//   • POST command requests to /execute_command
//   • Display feedback in the #cmd-feedback box
//   • Append entries to the command log panel
// =============================================================================

(function () {
  "use strict";

  // -------------------------------------------------------------------------
  // Constants
  // -------------------------------------------------------------------------
  const EXECUTE_URL = "/execute_command";
  const MAX_LOG_ENTRIES = 50;

  // -------------------------------------------------------------------------
  // DOM refs (populated after DOMContentLoaded)
  // -------------------------------------------------------------------------
  let feedbackEl  = null;
  let logEl       = null;
  let missionEl   = null;

  // -------------------------------------------------------------------------
  // Utility: pad timestamp
  // -------------------------------------------------------------------------
  function nowTs() {
    const d = new Date();
    const p = (n) => String(n).padStart(2, "0");
    return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
  }

  async function executeCommand(command){

    let response = await fetch("/execute_command",{
        method:"POST",
        headers:{ "Content-Type":"application/json"},
        body: JSON.stringify({command})
    });

    let data = await response.json();

    // voice challenge
    if(data.status === "voice_required"){

        const phrase = data.phrase;

        document.getElementById("cmd-feedback").innerText =
            "VOICE AUTHORIZATION REQUIRED\nSay: \"" + phrase.toUpperCase() + "\"";

        startVoiceRecognition(command, phrase);

        return;
    }

    updateConsole(data);
}


  // -------------------------------------------------------------------------
  // Set feedback display
  // -------------------------------------------------------------------------
  function setFeedback(message, type = "neutral") {
    if (!feedbackEl) return;
    feedbackEl.textContent = message;
    feedbackEl.className   = "";                    // clear existing classes
    if (type === "success") feedbackEl.classList.add("success");
    if (type === "error")   feedbackEl.classList.add("error");
  }

  // -------------------------------------------------------------------------
  // Set feedback to loading state
  // -------------------------------------------------------------------------
  function setFeedbackLoading(cmdName) {
    if (!feedbackEl) return;
    feedbackEl.innerHTML =
      `<span class="spinner"></span> AUTHORIZING: ${cmdName.toUpperCase()} ...`;
    feedbackEl.className = "";
  }

  // -------------------------------------------------------------------------
  // Append a row to the command log
  // -------------------------------------------------------------------------
  function appendLog(ts, operator, cmdName, result) {
    if (!logEl) return;

    // Trim old entries
    const existing = logEl.querySelectorAll(".log-entry");
    if (existing.length >= MAX_LOG_ENTRIES) {
      existing[0].remove();
    }

    const entry = document.createElement("div");
    entry.className = "log-entry";

    const isAbort = cmdName === "abort_mission";

    entry.innerHTML = `
      <span class="log-ts">${ts}</span>
      <span class="log-op">${escHtml(operator)}</span>
      <span class="log-cmd">${escHtml(cmdName.toUpperCase())}</span>
      <span class="log-result ${isAbort ? "abort" : "ok"}">${escHtml(result)}</span>
    `;

    logEl.appendChild(entry);
    logEl.scrollTop = logEl.scrollHeight;
  }

  // -------------------------------------------------------------------------
  // Update mission status badge
  // -------------------------------------------------------------------------
  function updateMissionStatus(cmdName) {
    if (!missionEl) return;

    const statusMap = {
      start_recon:   { text: "RECON ACTIVE",   alert: false },
      deploy_drone:  { text: "DRONE DEPLOYED", alert: false },
      return_base:   { text: "RTB IN PROGRESS", alert: false },
      abort_mission: { text: "⚠ MISSION ABORT", alert: true  },
      system_status: { text: "STANDBY",         alert: false },
    };

    const info = statusMap[cmdName] || { text: "STANDBY", alert: false };
    missionEl.textContent = info.text;
    missionEl.classList.toggle("alert", info.alert);
  }

  // -------------------------------------------------------------------------
  // Execute a command via the Flask API
  // -------------------------------------------------------------------------
  async function executeCommand(cmdName, btnEl) {
    // Disable all buttons during request
    const allBtns = document.querySelectorAll(".cmd-btn");
    allBtns.forEach((b) => (b.disabled = true));

    setFeedbackLoading(cmdName);

    try {
      const response = await fetch(EXECUTE_URL, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ command: cmdName }),
      });

      const data = await response.json();

      if (response.ok && data.status === "success") {
        const msg = `[${data.command.toUpperCase()}] ${data.result}`;
        setFeedback(msg, "success");
        appendLog(nowTs(), data.operator || "OPERATOR", data.command, data.result);
        updateMissionStatus(data.command);
        // Brief flash on button
        if (btnEl) {
          btnEl.classList.add("btn-flash");
          setTimeout(() => btnEl.classList.remove("btn-flash"), 600);
        }
      } else {
        const errMsg = data.result || "Command authorization failed.";
        setFeedback(`[ERROR] ${errMsg}`, "error");
        appendLog(nowTs(), "SYSTEM", cmdName, "AUTHORIZATION FAILED");
      }
    } catch (err) {
      setFeedback("[NETWORK ERROR] Could not reach command server.", "error");
      console.error("Command execution error:", err);
    } finally {
      // Re-enable buttons
      allBtns.forEach((b) => (b.disabled = false));
    }
  }

  // -------------------------------------------------------------------------
  // Escape HTML to prevent XSS in log entries
  // -------------------------------------------------------------------------
  function escHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  // -------------------------------------------------------------------------
  // Bind all command buttons
  // -------------------------------------------------------------------------
  function bindButtons() {
    // Standard command buttons (keyboard / HUD)
    document.querySelectorAll(".cmd-btn[data-command]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const cmdName = btn.getAttribute("data-command");
        if (cmdName) executeCommand(cmdName, btn);
      });
    });

    // Gesture trigger — separate endpoint, separate handler
    const gestureTrigger = document.getElementById("gesture-trigger");
    if (gestureTrigger) {
      gestureTrigger.addEventListener("click", () => {
        if (!gestureTrigger.disabled) triggerGestureCommand(gestureTrigger);
      });
    }
  }

  // -------------------------------------------------------------------------
  // Gesture status banner helpers
  // -------------------------------------------------------------------------

  /**
   * Show the gesture status banner with a message and visual state.
   * @param {string} message   - Text to display
   * @param {'ok'|'cancelled'|'error'} type
   */
  function showGestureBanner(message, type = "ok") {
    const banner   = document.getElementById("gesture-status-banner");
    const textEl   = document.getElementById("gesture-status-text");
    const iconEl   = banner && banner.querySelector(".gesture-status-icon");
    if (!banner || !textEl) return;

    const icons = { ok: "✋", cancelled: "⊘", error: "⚠" };

    banner.hidden = false;
    banner.className = "gesture-status-banner" + (type !== "ok" ? ` ${type}` : "");
    if (iconEl) iconEl.textContent = icons[type] || "✋";
    textEl.textContent = message;

    // Auto-hide after 8 s for non-error states
    if (type !== "error") {
      clearTimeout(banner._hideTimer);
      banner._hideTimer = setTimeout(() => {
        banner.hidden = true;
      }, 8000);
    }
  }

  function hideGestureBanner() {
    const banner = document.getElementById("gesture-status-banner");
    if (banner) banner.hidden = true;
  }

  // -------------------------------------------------------------------------
  // Gesture button state helpers
  // -------------------------------------------------------------------------

  function setGestureButtonScanning(btnEl) {
    btnEl.classList.add("gesture-scanning");
    btnEl.classList.remove("gesture-done");
    btnEl.setAttribute("aria-pressed", "true");
    btnEl.disabled = true;
    const sub = document.getElementById("gesture-btn-sub");
    if (sub) sub.textContent = "Scanning · Hold gesture steady …";
  }

  function setGestureButtonDone(btnEl) {
    btnEl.classList.remove("gesture-scanning");
    btnEl.classList.add("gesture-done");
    btnEl.setAttribute("aria-pressed", "false");
    btnEl.disabled = false;
    const sub = document.getElementById("gesture-btn-sub");
    if (sub) sub.textContent = "Camera · MediaPipe · RSA-Signed";
    // Return dot to idle after 3 s
    setTimeout(() => btnEl.classList.remove("gesture-done"), 3000);
  }

  function setGestureButtonIdle(btnEl) {
    btnEl.classList.remove("gesture-scanning", "gesture-done");
    btnEl.setAttribute("aria-pressed", "false");
    btnEl.disabled = false;
    const sub = document.getElementById("gesture-btn-sub");
    if (sub) sub.textContent = "Camera · MediaPipe · RSA-Signed";
  }

  // -------------------------------------------------------------------------
  // Gesture command — calls POST /gesture-command
  // -------------------------------------------------------------------------
  async function triggerGestureCommand(btnEl) {
    // Disable all other command buttons while webcam is active
    document.querySelectorAll(".cmd-btn[data-command]").forEach((b) => (b.disabled = true));

    setGestureButtonScanning(btnEl);
    hideGestureBanner();

    setFeedback(
      "✋ GESTURE MODE ACTIVE — Show hand to camera. Hold gesture steady to confirm. Press Q to cancel.",
      "neutral"
    );

    try {
      const response = await fetch("/gesture-command", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
      });

      const data = await response.json();

      // ── Success ────────────────────────────────────────────────────────────
      if (data.status === "executed") {
        const cmdUpper   = (data.command || "").toUpperCase().replace(/_/g, " ");
        const gestureRaw = data.gesture || data.command || "";

        // Status banner: "Gesture command detected: START_RECON"
        showGestureBanner(`Gesture command detected: ${gestureRaw}`, "ok");

        // Feedback box
        setFeedback(
          `[GESTURE → ${cmdUpper}] ${data.result}`,
          "success"
        );

        // Audit log entry
        appendLog(
          nowTs(),
          data.operator || "OPERATOR",
          data.command,
          `${data.result}  [input: gesture ${gestureRaw}]`
        );

        // Telemetry mission badge
        updateMissionStatus(data.command);
        setGestureButtonDone(btnEl);

      // ── Cancelled ──────────────────────────────────────────────────────────
      } else if (data.status === "cancelled") {
        showGestureBanner("Gesture detection cancelled — no command issued.", "cancelled");
        setFeedback("[GESTURE] Cancelled — no command was authorized.", "neutral");
        appendLog(nowTs(), "SYSTEM", "GESTURE_INPUT", "Gesture detection cancelled by operator.");
        setGestureButtonIdle(btnEl);

      // ── Error ──────────────────────────────────────────────────────────────
      } else {
        const errMsg = data.result || "Gesture command failed.";
        showGestureBanner(`Error: ${errMsg}`, "error");
        setFeedback(`[GESTURE ERROR] ${errMsg}`, "error");
        appendLog(nowTs(), "SYSTEM", "GESTURE_ERROR", errMsg);
        setGestureButtonIdle(btnEl);
      }

    } catch (err) {
      showGestureBanner("Network error — could not reach gesture endpoint.", "error");
      setFeedback("[NETWORK ERROR] Could not reach /gesture-command.", "error");
      console.error("Gesture command fetch error:", err);
      setGestureButtonIdle(btnEl);
    } finally {
      // Always re-enable the standard command buttons
      document.querySelectorAll(".cmd-btn[data-command]").forEach((b) => (b.disabled = false));
    }
  }

  // -------------------------------------------------------------------------
  // Initialise on DOM ready
  // -------------------------------------------------------------------------
  document.addEventListener("DOMContentLoaded", () => {
    feedbackEl = document.getElementById("cmd-feedback");
    logEl      = document.getElementById("command-log");
    missionEl  = document.getElementById("mission-status");

    bindButtons();

    // Welcome entry in log
    appendLog(nowTs(), "SYSTEM", "SYSTEM_INIT", "Console online — awaiting operator commands.");
  });

})();