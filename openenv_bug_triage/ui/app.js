const els = {
  taskSelect: document.getElementById("task-select"),
  seedInput: document.getElementById("seed-input"),
  resetBtn: document.getElementById("reset-btn"),
  stateBtn: document.getElementById("state-btn"),
  stepBtn: document.getElementById("step-btn"),
  status: document.getElementById("status"),
  actionType: document.getElementById("action-type"),
  payloadFields: document.getElementById("payload-fields"),
  actionPreview: document.getElementById("action-preview"),
  ticketMeta: document.getElementById("ticket-meta"),
  ticketBody: document.getElementById("ticket-body"),
  stepLog: document.getElementById("step-log"),
  stateJson: document.getElementById("state-json"),
  stepsUsed: document.getElementById("steps-used"),
  stepsRemaining: document.getElementById("steps-remaining"),
  doneFlag: document.getElementById("done-flag"),
  cumulativeReward: document.getElementById("cumulative-reward"),
};

let currentObservation = null;
let done = false;
let stepCount = 0;
let cumulativeReward = 0;

const DEFAULT_COMPONENTS = [
  "api-gateway",
  "auth-service",
  "user-service",
  "payment-service",
  "web-app",
  "ios-app",
  "android-app",
  "database",
  "cache",
  "cdn",
];

const DEFAULT_TEAMS = [
  "backend-api",
  "frontend-web",
  "mobile-ios",
  "mobile-android",
  "infrastructure",
  "data-platform",
];

function setStatus(text, kind = "idle") {
  els.status.textContent = text;
  els.status.className = `status status-${kind}`;
}

function pretty(obj) {
  return JSON.stringify(obj, null, 2);
}

function optionHtml(value, selectedValue) {
  const selected = value === selectedValue ? "selected" : "";
  return `<option value="${value}" ${selected}>${value}</option>`;
}

function componentsList() {
  return currentObservation?.available_components?.length
    ? currentObservation.available_components
    : DEFAULT_COMPONENTS;
}

function teamsList() {
  return currentObservation?.available_teams?.length
    ? currentObservation.available_teams
    : DEFAULT_TEAMS;
}

function renderPayloadFields() {
  const actionType = els.actionType.value;
  const components = componentsList();
  const teams = teamsList();

  if (actionType === "classify") {
    els.payloadFields.innerHTML = `
      <label>
        <span>Severity</span>
        <select id="f-severity">
          <option value="sev0">sev0</option>
          <option value="sev1">sev1</option>
          <option value="sev2" selected>sev2</option>
          <option value="sev3">sev3</option>
        </select>
      </label>
      <label>
        <span>Priority</span>
        <select id="f-priority">
          <option value="p0">p0</option>
          <option value="p1">p1</option>
          <option value="p2" selected>p2</option>
          <option value="p3">p3</option>
        </select>
      </label>
      <label>
        <span>Component</span>
        <select id="f-component">
          ${components.map((c, i) => optionHtml(c, i === 0 ? c : "")).join("")}
        </select>
      </label>
    `;
    return;
  }

  if (actionType === "assign") {
    els.payloadFields.innerHTML = `
      <label>
        <span>Team</span>
        <select id="f-team">
          ${teams.map((t, i) => optionHtml(t, i === 0 ? t : "")).join("")}
        </select>
      </label>
    `;
    return;
  }

  if (actionType === "mark_duplicate") {
    els.payloadFields.innerHTML = `
      <label>
        <span>Canonical Ticket ID</span>
        <input id="f-canonical" type="text" placeholder="BUG-1001" />
      </label>
    `;
    return;
  }

  if (actionType === "request_info") {
    els.payloadFields.innerHTML = `
      <label>
        <span>Info Type</span>
        <select id="f-info-type">
          <option value="repro_steps">repro_steps</option>
          <option value="logs">logs</option>
          <option value="both" selected>both</option>
        </select>
      </label>
    `;
    return;
  }

  if (actionType === "defer") {
    els.payloadFields.innerHTML = `
      <label>
        <span>Reason</span>
        <input id="f-defer-reason" type="text" placeholder="Waiting for roadmap decision" />
      </label>
    `;
    return;
  }

  if (actionType === "close") {
    els.payloadFields.innerHTML = `
      <label>
        <span>Close Reason</span>
        <select id="f-close-reason">
          <option value="invalid">invalid</option>
          <option value="wont_fix">wont_fix</option>
          <option value="cannot_reproduce">cannot_reproduce</option>
          <option value="resolved">resolved</option>
        </select>
      </label>
    `;
    return;
  }

  if (actionType === "escalate_incident") {
    els.payloadFields.innerHTML = `
      <label>
        <span>Justification</span>
        <textarea id="f-justification" placeholder="Production impact and SLA risk detected."></textarea>
      </label>
    `;
    return;
  }

  els.payloadFields.innerHTML = `<p class="ticket-meta">No payload required.</p>`;
}

