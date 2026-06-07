import { askAgent } from "./agentClient.js?v=4";
import { buildDailyReport } from "./healthRules.js?v=2";
import { connectLiveKit, disconnectLiveKit, isLiveKitConnected } from "./livekitClient.js?v=1";
import { analyzeCurrentMoment } from "./modelAdapter.js?v=2";
import { createScenarioEvent, createSeedEvents, scenarioTypes } from "./sampleData.js?v=2";

const storageKey = "mochi-monitor-events";

const state = {
  activeTab: "live",
  mediaEnabled: false,
  stream: null,
  events: loadEvents(),
  chat: [
    {
      role: "assistant",
      text: "I will answer using Mochi's timeline only. Start live analysis or load a demo day to give me context."
    }
  ]
};

const elements = {
  tabs: document.querySelectorAll(".tab-button"),
  panels: document.querySelectorAll(".tab-panel"),
  previewVideo: document.querySelector("#previewVideo"),
  videoFallback: document.querySelector("#videoFallback"),
  enableMedia: document.querySelector("#enableMedia"),
  connectLiveKit: document.querySelector("#connectLiveKit"),
  analyzeNow: document.querySelector("#analyzeNow"),
  mediaStatus: document.querySelector("#mediaStatus"),
  mediaMessage: document.querySelector("#mediaMessage"),
  currentStatus: document.querySelector("#currentStatus"),
  riskBadge: document.querySelector("#riskBadge"),
  scenarioButtons: document.querySelector("#scenarioButtons"),
  seedDemo: document.querySelector("#seedDemo"),
  clearTimeline: document.querySelector("#clearTimeline"),
  timeline: document.querySelector("#timeline"),
  chatLog: document.querySelector("#chatLog"),
  chatForm: document.querySelector("#chatForm"),
  chatInput: document.querySelector("#chatInput"),
  promptButtons: document.querySelectorAll(".prompt-button"),
  reportDate: document.querySelector("#reportDate"),
  overallBadge: document.querySelector("#overallBadge"),
  reportSummary: document.querySelector("#reportSummary"),
  metricGrid: document.querySelector("#metricGrid"),
  alertsList: document.querySelector("#alertsList")
};

bindEvents();
renderScenarioButtons();
render();

function bindEvents() {
  elements.tabs.forEach((button) => {
    button.addEventListener("click", () => {
      state.activeTab = button.dataset.tab;
      renderTabs();
    });
  });

  elements.enableMedia.addEventListener("click", startMediaPreview);
  elements.connectLiveKit.addEventListener("click", handleLiveKitToggle);
  elements.analyzeNow.addEventListener("click", handleAnalyze);
  elements.seedDemo.addEventListener("click", () => {
    state.events = createSeedEvents();
    saveEvents();
    render();
  });
  elements.clearTimeline.addEventListener("click", () => {
    state.events = [];
    saveEvents();
    render();
  });

  elements.chatForm.addEventListener("submit", (event) => {
    event.preventDefault();
    handleAsk(elements.chatInput.value);
  });

  elements.promptButtons.forEach((button) => {
    button.addEventListener("click", () => handleAsk(button.textContent));
  });
}

async function startMediaPreview() {
  if (!navigator.mediaDevices?.getUserMedia) {
    elements.mediaMessage.textContent = "This browser does not expose camera/microphone capture. Demo mode is still available.";
    return;
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
    state.stream = stream;
    state.mediaEnabled = true;
    elements.previewVideo.srcObject = stream;
    elements.mediaMessage.textContent = "Live preview is running. Analyze Now will sample the current moment.";
    renderMediaState();
  } catch (error) {
    state.mediaEnabled = false;
    elements.mediaMessage.textContent = "Media permission was not granted. You can still use Analyze Now and demo scenarios.";
    renderMediaState();
  }
}

