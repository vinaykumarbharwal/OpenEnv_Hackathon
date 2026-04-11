(() => {
  const BASE_PATH = String(window.OPENENV_BASE_PATH || "").replace(/\/$/, "");

  const DEFAULT_COMPONENTS = [
    "api-gateway", "auth-service", "user-service", "payment-service", "web-app",
    "ios-app", "android-app", "database", "cache", "cdn",
  ];

  const DEFAULT_TEAMS = [
    "backend-api", "frontend-web", "mobile-ios", "mobile-android", "infrastructure", "data-platform",
  ];

  // Used as a fallback when the /tasks API call fails (e.g. server not yet ready).
  const FALLBACK_TASKS = [
    { id: "bug_triage_easy" },
    { id: "bug_triage_medium" },
    { id: "bug_triage_hard" },
  ];


  const el = {
    health: document.getElementById("health"),
    status: document.getElementById("status"),
    taskSelect: document.getElementById("task-select"),
    seedInput: document.getElementById("seed-input"),
    resetBtn: document.getElementById("reset-btn"),
    stateBtn: document.getElementById("state-btn"),
    suggestBtn: document.getElementById("suggest-btn"),
    stepBtn: document.getElementById("step-btn"),
    baseline: document.getElementById("baseline"),
    actionType: document.getElementById("action-type"),
    payloadFields: document.getElementById("payload-fields"),
    actionPreview: document.getElementById("action-preview"),
    ticketSummary: document.getElementById("ticket-summary"),
    ticketJson: document.getElementById("ticket-json"),
    rewardJson: document.getElementById("reward-json"),
    stateJson: document.getElementById("state-json"),
    log: document.getElementById("log"),
    mStepsUsed: document.getElementById("m-steps-used"),
    mStepsRemaining: document.getElementById("m-steps-remaining"),
    mQueueRemaining: document.getElementById("m-queue-remaining"),
    mUrgentCount: document.getElementById("m-urgent-count"),
    mSlaRisk: document.getElementById("m-sla-risk"),
    mPartialScore: document.getElementById("m-partial-score"),
    mCumulativeReward: document.getElementById("m-cumulative-reward"),
    mDone: document.getElementById("m-done"),
  };

  let currentObservation = null;
  let currentState = null;
  let episodeDone = false;

  function setStatus(text) {
    el.status.textContent = text;
  }

  function pretty(obj) {
    return JSON.stringify(obj ?? {}, null, 2);
  }

  function addLog(text) {
    const item = document.createElement("li");
    item.textContent = text;
    el.log.prepend(item);
  }

  function endpoint(path) {
    return path.startsWith("/") ? `${BASE_PATH}${path}` : `${BASE_PATH}/${path}`;
  }

  async function api(path, method = "GET", body = null) {
    const options = { method, headers: {} };
    if (body !== null) {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(body);
    }
    const response = await fetch(endpoint(path), options);
    const payload = await response.json().catch(() => null);
    if (!response.ok) {
      throw new Error(payload?.detail || `HTTP ${response.status}`);
    }
    return payload;
  }

  function getTicket() {
    return currentObservation?.current_ticket || null;
  }

  function teams() {
    return currentObservation?.available_teams?.length ? currentObservation.available_teams : DEFAULT_TEAMS;
  }

  function components() {
    const candidates = getTicket()?.component_candidates || [];
    const available = currentObservation?.available_components || DEFAULT_COMPONENTS;
    return [...new Set([...candidates, ...available])];
  }

  function updateMetrics() {
    const q = currentObservation?.queue_stats || {};
    el.mStepsUsed.textContent = String(currentObservation?.steps_used ?? currentState?.steps_used ?? 0);
    el.mStepsRemaining.textContent = String(currentObservation?.steps_remaining ?? currentState?.steps_remaining ?? 0);
    el.mQueueRemaining.textContent = String(q.remaining_count ?? 0);
    el.mUrgentCount.textContent = String(q.urgent_count ?? 0);
    el.mSlaRisk.textContent = String(q.sla_at_risk_count ?? 0);
    el.mPartialScore.textContent = Number(currentObservation?.partial_score ?? 0).toFixed(2);
    el.mCumulativeReward.textContent = Number(currentState?.cumulative_reward ?? 0).toFixed(2);
    el.mDone.textContent = String(Boolean(currentState?.episode_done ?? episodeDone));
  }

  function renderTicket() {
    const ticket = getTicket();
    if (!ticket) {
      el.ticketSummary.textContent = episodeDone ? "Episode complete." : "No ticket loaded.";
      el.ticketJson.textContent = pretty(currentObservation || {});
      return;
    }

    el.ticketSummary.textContent = `${ticket.ticket_id} | ${ticket.title} | service=${ticket.service} | reporter=${ticket.reporter_type}`;
    el.ticketJson.textContent = pretty(ticket);
  }

  function field(id, label, html) {
    return `<label for="${id}">${label}</label>${html}`;
  }

  function select(id, options, value) {
    const content = options.map((opt) => `<option value="${opt}" ${opt === value ? "selected" : ""}>${opt}</option>`).join("");
    return `<select id="${id}">${content}</select>`;
  }

  function renderPayloadFields() {
    const type = el.actionType.value;
    const ticket = getTicket();
    const defaultDuplicate = ticket?.suspected_duplicate_ids?.[0] || "";

    if (type === "classify") {
      el.payloadFields.innerHTML = [
        field("f-severity", "severity", select("f-severity", ["sev0", "sev1", "sev2", "sev3"], "sev2")),
        field("f-priority", "priority", select("f-priority", ["p0", "p1", "p2", "p3"], "p2")),
        field("f-component", "component", select("f-component", components(), components()[0] || "api-gateway")),
      ].join("");
    } else if (type === "assign") {
      el.payloadFields.innerHTML = field("f-team", "team", select("f-team", teams(), teams()[0] || "backend-api"));
    } else if (type === "mark_duplicate") {
      el.payloadFields.innerHTML = field("f-canonical", "canonical_ticket_id", `<input id="f-canonical" value="${defaultDuplicate}" placeholder="BUG-1001" />`);
    } else if (type === "request_info") {
      el.payloadFields.innerHTML = field("f-info", "info_type", select("f-info", ["repro_steps", "logs", "both"], "both"));
    } else if (type === "defer") {
      el.payloadFields.innerHTML = field("f-defer", "reason", `<input id="f-defer" value="needs prioritization review" />`);
    } else if (type === "close") {
      el.payloadFields.innerHTML = field("f-close", "reason", select("f-close", ["invalid", "wont_fix", "cannot_reproduce", "resolved"], "resolved"));
    } else if (type === "escalate_incident") {
      el.payloadFields.innerHTML = field("f-just", "justification", `<input id="f-just" value="High-impact production risk detected" />`);
    } else {
      el.payloadFields.innerHTML = "<p class='muted small'>No payload required.</p>";
    }

    renderActionPreview();
  }

  function buildAction() {
    const type = el.actionType.value;
    const action = { action_type: type };

    if (type === "classify") {
      action.classify = {
        severity: document.getElementById("f-severity").value,
        priority: document.getElementById("f-priority").value,
        component: document.getElementById("f-component").value,
      };
    } else if (type === "assign") {
      action.assign = { team: document.getElementById("f-team").value };
    } else if (type === "mark_duplicate") {
      action.mark_duplicate = { canonical_ticket_id: (document.getElementById("f-canonical").value || "").trim() };
    } else if (type === "request_info") {
      action.request_info = { info_type: document.getElementById("f-info").value };
    } else if (type === "defer") {
      action.defer = { reason: (document.getElementById("f-defer").value || "backlog").trim() };
    } else if (type === "close") {
      action.close = { reason: document.getElementById("f-close").value };
    } else if (type === "escalate_incident") {
      action.escalate_incident = { justification: (document.getElementById("f-just").value || "Critical impact").trim() };
    } else if (type === "next_ticket") {
      action.next_ticket = {};
    }

    return action;
  }

  function renderActionPreview() {
    el.actionPreview.textContent = pretty(buildAction());
  }

  async function loadHealth() {
    try {
      const data = await api("/health");
      el.health.textContent = data?.status || "unknown";
    } catch {
      el.health.textContent = "offline";
    }
  }

  async function loadTasks() {
    try {
      const data = await api("/tasks");
      const tasks = Array.isArray(data?.tasks) ? data.tasks : [];
      el.taskSelect.innerHTML = tasks.map((t) => `<option value="${t.id}">${t.id}</option>`).join("");
      if (!tasks.length) {
        el.taskSelect.innerHTML = FALLBACK_TASKS.map((t) => `<option value="${t.id}">${t.id}</option>`).join("");
      }
    } catch {
      el.taskSelect.innerHTML = FALLBACK_TASKS.map((t) => `<option value="${t.id}">${t.id}</option>`).join("");
    }
  }

  async function loadBaseline() {
    try {
      const data = await api("/baseline");
      const mean = Number(data?.mean_score ?? 0).toFixed(4);
      const rows = (data?.results || []).map((r) => `${r.task_id}:${Number(r.score).toFixed(4)}`).join(" | ");
      el.baseline.textContent = `Baseline mean=${mean}${rows ? ` | ${rows}` : ""}`;
    } catch {
      el.baseline.textContent = "Baseline unavailable.";
    }
  }

  async function refreshState(silent = false) {
    const state = await api("/state");
    currentState = state;
    episodeDone = Boolean(state?.episode_done);
    el.stateJson.textContent = pretty(state);
    updateMetrics();
    if (!silent) {
      setStatus("state updated");
    }
  }

  async function doReset() {
    try {
      setStatus("resetting...");
      el.log.innerHTML = "";
      el.rewardJson.textContent = "{}";

      const payload = {
        task_id: el.taskSelect.value,
        seed: Number(el.seedInput.value || 42),
      };
      const observation = await api("/reset", "POST", payload);
      currentObservation = observation;
      episodeDone = false;
      renderTicket();
      await refreshState(true);
      addLog(`reset task=${payload.task_id} seed=${payload.seed}`);
      setStatus("episode ready");
    } catch (err) {
      setStatus(`reset error: ${err.message}`);
      addLog(`reset failed: ${err.message}`);
    }
  }

  async function doSuggest() {
    if (!getTicket() || episodeDone) {
      setStatus("no active ticket");
      return;
    }

    try {
      setStatus("suggesting...");
      const result = await api("/suggest_action");
      const action = result?.action;
      if (!action?.action_type) {
        throw new Error("invalid suggestion payload");
      }

      el.actionType.value = action.action_type;
      renderPayloadFields();

      if (action.action_type === "classify" && action.classify) {
        document.getElementById("f-severity").value = action.classify.severity;
        document.getElementById("f-priority").value = action.classify.priority;
        document.getElementById("f-component").value = action.classify.component;
      } else if (action.action_type === "assign" && action.assign) {
        document.getElementById("f-team").value = action.assign.team;
      } else if (action.action_type === "mark_duplicate" && action.mark_duplicate) {
        document.getElementById("f-canonical").value = action.mark_duplicate.canonical_ticket_id;
      } else if (action.action_type === "request_info" && action.request_info) {
        document.getElementById("f-info").value = action.request_info.info_type;
      } else if (action.action_type === "defer" && action.defer) {
        document.getElementById("f-defer").value = action.defer.reason;
      } else if (action.action_type === "close" && action.close) {
        document.getElementById("f-close").value = action.close.reason;
      } else if (action.action_type === "escalate_incident" && action.escalate_incident) {
        document.getElementById("f-just").value = action.escalate_incident.justification;
      }

      renderActionPreview();
      addLog(`suggested action=${action.action_type}`);
      setStatus("suggestion loaded");
    } catch (err) {
      setStatus(`suggest error: ${err.message}`);
      addLog(`suggest failed: ${err.message}`);
    }
  }

  async function doStep() {
    if (!getTicket()) {
      setStatus("reset first");
      return;
    }
    if (episodeDone) {
      setStatus("episode done, reset again");
      return;
    }

    const action = buildAction();
    try {
      setStatus("stepping...");
      const result = await api("/step", "POST", { action });
      currentObservation = result.observation;
      episodeDone = Boolean(result.done);
      el.rewardJson.textContent = pretty(result.reward);
      renderTicket();
      await refreshState(true);

      const reward = Number(result?.reward?.step_reward ?? 0).toFixed(2);
      const err = result?.info?.validation_error || "null";
      addLog(`step action=${action.action_type} reward=${reward} done=${episodeDone} error=${err}`);
      setStatus(episodeDone ? "episode complete" : "step ok");
    } catch (err) {
      setStatus(`step error: ${err.message}`);
      addLog(`step failed: ${err.message}`);
    }
  }

  el.actionType.addEventListener("change", renderPayloadFields);
  el.payloadFields.addEventListener("input", renderActionPreview);
  el.payloadFields.addEventListener("change", renderActionPreview);
  el.resetBtn.addEventListener("click", doReset);
  el.stateBtn.addEventListener("click", () => refreshState(false).catch((err) => setStatus(`state error: ${err.message}`)));
  el.suggestBtn.addEventListener("click", doSuggest);
  el.stepBtn.addEventListener("click", doStep);

  renderPayloadFields();
  loadHealth();
  loadTasks();
  loadBaseline();
  refreshState(true).then(() => setStatus("ready")).catch(() => setStatus("ready"));
})();
