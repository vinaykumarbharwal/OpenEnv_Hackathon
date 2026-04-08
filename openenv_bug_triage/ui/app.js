const els = {
  taskSelect: document.getElementById("task-select"),
  seedInput: document.getElementById("seed-input"),
  resetBtn: document.getElementById("reset-btn"),
  stateBtn: document.getElementById("state-btn"),
  stepBtn: document.getElementById("step-btn"),
  status: document.getElementById("status"),
  healthPill: document.getElementById("health-pill"),
  taskCards: document.getElementById("task-cards"),
  taskBrief: document.getElementById("task-brief"),
  actionType: document.getElementById("action-type"),
  actionHint: document.getElementById("action-hint"),
  payloadFields: document.getElementById("payload-fields"),
  actionPreview: document.getElementById("action-preview"),
  ticketMeta: document.getElementById("ticket-meta"),
  ticketTitle: document.getElementById("ticket-title"),
  ticketSummary: document.getElementById("ticket-summary"),
  ticketDescription: document.getElementById("ticket-description"),
  ticketComponents: document.getElementById("ticket-components"),
  ticketDuplicates: document.getElementById("ticket-duplicates"),
  ticketEvidence: document.getElementById("ticket-evidence"),
  lastActionResult: document.getElementById("last-action-result"),
  ticketBody: document.getElementById("ticket-body"),
  rewardBreakdown: document.getElementById("reward-breakdown"),
  stepLog: document.getElementById("step-log"),
  stateJson: document.getElementById("state-json"),
  stepsUsed: document.getElementById("steps-used"),
  stepsRemaining: document.getElementById("steps-remaining"),
  queueRemaining: document.getElementById("queue-remaining"),
  urgentCount: document.getElementById("urgent-count"),
  slaCount: document.getElementById("sla-count"),
  partialScore: document.getElementById("partial-score"),
  doneFlag: document.getElementById("done-flag"),
  cumulativeReward: document.getElementById("cumulative-reward"),
};

const BASE_PATH = String(window.OPENENV_BASE_PATH || "").replace(/\/$/, "");

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

const FALLBACK_TASKS = [
  { id: "bug_triage_easy", difficulty: "easy", description: "8 clear tickets, minimal duplicates" },
  { id: "bug_triage_medium", difficulty: "medium", description: "15 mixed-quality tickets, several duplicates" },
  { id: "bug_triage_hard", difficulty: "hard", description: "25 noisy tickets, strict SLA pressure" },
];

const TASK_GUIDE = {
  bug_triage_easy: {
    headline: "Clear tickets, clean decisions",
    summary: "This task is about proving the environment handles practical triage basics with deterministic grading.",
    points: [
      "Prioritize clean severity, priority, and component labels.",
      "Route valid bugs to the correct team without wasting steps.",
      "Keep mistakes low and show the baseline workflow clearly.",
    ],
  },
  bug_triage_medium: {
    headline: "Noise, duplicates, and missing context",
    summary: "The medium task rewards judgment instead of only raw labeling speed.",
    points: [
      "Catch duplicates when the hints are present.",
      "Use request_info when repro data or logs are actually missing.",
      "Avoid loops and destructive actions that drag the score down.",
    ],
  },
  bug_triage_hard: {
    headline: "SLA pressure and escalation discipline",
    summary: "The hardest task makes queue management and critical-incident handling visible to judges.",
    points: [
      "Handle sev0 and sev1 reports with strong escalation behavior.",
      "Protect the step budget across a larger, noisier queue.",
      "Show policy quality under pressure instead of gambling on shortcuts.",
    ],
  },
};

const ACTION_HINTS = {
  classify: "Set severity, priority, and component for the active ticket. Candidate components from the observation are shown first.",
  assign: "Use this after classification to route the issue to the owning team.",
  mark_duplicate: "Link the report to a canonical ticket when the duplicate hints are strong enough.",
  request_info: "Ask for missing repro steps or logs when the report is incomplete.",
  defer: "Use sparingly. Deferring the wrong issue can hurt both reward and grader outcomes.",
  close: "Closing is high risk unless the ticket clearly deserves it.",
  escalate_incident: "Escalate critical production incidents when urgency and customer impact justify it.",
  next_ticket: "Move on only when you are comfortable with the current decision quality.",
};