async function handleLiveKitToggle() {
  if (isLiveKitConnected()) {
    disconnectLiveKit();
    state.mediaEnabled = false;
    elements.connectLiveKit.textContent = "Connect LiveKit";
    elements.mediaMessage.textContent = "Disconnected from LiveKit.";
    renderMediaState();
    return;
  }

  elements.connectLiveKit.disabled = true;
  elements.connectLiveKit.textContent = "Connecting";
  try {
    const session = await connectLiveKit({
      previewVideo: elements.previewVideo,
      statusCallback: (message) => {
        elements.mediaMessage.textContent = message;
      }
    });
    state.mediaEnabled = true;
    elements.connectLiveKit.textContent = "Disconnect";
    elements.mediaMessage.textContent = `LiveKit connected: ${session.room}`;
  } catch (error) {
    elements.connectLiveKit.textContent = "Connect LiveKit";
    elements.mediaMessage.textContent = `${error.message} Add LiveKit env vars to enable room streaming.`;
  } finally {
    elements.connectLiveKit.disabled = false;
    renderMediaState();
  }
}

async function handleAnalyze() {
  elements.analyzeNow.disabled = true;
  elements.analyzeNow.textContent = "Analyzing";
  const event = await analyzeCurrentMoment({
    mediaEnabled: state.mediaEnabled,
    timeline: state.events
  });
  addEvent(event);
  elements.analyzeNow.disabled = false;
  elements.analyzeNow.textContent = "Analyze now";
}

async function handleAsk(question) {
  const cleanQuestion = question.trim();
  if (!cleanQuestion) return;

  const report = buildDailyReport(state.events);
  state.chat.push({ role: "owner", text: cleanQuestion });
  state.chat.push({ role: "assistant", text: "Thinking with MiniMax..." });
  elements.chatInput.value = "";
  renderChat();
  const answer = await askAgent(cleanQuestion, state.events, report);
  state.chat[state.chat.length - 1] = {
    role: "assistant",
    text: answer.text,
    provider: answer.provider
  };
  renderChat();
}

function addEvent(event) {
  state.events = [...state.events, event].slice(-40);
  saveEvents();
  render();
}

function render() {
  renderTabs();
  renderMediaState();
  renderCurrentStatus();
  renderTimeline();
  renderChat();
  renderHealth();
}

function renderTabs() {
  elements.tabs.forEach((button) => {
    button.classList.toggle("active", button.dataset.tab === state.activeTab);
  });
  elements.panels.forEach((panel) => {
    panel.classList.toggle("active", panel.id === state.activeTab);
  });
}

function renderMediaState() {
  elements.mediaStatus.textContent = state.mediaEnabled ? "Media on" : "Media off";
  elements.mediaStatus.classList.toggle("active", state.mediaEnabled);
  elements.videoFallback.classList.toggle("hidden", state.mediaEnabled);
}

function renderScenarioButtons() {
  elements.scenarioButtons.innerHTML = scenarioTypes.map((scenario) => {
    return `<button class="scenario-button" data-scenario="${escapeHtml(scenario.id)}" type="button">${escapeHtml(scenario.label)}</button>`;
  }).join("");

  elements.scenarioButtons.querySelectorAll(".scenario-button").forEach((button) => {
    button.addEventListener("click", () => {
      addEvent(createScenarioEvent(button.dataset.scenario));
    });
  });
}

function renderCurrentStatus() {
  const latest = state.events[state.events.length - 1];
  if (!latest) {
    elements.riskBadge.textContent = "Baseline";
    setRiskClass(elements.riskBadge, "normal");
    elements.currentStatus.innerHTML = `
      <div class="empty-state">
        <h3>No current observation yet</h3>
        <p>Run a live analysis or load a demo day to see model output here.</p>
      </div>
    `;
    return;
  }

  elements.riskBadge.textContent = labelForRisk(latest.riskLevel);
  setRiskClass(elements.riskBadge, latest.riskLevel);
  elements.currentStatus.innerHTML = `
    <div class="state-title">${escapeHtml(latest.state)}</div>
    <div class="confidence-row">
      <span>${Math.round(latest.confidence * 100)}% confidence</span>
      <span>${formatTime(latest.time)}</span>
    </div>
    <div class="confidence-meter"><span style="width:${Math.round(latest.confidence * 100)}%"></span></div>
    <dl class="status-details">
      <div><dt>Intent</dt><dd>${escapeHtml(formatToken(latest.intent))}</dd></div>
      <div><dt>Behavior</dt><dd>${escapeHtml(formatToken(latest.behaviorLabel))}</dd></div>
      <div><dt>Sound</dt><dd>${escapeHtml(formatToken(latest.soundType))}</dd></div>
    </dl>
    <p>${escapeHtml(latest.summary)}</p>
    <div class="suggestion">${escapeHtml(latest.suggestion)}</div>
    ${renderSignalChips(latest.signals)}
  `;
}