function buildAction() {
  const type = els.actionType.value;
  const action = { action_type: type };

  if (type === "classify") {
    action.classify = {
      severity: document.getElementById("f-severity").value,
      priority: document.getElementById("f-priority").value,
      component: document.getElementById("f-component").value,
    };
  } else if (type === "assign") {
    action.assign = {
      team: document.getElementById("f-team").value,
    };
  } else if (type === "mark_duplicate") {
    action.mark_duplicate = {
      canonical_ticket_id: document.getElementById("f-canonical").value.trim(),
    };
  } else if (type === "request_info") {
    action.request_info = {
      info_type: document.getElementById("f-info-type").value,
    };
  } else if (type === "defer") {
    action.defer = {
      reason: document.getElementById("f-defer-reason").value.trim() || "backlog",
    };
  } else if (type === "close") {
    action.close = {
      reason: document.getElementById("f-close-reason").value,
    };
  } else if (type === "escalate_incident") {
    action.escalate_incident = {
      justification: document.getElementById("f-justification").value.trim() || "Critical impact",
    };
  } else if (type === "next_ticket") {
    action.next_ticket = {};
  }

  return action;
}

function renderPreview() {
  const action = buildAction();
  els.actionPreview.textContent = pretty(action);
}

function renderObservation(obs) {
  currentObservation = obs;
  if (!obs || !obs.current_ticket) {
    els.ticketMeta.textContent = "No active ticket";
    els.ticketBody.textContent = "{}";
    return;
  }

  const t = obs.current_ticket;
  els.ticketMeta.textContent = `${t.ticket_id} | ${t.service} | ${t.reporter_type} | tier:${t.customer_tier}`;
  els.ticketBody.textContent = pretty(t);

  els.stepsUsed.textContent = String(obs.steps_used);
  els.stepsRemaining.textContent = String(obs.steps_remaining);

  renderPayloadFields();
  renderPreview();
}

function appendLog(text) {
  const li = document.createElement("li");
  li.textContent = text;
  els.stepLog.prepend(li);
}

async function api(url, method = "GET", body = null) {
  const opts = { method, headers: {} };
  if (body !== null) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }

  const res = await fetch(url, opts);
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const msg = data?.detail || `HTTP ${res.status}`;
    throw new Error(msg);
  }
  return data;
}

async function doReset() {
  const task_id = els.taskSelect.value;
  const seed = Number(els.seedInput.value || 42);

  try {
    setStatus("Resetting episode...", "idle");
    const obs = await api("/reset", "POST", { task_id, seed });
    done = false;
    stepCount = 0;
    cumulativeReward = 0;
    els.stepLog.innerHTML = "";
    renderObservation(obs);
    els.doneFlag.textContent = "false";
    els.cumulativeReward.textContent = "0.00";
    setStatus(`Ready on ${obs.current_ticket?.ticket_id || "no-ticket"}`, "ok");
    appendLog(`reset task=${task_id} seed=${seed}`);
  } catch (err) {
    setStatus(`Reset failed: ${err.message}`, "error");
  }
}

async function doStep() {
  if (!currentObservation) {
    setStatus("Run Reset first.", "error");
    return;
  }
  if (done) {
    setStatus("Episode already done. Reset to start another.", "error");
    return;
  }

  const action = buildAction();

  try {
    const result = await api("/step", "POST", { action });
    stepCount += 1;
    done = Boolean(result.done);

    const reward = Number(result.reward?.step_reward || 0);
    cumulativeReward = Number(result.reward?.cumulative_reward || cumulativeReward);

    renderObservation(result.observation);
    els.doneFlag.textContent = String(done);
    els.cumulativeReward.textContent = cumulativeReward.toFixed(2);

    const err = result.info?.validation_error ? ` error=${result.info.validation_error}` : "";
    appendLog(
      `step=${stepCount} action=${action.action_type} reward=${reward.toFixed(2)} done=${done}${err}`
    );

    setStatus(done ? "Episode completed." : "Step accepted.", done ? "ok" : "idle");
  } catch (err) {
    setStatus(`Step failed: ${err.message}`, "error");
    appendLog(`step_error ${err.message}`);
  }
}

async function fetchState() {
  try {
    const state = await api("/state", "GET");
    els.stateJson.textContent = pretty(state);
    setStatus("State fetched.", "ok");
  } catch (err) {
    setStatus(`State fetch failed: ${err.message}`, "error");
  }
}

els.actionType.addEventListener("change", () => {
  renderPayloadFields();
  renderPreview();
});

els.payloadFields.addEventListener("input", renderPreview);
els.payloadFields.addEventListener("change", renderPreview);
els.resetBtn.addEventListener("click", doReset);
els.stepBtn.addEventListener("click", doStep);
els.stateBtn.addEventListener("click", fetchState);

renderPayloadFields();
renderPreview();
setStatus("Idle", "idle");