let currentObservation = null;
let done = false;
let stepCount = 0;
let cumulativeReward = 0;
let busy = false;
let taskRegistry = { tasks: FALLBACK_TASKS };

function pretty(obj) {
  return JSON.stringify(obj ?? {}, null, 2);
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => {
    const table = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    };
    return table[char] || char;
  });
}

function formatDate(value) {
  if (!value) {
    return "unknown date";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "unknown date";
  }
  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function formatDifficulty(value) {
  if (!value) {
    return "Task";
  }
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function humanizeKey(value) {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function selectedTaskId() {
  return els.taskSelect.value;
}

function availableTasks() {
  return Array.isArray(taskRegistry.tasks) && taskRegistry.tasks.length
    ? taskRegistry.tasks
    : FALLBACK_TASKS;
}

function taskMetaById(taskId) {
  return availableTasks().find((task) => task.id === taskId) || FALLBACK_TASKS[0];
}

function mergeUnique(primary, secondary) {
  return [...new Set([...(primary || []), ...(secondary || [])])];
}

function currentTicket() {
  return currentObservation?.current_ticket || null;
}

function componentsList() {
  const ticket = currentTicket();
  return mergeUnique(ticket?.component_candidates || [], currentObservation?.available_components || DEFAULT_COMPONENTS);
}

function teamsList() {
  return currentObservation?.available_teams?.length
    ? currentObservation.available_teams
    : DEFAULT_TEAMS;
}

function suggestedInfoType() {
  const ticket = currentTicket();
  if (!ticket) {
    return "both";
  }
  if (!ticket.repro_steps_present && !ticket.logs_present) {
    return "both";
  }
  if (!ticket.repro_steps_present) {
    return "repro_steps";
  }
  if (!ticket.logs_present) {
    return "logs";
  }
  return "both";
}

function setStatus(text, kind = "idle") {
  els.status.textContent = text;
  els.status.className = `status status-${kind}`;
}

function setHealth(text, kind = "pending") {
  els.healthPill.textContent = text;
  els.healthPill.className = `health-pill is-${kind}`;
}

function updateButtonState() {
  const hasActiveTicket = Boolean(currentObservation?.current_ticket) && !done;
  els.resetBtn.disabled = busy;
  els.stateBtn.disabled = busy;
  els.stepBtn.disabled = busy || !hasActiveTicket;
}

function renderTokens(container, values, emptyLabel = "None") {
  container.innerHTML = "";

  const items = values && values.length ? values : [{ label: emptyLabel, tone: "muted" }];
  items.forEach((item) => {
    const token = document.createElement("span");
    const label = typeof item === "string" ? item : item.label;
    const tone = typeof item === "string" ? "" : item.tone || "";
    token.className = `token${tone ? ` token-${tone}` : ""}`;
    token.textContent = label;
    container.appendChild(token);
  });
}

function renderSummaryMetrics(observation = currentObservation) {
  els.stepsUsed.textContent = String(observation?.steps_used ?? stepCount ?? 0);
  els.stepsRemaining.textContent = String(observation?.steps_remaining ?? 0);
  els.queueRemaining.textContent = String(observation?.queue_stats?.remaining_count ?? 0);
  els.urgentCount.textContent = String(observation?.queue_stats?.urgent_count ?? 0);
  els.slaCount.textContent = String(observation?.queue_stats?.sla_at_risk_count ?? 0);
  els.partialScore.textContent = Number(observation?.partial_score ?? 0).toFixed(2);
  els.cumulativeReward.textContent = Number(cumulativeReward || 0).toFixed(2);
  els.doneFlag.textContent = done ? "completed" : observation?.current_ticket ? "open" : "idle";
}

function renderTaskOptions() {
  const selected = selectedTaskId();
  els.taskSelect.innerHTML = availableTasks()
    .map((task) => `<option value="${escapeHtml(task.id)}">${escapeHtml(task.id)}</option>`)
    .join("");

  els.taskSelect.value = availableTasks().some((task) => task.id === selected)
    ? selected
    : availableTasks()[0].id;
}

function renderTaskCards() {
  const selected = selectedTaskId();
  els.taskCards.innerHTML = availableTasks()
    .map((task) => {
      const guide = TASK_GUIDE[task.id] || TASK_GUIDE.bug_triage_easy;
      const activeClass = task.id === selected ? " is-active" : "";
      return `
        <button type="button" class="task-card${activeClass}" data-task="${escapeHtml(task.id)}">
          <small>${escapeHtml(formatDifficulty(task.difficulty))}</small>
          <strong>${escapeHtml(guide.headline)}</strong>
          <p>${escapeHtml(task.description)}</p>
        </button>
      `;
    })
    .join("");
}

function renderTaskBrief() {
  const taskId = selectedTaskId();
  const meta = taskMetaById(taskId);
  const guide = TASK_GUIDE[taskId] || TASK_GUIDE.bug_triage_easy;

  els.taskBrief.innerHTML = `
    <div class="task-brief-header">
      <h3>${escapeHtml(guide.headline)}</h3>
      <span class="difficulty-pill">${escapeHtml(formatDifficulty(meta.difficulty))}</span>
    </div>
    <p>${escapeHtml(guide.summary)}</p>
    <ul class="mini-list">
      ${guide.points.map((point) => `<li>${escapeHtml(point)}</li>`).join("")}
    </ul>
  `;
}

function renderActionHint() {
  const actionType = els.actionType.value;
  const ticket = currentTicket();
  let hint = ACTION_HINTS[actionType] || "Choose an action and step the environment.";

  if (actionType === "mark_duplicate" && ticket?.suspected_duplicate_ids?.length) {
    hint += ` Suggested canonical IDs: ${ticket.suspected_duplicate_ids.join(", ")}.`;
  }
  if (actionType === "request_info" && ticket) {
    const missing = [];
    if (!ticket.repro_steps_present) {
      missing.push("repro steps");
    }
    if (!ticket.logs_present) {
      missing.push("logs");
    }
    if (missing.length) {
      hint += ` Missing on this ticket: ${missing.join(" and ")}.`;
    }
  }
  if (actionType === "classify" && ticket?.component_candidates?.length) {
    hint += ` Observation candidates: ${ticket.component_candidates.join(", ")}.`;
  }

  els.actionHint.textContent = hint;
}

function optionHtml(value, selectedValue) {
  const selected = value === selectedValue ? "selected" : "";
  return `<option value="${escapeHtml(value)}" ${selected}>${escapeHtml(value)}</option>`;
}

function renderPayloadFields() {
  const actionType = els.actionType.value;
  const ticket = currentTicket();
  const components = componentsList();
  const teams = teamsList();
  const duplicateSuggestion = ticket?.suspected_duplicate_ids?.[0] || "";

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
          ${components.map((component, index) => optionHtml(component, index === 0 ? component : "")).join("")}
        </select>
      </label>
    `;
  } else if (actionType === "assign") {
    els.payloadFields.innerHTML = `
      <label>
        <span>Team</span>
        <select id="f-team">
          ${teams.map((team, index) => optionHtml(team, index === 0 ? team : "")).join("")}
        </select>
      </label>
    `;
  } else if (actionType === "mark_duplicate") {
    els.payloadFields.innerHTML = `
      <label>
        <span>Canonical ticket ID</span>
        <input id="f-canonical" type="text" value="${escapeHtml(duplicateSuggestion)}" placeholder="BUG-1001" />
      </label>
    `;
  } else if (actionType === "request_info") {
    const infoType = suggestedInfoType();
    els.payloadFields.innerHTML = `
      <label>
        <span>Info type</span>
        <select id="f-info-type">
          <option value="repro_steps" ${infoType === "repro_steps" ? "selected" : ""}>repro_steps</option>
          <option value="logs" ${infoType === "logs" ? "selected" : ""}>logs</option>
          <option value="both" ${infoType === "both" ? "selected" : ""}>both</option>
        </select>
      </label>
    `;
  } else if (actionType === "defer") {
    els.payloadFields.innerHTML = `
      <label>
        <span>Reason</span>
        <input id="f-defer-reason" type="text" value="needs prioritization review" placeholder="Waiting for roadmap decision" />
      </label>
    `;
  } else if (actionType === "close") {
    els.payloadFields.innerHTML = `
      <label>
        <span>Close reason</span>
        <select id="f-close-reason">
          <option value="invalid">invalid</option>
          <option value="wont_fix">wont_fix</option>
          <option value="cannot_reproduce">cannot_reproduce</option>
          <option value="resolved">resolved</option>
        </select>
      </label>
    `;
  } else if (actionType === "escalate_incident") {
    els.payloadFields.innerHTML = `
      <label>
        <span>Justification</span>
        <textarea id="f-justification" placeholder="Production impact, customer scope, and urgency justify escalation."></textarea>
      </label>
    `;
  } else {
    els.payloadFields.innerHTML = `<p class="muted-copy">No payload required for this action.</p>`;
  }

  renderActionHint();
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
  els.actionPreview.textContent = pretty(buildAction());
}

function renderRewardBreakdown(breakdown = null) {
  els.rewardBreakdown.innerHTML = "";
  const entries = breakdown ? Object.entries(breakdown) : [];

  if (!entries.length) {
    const li = document.createElement("li");
    li.textContent = "Take a step to inspect reward components.";
    els.rewardBreakdown.appendChild(li);
    return;
  }

  entries
    .sort((a, b) => Math.abs(Number(b[1]) || 0) - Math.abs(Number(a[1]) || 0))
    .forEach(([key, rawValue]) => {
      const value = Number(rawValue || 0);
      const li = document.createElement("li");
      const label = document.createElement("span");
      const score = document.createElement("strong");

      label.textContent = humanizeKey(key);
      score.textContent = `${value >= 0 ? "+" : ""}${value.toFixed(2)}`;
      score.className = value > 0 ? "value-good" : value < 0 ? "value-bad" : "value-neutral";

      li.append(label, score);
      els.rewardBreakdown.appendChild(li);
    });
}

function appendLog({ title, meta, note, tone = "neutral" }) {
  const li = document.createElement("li");
  li.className = `log-entry${tone === "bad" ? " is-bad" : tone === "warn" ? " is-warn" : ""}`;

  const heading = document.createElement("strong");
  heading.textContent = title;

  const metaNode = document.createElement("div");
  metaNode.className = "log-meta";
  metaNode.textContent = meta;

  const noteNode = document.createElement("p");
  noteNode.className = "log-note";
  noteNode.textContent = note;

  li.append(heading, metaNode, noteNode);
  els.stepLog.prepend(li);
}

function renderObservation(observation) {
  currentObservation = observation;
  const ticket = observation?.current_ticket || null;

  if (!ticket) {
    els.ticketMeta.textContent = done
      ? "Episode completed. Reset to start another run."
      : "Run reset to load a task.";
    els.ticketTitle.textContent = "No active ticket";
    els.ticketDescription.textContent = "The current observation does not include an active ticket.";
    els.lastActionResult.textContent = observation?.last_action_result || "No action taken yet.";
    renderTokens(els.ticketSummary, [], "Waiting for ticket data");
    renderTokens(els.ticketComponents, [], "No component hints");
    renderTokens(els.ticketDuplicates, [], "No duplicate hints");
    renderTokens(els.ticketEvidence, [], "No evidence details");
    els.ticketBody.textContent = pretty(observation || {});
    renderSummaryMetrics(observation);
    updateButtonState();
    renderPayloadFields();
    renderPreview();
    return;
  }

  els.ticketMeta.textContent = `${ticket.ticket_id} - ${ticket.service} - ${formatDate(ticket.created_at)}`;
  els.ticketTitle.textContent = ticket.title;
  els.ticketDescription.textContent = ticket.description;
  els.lastActionResult.textContent = observation?.last_action_result || "No action taken yet.";

  renderTokens(els.ticketSummary, [
    { label: `Reporter: ${ticket.reporter_type}` },
    { label: `Tier: ${ticket.customer_tier}` },
    { label: `Attachments: ${ticket.attachments_count}` },
  ]);

  renderTokens(
    els.ticketComponents,
    (ticket.component_candidates || []).map((component) => ({ label: component, tone: "good" })),
    "No component hints"
  );

  renderTokens(
    els.ticketDuplicates,
    (ticket.suspected_duplicate_ids || []).map((ticketId) => ({ label: ticketId, tone: "warn" })),
    "No duplicate hints"
  );

  renderTokens(els.ticketEvidence, [
    {
      label: ticket.repro_steps_present ? "Repro steps present" : "Repro steps missing",
      tone: ticket.repro_steps_present ? "good" : "warn",
    },
    {
      label: ticket.logs_present ? "Logs present" : "Logs missing",
      tone: ticket.logs_present ? "good" : "warn",
    },
    {
      label: ticket.attachments_count > 0 ? "Attachments included" : "No attachments",
      tone: ticket.attachments_count > 0 ? "good" : "muted",
    },
  ]);

  els.ticketBody.textContent = pretty(observation);
  renderSummaryMetrics(observation);
  renderPayloadFields();
  renderPreview();
  updateButtonState();
}

async function api(url, method = "GET", body = null) {
  const normalizedUrl = url.startsWith("/")
    ? `${BASE_PATH}${url}`
    : `${BASE_PATH}/${url}`;
  const options = { method, headers: {} };
  if (body !== null) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }

  const response = await fetch(normalizedUrl, options);
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const message = data?.detail || `HTTP ${response.status}`;
    throw new Error(message);
  }
  return data;
}

async function fetchHealth() {
  try {
    const health = await api("/health");
    setHealth(health?.status === "ok" ? "Online" : "Degraded", health?.status === "ok" ? "ok" : "bad");
  } catch (error) {
    setHealth("Offline", "bad");
  }
}

async function fetchTasks() {
  try {
    const data = await api("/tasks");
    if (Array.isArray(data?.tasks) && data.tasks.length) {
      taskRegistry = data;
    }
  } catch (error) {
    taskRegistry = { tasks: FALLBACK_TASKS };
  }

  renderTaskOptions();
  renderTaskCards();
  renderTaskBrief();
}

async function fetchState({ silent = false } = {}) {
  const state = await api("/state");
  els.stateJson.textContent = pretty(state);

  if (state.initialized) {
    stepCount = Number(state.steps_used || 0);
    cumulativeReward = Number(state.cumulative_reward || 0);
    done = Boolean(state.episode_done);

    if (state.current_task_id && availableTasks().some((task) => task.id === state.current_task_id)) {
      els.taskSelect.value = state.current_task_id;
      renderTaskCards();
      renderTaskBrief();
    }

    els.stepsUsed.textContent = String(state.steps_used || 0);
    els.stepsRemaining.textContent = String(state.steps_remaining || 0);
    els.cumulativeReward.textContent = Number(state.cumulative_reward || 0).toFixed(2);
    els.doneFlag.textContent = done ? "completed" : "open";
  } else if (!currentObservation) {
    renderSummaryMetrics(null);
  }

  if (!silent) {
    setStatus(state.initialized ? "State snapshot updated." : "Server ready. Reset to start an episode.", "ok");
  }

  updateButtonState();
  return state;
}

async function doReset() {
  const taskId = els.taskSelect.value;
  const seed = Number(els.seedInput.value || 42);

  try {
    busy = true;
    updateButtonState();
    setStatus("Resetting episode...", "idle");

    const observation = await api("/reset", "POST", { task_id: taskId, seed });
    done = false;
    stepCount = 0;
    cumulativeReward = 0;
    els.stepLog.innerHTML = "";
    renderRewardBreakdown(null);
    renderObservation(observation);
    await fetchState({ silent: true });

    appendLog({
      title: `Episode reset - ${taskId}`,
      meta: `seed=${seed}`,
      note: taskMetaById(taskId).description,
    });
    setStatus(`Episode ready on ${taskId}.`, "ok");
  } catch (error) {
    setStatus(`Reset failed: ${error.message}`, "error");
    appendLog({
      title: "Reset failed",
      meta: "reset",
      note: error.message,
      tone: "bad",
    });
  } finally {
    busy = false;
    updateButtonState();
  }
}

async function doStep() {
  if (!currentObservation?.current_ticket) {
    setStatus("Run reset first.", "error");
    return;
  }

  if (done) {
    setStatus("Episode already completed. Reset to start again.", "warn");
    return;
  }

  const action = buildAction();

  try {
    busy = true;
    updateButtonState();
    setStatus("Submitting step...", "idle");

    const result = await api("/step", "POST", { action });
    stepCount += 1;
    done = Boolean(result.done);
    cumulativeReward = Number(result.reward?.cumulative_reward || cumulativeReward);

    renderObservation(result.observation);
    renderRewardBreakdown(result.reward?.reward_breakdown);
    await fetchState({ silent: true });

    const reward = Number(result.reward?.step_reward || 0);
    const validationError = result.info?.validation_error;
    const note = validationError || result.observation?.last_action_result || "Step accepted.";

    appendLog({
      title: `Step ${stepCount} - ${action.action_type}`,
      meta: `reward=${reward.toFixed(2)} - ${done ? "completed" : "running"}`,
      note,
      tone: validationError ? "warn" : "neutral",
    });

    if (validationError) {
      setStatus(`Step accepted with penalty: ${validationError}`, "warn");
    } else {
      setStatus(done ? "Episode completed." : "Step accepted.", done ? "ok" : "idle");
    }
  } catch (error) {
    setStatus(`Step failed: ${error.message}`, "error");
    appendLog({
      title: "Step failed",
      meta: `action=${action.action_type}`,
      note: error.message,
      tone: "bad",
    });
  } finally {
    busy = false;
    updateButtonState();
  }
}

els.taskSelect.addEventListener("change", () => {
  renderTaskCards();
  renderTaskBrief();
});

els.taskCards.addEventListener("click", (event) => {
  const card = event.target.closest("[data-task]");
  if (!card) {
    return;
  }

  els.taskSelect.value = card.dataset.task;
  renderTaskCards();
  renderTaskBrief();
});

els.actionType.addEventListener("change", () => {
  renderPayloadFields();
  renderPreview();
});

els.payloadFields.addEventListener("input", renderPreview);
els.payloadFields.addEventListener("change", renderPreview);
els.resetBtn.addEventListener("click", doReset);
els.stepBtn.addEventListener("click", doStep);
els.stateBtn.addEventListener("click", async () => {
  try {
    await fetchState();
  } catch (error) {
    setStatus(`State fetch failed: ${error.message}`, "error");
  }
});

renderTaskOptions();
renderTaskCards();
renderTaskBrief();
renderPayloadFields();
renderPreview();
renderRewardBreakdown(null);
renderSummaryMetrics(null);
setStatus("Loading server state...", "idle");

fetchHealth();
fetchTasks()
  .then(() => fetchState({ silent: true }))
  .then(() => {
    if (!currentObservation) {
      setStatus("Server ready. Reset to start an episode.", "idle");
    }
  })
  .catch(() => {
    setStatus("Server ready. Reset to start an episode.", "idle");
  });