function renderTimeline() {
  if (state.events.length === 0) {
    elements.timeline.innerHTML = `
      <div class="empty-state">
        <h3>No timeline events</h3>
        <p>Timeline events become the context for the owner agent and health assistant.</p>
      </div>
    `;
    return;
  }

  elements.timeline.innerHTML = [...state.events].reverse().map((event) => `
    <article class="timeline-item">
      <div class="timeline-meta">
        <span>${formatTime(event.time)}</span>
        <span class="risk-dot ${escapeHtml(event.riskLevel)}"></span>
      </div>
      <h3>${escapeHtml(event.state)}</h3>
      <p>${escapeHtml(event.summary)}</p>
      <div class="timeline-foot">
        <span>${escapeHtml(formatToken(event.behaviorLabel))}</span>
        <span>${Math.round(event.confidence * 100)}%</span>
      </div>
    </article>
  `).join("");
}

function renderChat() {
  elements.chatLog.innerHTML = state.chat.map((message) => `
    <div class="chat-message ${message.role}">
      <span>${message.role === "owner" ? "Owner" : `Agent · ${escapeHtml(message.provider || "local")}`}</span>
      <p>${escapeHtml(message.text)}</p>
    </div>
  `).join("");
  elements.chatLog.scrollTop = elements.chatLog.scrollHeight;
}

function renderHealth() {
  const report = buildDailyReport(state.events);
  elements.reportDate.textContent = report.dateLabel;
  elements.overallBadge.textContent = labelForRisk(report.overall);
  setRiskClass(elements.overallBadge, report.overall);
  elements.reportSummary.textContent = report.summary;

  const metrics = [
    ["Events", report.totalEvents],
    ["Eating", report.counts.eating],
    ["Litter", report.counts.litter],
    ["Active", report.counts.active],
    ["Resting", report.counts.resting],
    ["Vocal", report.counts.vocal]
  ];

  elements.metricGrid.innerHTML = metrics.map(([label, value]) => `
    <div class="metric">
      <span>${escapeHtml(label)}</span>
      <strong>${value}</strong>
    </div>
  `).join("");

  if (report.alerts.length === 0) {
    elements.alertsList.innerHTML = `
      <div class="empty-state">
        <h3>No warnings yet</h3>
        <p>The assistant is building a behavior baseline. This is not a medical diagnosis.</p>
      </div>
    `;
    return;
  }

  elements.alertsList.innerHTML = report.alerts.map((alert) => `
    <article class="alert-card ${escapeHtml(alert.level)}">
      <div class="alert-head">
        <span>${escapeHtml(alert.level)}</span>
        <strong>${Math.round(alert.confidence * 100)}%</strong>
      </div>
      <h3>${escapeHtml(alert.title)}</h3>
      <ul>
        ${alert.evidence.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
      </ul>
      <p>${escapeHtml(alert.suggestion)}</p>
    </article>
  `).join("");
}

function renderSignalChips(signals) {
  if (!signals.length) return `<div class="signal-list"><span>no warning signals</span></div>`;
  return `<div class="signal-list">${signals.map((signal) => `<span>${escapeHtml(formatToken(signal))}</span>`).join("")}</div>`;
}

function setRiskClass(element, risk) {
  element.classList.remove("normal", "watch", "review");
  element.classList.add(risk === "review" ? "review" : risk === "watch" ? "watch" : "normal");
}

function labelForRisk(risk) {
  if (risk === "review") return "Review";
  if (risk === "watch") return "Watch";
  return "Normal";
}

function formatToken(value) {
  return String(value || "unknown").replaceAll("_", " ").replaceAll(".", " / ");
}

function formatTime(value) {
  return new Date(value).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => {
    const entities = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
    return entities[char];
  });
}

function loadEvents() {
  try {
    return JSON.parse(localStorage.getItem(storageKey)) || [];
  } catch {
    return [];
  }
}

function saveEvents() {
  localStorage.setItem(storageKey, JSON.stringify(state.events));
}
