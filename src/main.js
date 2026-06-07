import { askAgent } from "./agentClient.js?v=5";
import { buildDailyReport, buildRangeReport } from "./healthRules.js?v=3";
import { connectLiveKit, disconnectLiveKit, isLiveKitConnected } from "./livekitClient.js?v=1";
import { analyzeUploadedClip } from "./modelAdapter.js?v=4";
const fallbackCatAccents = ["#66d19e", "#e4bd5b", "#76c7d8", "#ef7c73", "#d3c7a3"];

const state = {
  activeTab: "home",
  reportRange: "day",
  activityFilter: "all",
  mediaEnabled: false,
  stream: null,
  uploadedClipUrl: "",
  selectedClipFile: null,
  clipAnalysis: null,
  events: [],
  cats: [],
  scenarios: [],
  chat: [
    {
      role: "assistant",
      provider: "local",
      text: "Ask Beenz about today, any cat's routine, nighttime vocalizations, activity, or whether a pattern is worth watching."
    }
  ]
};

const elements = {
  tabs: document.querySelectorAll(".tab-button"),
  panels: document.querySelectorAll(".tab-panel"),
  previewVideo: document.querySelector("#previewVideo"),
  videoFallback: document.querySelector("#videoFallback"),
  enableMedia: document.querySelector("#enableMedia"),
  uploadMenu: document.querySelector("#uploadMenu"),
  uploadOptions: document.querySelector("#uploadOptions"),
  takeVideoButton: document.querySelector("#takeVideoButton"),
  uploadVideoButton: document.querySelector("#uploadVideoButton"),
  takeVideoUpload: document.querySelector("#takeVideoUpload"),
  uploadVideoUpload: document.querySelector("#uploadVideoUpload"),
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
  homeGreetingLabel: document.querySelector("#homeGreetingLabel"),
  homeGreeting: document.querySelector("#homeGreeting"),
  homeOverallBadge: document.querySelector("#homeOverallBadge"),
  homeSummary: document.querySelector("#homeSummary"),
  homeInsight: document.querySelector("#homeInsight"),
  homeMetricGrid: document.querySelector("#homeMetricGrid"),
  homePreview: document.querySelector("#homePreview"),
  homeCatCount: document.querySelector("#homeCatCount"),
  catRoster: document.querySelector("#catRoster"),
  homeActions: document.querySelectorAll("[data-go-tab]"),
  activityCount: document.querySelector("#activityCount"),
  activitySummary: document.querySelector("#activitySummary"),
  activityRings: document.querySelector("#activityRings"),
  activityMetrics: document.querySelector("#activityMetrics"),
  activityBars: document.querySelector("#activityBars"),
  activityList: document.querySelector("#activityList"),
  filterButtons: document.querySelectorAll(".filter-button"),
  reportDate: document.querySelector("#reportDate"),
  overallBadge: document.querySelector("#overallBadge"),
  reportSummary: document.querySelector("#reportSummary"),
  catReports: document.querySelector("#catReports"),
  metricGrid: document.querySelector("#metricGrid"),
  alertsList: document.querySelector("#alertsList"),
  rangeButtons: document.querySelectorAll(".range-button")
};

bindEvents();
render();
loadAppData();

function bindEvents() {
  elements.tabs.forEach((button) => button.addEventListener("click", () => switchTab(button.dataset.tab)));
  elements.homeActions.forEach((card) => card.addEventListener("click", () => switchTab(card.dataset.goTab)));
  elements.enableMedia.addEventListener("click", startMediaPreview);
  elements.uploadMenu.addEventListener("click", () => {
    elements.uploadOptions.hidden = !elements.uploadOptions.hidden;
  });
  elements.takeVideoButton.addEventListener("click", () => {
    elements.uploadOptions.hidden = true;
    elements.takeVideoUpload.value = "";
    elements.takeVideoUpload.click();
  });
  elements.uploadVideoButton.addEventListener("click", () => {
    elements.uploadOptions.hidden = true;
    elements.uploadVideoUpload.value = "";
    elements.uploadVideoUpload.click();
  });
  elements.takeVideoUpload.addEventListener("change", (event) => {
    handleClipUpload(event.target.files?.[0]);
  });
  elements.uploadVideoUpload.addEventListener("change", (event) => {
    handleClipUpload(event.target.files?.[0]);
  });
  document.addEventListener("click", (event) => {
    const target = event.target;
    if (
      !elements.uploadOptions?.hidden &&
      target &&
      !elements.uploadOptions.contains(target) &&
      !elements.uploadMenu.contains(target)
    ) {
      elements.uploadOptions.hidden = true;
    }
  });
  elements.connectLiveKit.addEventListener("click", handleLiveKitToggle);
  elements.analyzeNow.addEventListener("click", handleAnalyze);
  elements.seedDemo.addEventListener("click", handleSeedDemo);
  elements.clearTimeline.addEventListener("click", handleClearTimeline);
  elements.chatForm.addEventListener("submit", (event) => {
    event.preventDefault();
    handleAsk(elements.chatInput.value);
  });
  elements.promptButtons.forEach((button) => button.addEventListener("click", () => handleAsk(button.textContent)));
  elements.rangeButtons.forEach((button) => button.addEventListener("click", () => {
    state.reportRange = button.dataset.range;
    renderHealth();
  }));
  elements.filterButtons.forEach((button) => button.addEventListener("click", () => {
    state.activityFilter = button.dataset.filter;
    renderActivity();
  }));
}

async function loadAppData() {
  try {
    await loadCats();
    await Promise.all([loadScenarios(), loadEvents()]);
  } catch (error) {
    elements.mediaMessage.textContent = `Data load failed: ${error.message}`;
  } finally {
    render();
  }
}

function normalizeCats(rawCats) {
  return rawCats.map((cat, index) => {
    const name = String(cat?.name || `Cat ${index + 1}`).trim();
    const initial = String(cat?.initials || generateInitials(name)).trim().toUpperCase();
    return {
      id: String(cat?.id || `cat_${index}`).trim().toLowerCase(),
      name,
      initials: initial,
      age: String(cat?.age || "unknown"),
      breed: String(cat?.breed || "Domestic cat"),
      room: String(cat?.room || "Home"),
      routine: String(cat?.routine || "Routine tracking starts with synced timeline events."),
      avatar: String(cat?.avatar || ""),
      accent: String(cat?.accent || fallbackCatAccents[index % fallbackCatAccents.length])
    };
  });
}

function generateInitials(name) {
  const normalized = String(name || "").trim();
  if (!normalized) return "??";
  const parts = normalized.split(/\s+/);
  if (parts.length === 1) return normalized.slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
}

async function requestApiJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || payload?.ok === false) {
    const errorMessage = payload.detail || payload.message || `Request failed with status ${response.status}`;
    throw new Error(errorMessage);
  }
  return payload;
}

async function loadCats() {
  const response = await requestApiJson("/api/cats/public", { method: "GET" });
  const rawCats = Array.isArray(response.cats) ? response.cats : [];
  state.cats = normalizeCats(rawCats);
}

async function loadScenarios() {
  const response = await requestApiJson("/api/events/scenarios", { method: "GET" });
  const rawScenarios = Array.isArray(response.scenarios) ? response.scenarios : [];
  state.scenarios = rawScenarios
    .filter((item) => item?.id && item?.label)
    .map((item) => ({ id: String(item.id), label: String(item.label) }));
}

async function loadEvents() {
  const response = await requestApiJson("/api/events");
  const rawEvents = Array.isArray(response.events) ? response.events : [];
  state.events = rawEvents.map((event, index) => normalizeEventCat(event, index));
}

async function handleSeedDemo() {
  try {
    const response = await requestApiJson("/api/events/seed", { method: "POST" });
    const rawEvents = Array.isArray(response.events) ? response.events : [];
    state.events = rawEvents.map((event, index) => normalizeEventCat(event, index));
    render();
  } catch (error) {
    elements.mediaMessage.textContent = `Failed to seed timeline: ${error.message}`;
  }
}

async function handleClearTimeline() {
  try {
    await requestApiJson("/api/events", { method: "DELETE" });
    state.events = [];
    render();
  } catch (error) {
    elements.mediaMessage.textContent = `Failed to clear timeline: ${error.message}`;
  }
}

function switchTab(tab) {
  state.activeTab = tab;
  renderTabs();
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
  } catch {
    state.mediaEnabled = false;
    elements.mediaMessage.textContent = "Media permission was not granted. Upload or demo scenarios still work.";
  }
  renderMediaState();
}

function handleClipUpload(file) {
  if (!file) return;
  if (!file.type.startsWith("video/")) {
    elements.mediaMessage.textContent = "Please select a video file.";
    return;
  }

  state.selectedClipFile = file;
  elements.mediaMessage.textContent = `${file.name} selected. Analyze clip will send only this file to the model.`;
  state.clipAnalysis = null;
  if (state.uploadedClipUrl) {
    URL.revokeObjectURL(state.uploadedClipUrl);
  }
  state.uploadedClipUrl = URL.createObjectURL(file);
  elements.previewVideo.srcObject = null;
  if (file.type.startsWith("video/")) {
    elements.previewVideo.src = state.uploadedClipUrl;
    elements.previewVideo.controls = true;
    elements.previewVideo.muted = true;
    elements.previewVideo.play().catch(() => {});
  } else {
    elements.previewVideo.removeAttribute("src");
    elements.previewVideo.controls = false;
  }
  renderMediaState();
  renderCurrentStatus();
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
      statusCallback: (message) => { elements.mediaMessage.textContent = message; }
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
  const file = state.selectedClipFile;
  if (!file) {
    elements.mediaMessage.textContent = "Upload a video first. LiveKit timeline analysis will come later.";
    return;
  }

  elements.analyzeNow.disabled = true;
  elements.analyzeNow.textContent = "Analyzing";
  elements.mediaMessage.textContent = "Sending clip to model...";
  try {
    state.clipAnalysis = await analyzeUploadedClip(file);
    elements.mediaMessage.textContent = `Model response received from ${state.clipAnalysis.provider}.`;
  } catch (error) {
    state.clipAnalysis = {
      provider: "error",
      text: error.message,
      file: { name: file.name, type: file.type, size: file.size },
      event: {
        time: new Date().toISOString(),
        state: "Clip analysis failed",
        intent: "unknown",
        behaviorLabel: "unknown",
        soundType: "unknown",
        confidence: 0,
        riskLevel: "watch",
        signals: [],
        summary: error.message,
        suggestion: "Try a shorter clip or check the model endpoint."
      }
    };
    elements.mediaMessage.textContent = "Could not analyze this clip.";
  } finally {
    elements.analyzeNow.disabled = false;
    elements.analyzeNow.textContent = "Analyze clip";
    renderCurrentStatus();
  }
}

async function handleAsk(question) {
  const cleanQuestion = question.trim();
  if (!cleanQuestion) return;
  const report = buildRangeReport(state.events, state.reportRange);
  state.chat.push({ role: "owner", text: cleanQuestion });
  state.chat.push({ role: "assistant", text: "Thinking with MiniMax...", provider: "minimax" });
  elements.chatInput.value = "";
  renderChat();
  const answer = await askAgent(cleanQuestion, state.events, report);
  state.chat[state.chat.length - 1] = { role: "assistant", text: answer.text, provider: answer.provider };
  renderChat();
}

function addEvent(event) {
  const normalized = normalizeEventCat(event);
  state.events = [...state.events, normalized].slice(-80);
  render();
}

async function handleScenarioAdd(type) {
  try {
    const response = await requestApiJson(`/api/events/scenario/${encodeURIComponent(type)}`, { method: "POST" });
    if (response?.event) {
      addEvent(response.event);
    }
  } catch (error) {
    elements.mediaMessage.textContent = `Failed to add scenario: ${error.message}`;
  }
}

function render() {
  renderTabs();
  renderScenarioButtons();
  renderHome();
  renderMediaState();
  renderCurrentStatus();
  renderTimeline();
  renderChat();
  renderActivity();
  renderHealth();
}

function renderTabs() {
  elements.tabs.forEach((button) => button.classList.toggle("active", button.dataset.tab === state.activeTab));
  elements.panels.forEach((panel) => panel.classList.toggle("active", panel.id === state.activeTab));
}

function renderHome() {
  const report = buildDailyReport(state.events);
  const catStates = buildCatHomeState();
  const reportTotalEvents = catStates.reduce((total, cat) => total + cat.report.totalEvents, 0);
  const householdStatus = getHouseholdStatus(catStates);
  const greeting = buildGreeting();
  elements.homeGreetingLabel.textContent = greeting.label;
  elements.homeGreeting.textContent = greeting.text;
  elements.homeOverallBadge.textContent = householdStatus;
  setRiskClass(elements.homeOverallBadge, riskFromCatStatus(householdStatus));
  elements.homeCatCount.textContent = `${catStates.length} cats`;
  elements.homeSummary.textContent = buildHomeBrief(catStates, reportTotalEvents);
  elements.homeInsight.innerHTML = renderInsight(catStates);
  elements.homeMetricGrid.innerHTML = renderHomeStats(report, catStates, householdStatus);
  elements.homePreview.innerHTML = renderCatPreview(catStates);
  elements.catRoster.innerHTML = renderCatRoster(catStates);
}

function buildGreeting() {
  const hour = new Date().getHours();
  if (hour < 12) return { label: "Good morning", text: "Good morning, BingQ." };
  if (hour < 18) return { label: "Good afternoon", text: "Good afternoon, BingQ." };
  return { label: "Good evening", text: "Good evening, BingQ." };
}

function buildHomeBrief(cats, totalEvents) {
  const alertCount = cats.filter((cat) => cat.status === "alert").length;
  const watchCount = cats.filter((cat) => cat.status === "watch").length;
  if (totalEvents === 0) return `${cats.length} cats are set up. Add live observations or load the demo day to build household baseline.`;
  if (alertCount > 0) return `${cats.length} cats checked in. ${alertCount} cat(s) need attention from today's behavior signals.`;
  if (watchCount > 0) return `${cats.length} cats checked in. One or more routines are worth watching, but no immediate health issue is flagged.`;
  return `${cats.length} cats checked in. The household looks steady, with routines close to the current baseline.`;
}

function renderInsight(catStates) {
  const firstAlertCat = catStates.find((cat) => cat.status === "alert");
  if (firstAlertCat) {
    const catAlert = firstAlertCat.report.alerts[0];
    if (catAlert) return `<strong>${escapeHtml(firstAlertCat.name)} needs attention</strong><span>${escapeHtml(catAlert.evidence[0])}</span>`;
  }
  if (catStates.some((cat) => cat.report.totalEvents > 0)) {
    const steady = catStates.find((cat) => cat.status === "perfect") || catStates[0];
    return `<strong>${escapeHtml(steady.name)} looks ${escapeHtml(steady.status)}</strong><span>Rest, food, activity, and vocal signals become stronger as each cat timeline grows.</span>`;
  }
  return `<strong>Build each cat's baseline</strong><span>MeowMeowBeenz works best after a few normal eating, activity, litter, vocal, and rest observations.</span>`;
}

function buildCatHomeState() {
  return state.cats.map((cat) => {
    const report = buildRangeReport(getCatEvents(cat.id), "day");
    return {
      ...cat,
      report,
      status: deriveCatStatus(report),
      lastSeen: getCatLastSeen(cat.id),
      note: getCatStatusNote(report),
      vitals: getCatVitals(report)
    };
  });
}

function deriveCatStatus(report) {
  if (report.totalEvents === 0) return "nice";
  if (report.overall === "review") return "alert";
  if (report.overall === "watch") return "watch";
  return "perfect";
}

function getCatEvents(catId) {
  const normalized = state.events.map((event, index) => normalizeEventCat(event, index));
  return normalized.filter((event) => event.catId === catId).sort((a, b) => new Date(b.time).getTime() - new Date(a.time).getTime());
}

function getCatLastSeen(catId) {
  const latest = getCatEvents(catId)[0];
  if (latest) return `${formatTime(latest.time)} · ${formatToken(latest.behaviorLabel)}`;
  return "No timeline events yet.";
}

function getCatStatusNote(report) {
  if (report.totalEvents === 0) return "Profile ready. Waiting for live or uploaded observations.";
  if (report.overall === "review") return "Needs a closer look. Compare with appetite, litter, and vocal patterns.";
  if (report.overall === "watch") return "A routine changed enough to watch, but the signal is still early.";
  return "Routine is matching the calm baseline in today's timeline.";
}

function getCatVitals(report) {
  return [["Events", report.totalEvents], ["Alerts", Math.min(report.alerts.length, 1)]];
}

function getHouseholdStatus(cats) {
  if (cats.some((cat) => cat.status === "alert")) return "alert";
  if (cats.some((cat) => cat.status === "watch")) return "watch";
  if (cats.every((cat) => cat.status === "perfect")) return "perfect";
  return "nice";
}

function riskFromCatStatus(status) {
  if (status === "alert") return "review";
  if (status === "watch") return "watch";
  return "normal";
}

function renderHomeStats(report, cats, householdStatus) {
  return [
    ["Cats", cats.length],
    ["Household", householdStatus],
    ["Events", report.totalEvents],
    ["Warnings", Math.min(report.alerts.length, 1)]
  ].map(([label, value]) => `<div class="home-stat"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join("");
}

function getCatEventBuckets(events) {
  const normalized = Array.isArray(events) ? events.map((event, index) => normalizeEventCat(event, index)) : [];
  return state.cats.map((cat) => ({
    cat,
    events: normalized.filter((event) => event.catId === cat.id)
  }));
}

function renderActivityGroups(catBuckets) {
  if (!catBuckets.length) {
    return `<div class="empty-state"><h3>No cats to show</h3><p>Load a timeline to see per-cat events.</p></div>`;
  }

  return catBuckets.map(({ cat, events }) => {
    const sortedEvents = [...events].sort((a, b) => new Date(b.time).getTime() - new Date(a.time).getTime());
    const copy = sortedEvents.length === 0 ? "No events match this filter yet." : "No timeline events yet.";
    return `
      <section class="cat-activity-group">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Timeline</p>
            <h2>${escapeHtml(cat.name)}</h2>
          </div>
          <span class="status-pill">${sortedEvents.length} events</span>
        </div>
        <div class="cat-activity-events">${renderEventCards(sortedEvents, copy, cat)}</div>
      </section>
    `;
  }).join("");
}

function renderCatPreview(cats) {
  return cats.map((cat) => `
    <article class="cat-preview-row">
      ${renderCatAvatar(cat)}
      <div>
        <strong>${escapeHtml(cat.name)}</strong>
        <span>${escapeHtml(cat.lastSeen)}</span>
      </div>
      ${renderCatStatus(cat.status)}
    </article>
  `).join("");
}

function renderCatRoster(cats) {
  return cats.map((cat) => `
    <article class="cat-card ${escapeHtml(cat.status)}">
      <div class="cat-card-top">
        ${renderCatAvatar(cat)}
        ${renderCatStatus(cat.status)}
      </div>
      <h3>${escapeHtml(cat.name)}</h3>
      <p>${escapeHtml(cat.breed)} · ${escapeHtml(cat.age)}</p>
      <dl class="cat-facts">
        <div><dt>Room</dt><dd>${escapeHtml(cat.room)}</dd></div>
        <div><dt>Routine</dt><dd>${escapeHtml(cat.routine)}</dd></div>
      </dl>
      <div class="cat-vitals">${cat.vitals.map(([label, value]) => `<span><b>${escapeHtml(value)}</b>${escapeHtml(label)}</span>`).join("")}</div>
      <p class="cat-note">${escapeHtml(cat.note)}</p>
    </article>
  `).join("");
}

function renderCatAvatar(cat) {
  if (cat.avatar) {
    return `<div class="cat-avatar" style="--cat-accent:${escapeHtml(cat.accent)}"><img src="${escapeHtml(cat.avatar)}" alt="${escapeHtml(cat.name)} profile photo" onerror="this.parentElement.classList.add('no-avatar'); this.remove()" /><span>${escapeHtml(cat.initials)}</span></div>`;
  }
  return `<div class="cat-avatar" style="--cat-accent:${escapeHtml(cat.accent)}"><span>${escapeHtml(cat.initials)}</span></div>`;
}

function renderCatStatus(status) {
  return `<span class="cat-status ${escapeHtml(status)}">${escapeHtml(status)}</span>`;
}

function renderMediaState() {
  const file = state.selectedClipFile;
  const hasVideoClip = Boolean(file?.type.startsWith("video/"));
  elements.mediaStatus.textContent = file ? "Clip ready" : state.mediaEnabled ? "Media on" : "Media off";
  elements.mediaStatus.classList.toggle("active", state.mediaEnabled || Boolean(file));
  elements.videoFallback.classList.toggle("hidden", state.mediaEnabled || hasVideoClip);
  if (!state.mediaEnabled && !hasVideoClip) {
    elements.videoFallback.querySelector("p").textContent = file ? "Video selected" : "Camera preview appears here";
  }
}

function renderScenarioButtons() {
  if (!state.scenarios.length) {
    elements.scenarioButtons.innerHTML = "";
    return;
  }
  elements.scenarioButtons.innerHTML = state.scenarios
    .map((scenario) => `<button class="scenario-button" data-scenario="${escapeHtml(scenario.id)}" type="button">${escapeHtml(scenario.label)}</button>`)
    .join("");
  elements.scenarioButtons.querySelectorAll(".scenario-button").forEach((button) => {
    button.addEventListener("click", () => handleScenarioAdd(button.dataset.scenario));
  });
}

function renderCurrentStatus() {
  if (state.clipAnalysis) {
    const event = state.clipAnalysis.event;
    elements.riskBadge.textContent = labelForRisk(event.riskLevel);
    setRiskClass(elements.riskBadge, event.riskLevel);
    elements.currentStatus.innerHTML = renderStatusObservation(event, state.clipAnalysis);
    return;
  }

  const latest = state.events[state.events.length - 1];
  if (!latest) {
    elements.riskBadge.textContent = "Baseline";
    setRiskClass(elements.riskBadge, "normal");
    elements.currentStatus.innerHTML = `<div class="empty-state"><h3>No clip analysis yet</h3><p>Upload a video, then run Analyze clip to see the model response here.</p></div>`;
    return;
  }
  elements.riskBadge.textContent = labelForRisk(latest.riskLevel);
  setRiskClass(elements.riskBadge, latest.riskLevel);
  elements.currentStatus.innerHTML = renderStatusObservation(latest);
}

function renderStatusObservation(event, analysis = null) {
  return `
    <div class="state-title">${escapeHtml(event.state)}</div>
    <div class="confidence-row"><span>${Math.round(event.confidence * 100)}% confidence</span><span>${formatTime(event.time)}</span></div>
    <div class="confidence-meter"><span style="width:${Math.round(event.confidence * 100)}%"></span></div>
    <dl class="status-details">
      <div><dt>Intent</dt><dd>${escapeHtml(formatToken(event.intent))}</dd></div>
      <div><dt>Behavior</dt><dd>${escapeHtml(formatToken(event.behaviorLabel))}</dd></div>
      <div><dt>Sound</dt><dd>${escapeHtml(formatToken(event.soundType))}</dd></div>
    </dl>
    ${analysis ? renderModelResponse(analysis) : ""}
    <p>${escapeHtml(event.summary)}</p><div class="suggestion">${escapeHtml(event.suggestion)}</div>${renderSignalChips(event.signals)}
  `;
}

function renderModelResponse(analysis) {
  const fileName = analysis.file?.name || "uploaded clip";
  return `
    <div class="model-response">
      <span>Model response · ${escapeHtml(analysis.provider)}</span>
      <strong>${escapeHtml(fileName)}</strong>
      <p>${escapeHtml(analysis.text)}</p>
    </div>
  `;
}

function renderTimeline() {
  elements.timeline.innerHTML = renderEventCards(state.events, "Timeline events become context for Agent, Activity, and Health.");
}

function renderChat() {
  elements.chatLog.innerHTML = state.chat.map((message) => `
    <div class="chat-message ${escapeHtml(message.role)}"><span>${message.role === "owner" ? "Owner" : `Agent · ${escapeHtml(message.provider || "local")}`}</span><p>${escapeHtml(message.text)}</p></div>
  `).join("");
  elements.chatLog.scrollTop = elements.chatLog.scrollHeight;
}

function renderActivity() {
  const events = filterEvents(state.events, state.activityFilter);
  const report = buildDailyReport(state.events);
  const watch = buildWatchMetrics(report);
  elements.filterButtons.forEach((button) => button.classList.toggle("active", button.dataset.filter === state.activityFilter));
  const catBuckets = getCatEventBuckets(events);
  const totalCatsWithEvents = catBuckets.filter((bucket) => bucket.events.length > 0).length;
  elements.activityCount.textContent = `${events.length} events · ${totalCatsWithEvents} cats`;
  elements.activitySummary.textContent = buildActivitySummary(report, watch);
  elements.activityRings.innerHTML = renderActivityRings(watch);
  elements.activityMetrics.innerHTML = renderWatchMetricCards(watch);
  elements.activityBars.innerHTML = renderActivityBars(report.counts);
  elements.activityList.innerHTML = renderActivityGroups(catBuckets);
}

function buildWatchMetrics(report) {
  const activeGoal = 4;
  const restGoal = 5;
  const routineGoal = 3;
  const activeScore = clampScore((report.counts.active / activeGoal) * 100);
  const restScore = clampScore((report.counts.resting / restGoal) * 100);
  const routineScore = clampScore(((report.counts.eating + report.counts.litter + Math.min(report.counts.vocal, 1)) / routineGoal) * 100);
  const quietScore = clampScore(100 - Math.max(0, report.counts.vocal - 1) * 28 - report.counts.review * 18);
  const readiness = Math.round((activeScore * 0.25) + (restScore * 0.25) + (routineScore * 0.25) + (quietScore * 0.25));
  return { activeScore, restScore, routineScore, quietScore, readiness, counts: report.counts };
}

function buildActivitySummary(report, watch) {
  if (report.totalEvents === 0) return "No rhythm yet. Load a demo day or analyze a clip to see activity, rest, routine, and nighttime noise scores.";
  if (watch.quietScore < 55) return "Night noise is the weak spot today. Activity and rest still matter, but repeated vocal events are worth comparing against normal nights.";
  if (watch.restScore >= 70 && watch.quietScore >= 70) return "Rest quality looks solid, with a calmer sleep window and limited disruption in the recorded timeline.";
  if (watch.activeScore < 35) return "Activity is low compared with the demo goal. Watch whether this is just a quiet day or a pattern that repeats.";
  return "Beenz mapped today's rhythm like a wearable: activity, rest, routine, and nighttime noise are all updating from the timeline.";
}

function renderActivityRings(watch) {
  return [
    ["Readiness", watch.readiness, "Overall balance"],
    ["Activity", watch.activeScore, "Movement goal"],
    ["Rest", watch.restScore, "Sleep/rest quality"],
    ["Quiet", watch.quietScore, "Night noise"],
  ].map(([label, score, caption]) => renderRing(label, score, caption)).join("");
}

function renderRing(label, score, caption) {
  const angle = Math.max(0, Math.min(100, score)) * 3.6;
  return `<article class="watch-ring" style="--ring:${angle}deg"><div class="ring-face"><strong>${Math.round(score)}</strong><span>${escapeHtml(label)}</span></div><p>${escapeHtml(caption)}</p></article>`;
}

function renderWatchMetricCards(watch) {
  return [
    ["Active events", watch.counts.active, "walk/play/climb"],
    ["Rest blocks", watch.counts.resting, "sleep/rest windows"],
    ["Routine hits", watch.counts.eating + watch.counts.litter, "food + litter"],
    ["Night noise", watch.counts.vocal, "meow/yowl/chirp"],
  ].map(([label, value, helper]) => `<div class="watch-metric"><span>${escapeHtml(label)}</span><strong>${value}</strong><em>${escapeHtml(helper)}</em></div>`).join("");
}

function clampScore(value) {
  return Math.round(Math.max(0, Math.min(100, value)));
}

function renderActivityBars(counts) {
  const entries = [["Active", counts.active], ["Rest", counts.resting], ["Food", counts.eating], ["Litter", counts.litter], ["Vocal", counts.vocal]];
  const max = Math.max(1, ...entries.map(([, value]) => value));
  return entries.map(([label, value]) => `<div class="activity-bar"><span>${label}</span><div><i style="width:${(value / max) * 100}%"></i></div><strong>${value}</strong></div>`).join("");
}

function renderHealth() {
  const report = buildRangeReport(state.events, state.reportRange);
  const catReports = state.cats.map((cat) => ({
    ...cat,
    report: buildRangeReport(getCatEvents(cat.id), state.reportRange)
  }));
  elements.rangeButtons.forEach((button) => button.classList.toggle("active", button.dataset.range === state.reportRange));
  elements.reportDate.textContent = report.dateLabel;
  elements.overallBadge.textContent = labelForRisk(report.overall);
  setRiskClass(elements.overallBadge, report.overall);
  elements.reportSummary.textContent = report.summary;
  elements.metricGrid.innerHTML = renderMetrics([["Events", report.totalEvents], ["Eating", report.counts.eating], ["Litter", report.counts.litter], ["Active", report.counts.active], ["Resting", report.counts.resting], ["Vocal", report.counts.vocal]]);
  if (catReports.length) {
    elements.catReports.innerHTML = renderCatReports(catReports);
  } else {
    elements.catReports.innerHTML = `<div class="empty-state"><h3>No cat reports yet</h3><p>Load the demo day or add live events to create per-cat reports.</p></div>`;
  }
  if (report.alerts.length === 0) {
    elements.alertsList.innerHTML = `<div class="empty-state"><h3>No warnings yet</h3><p>The assistant is building a behavior baseline. This is not a medical diagnosis.</p></div>`;
    return;
  }
  elements.alertsList.innerHTML = report.alerts.map((alert) => `
    <article class="alert-card ${escapeHtml(alert.level)}"><div class="alert-head"><span>${escapeHtml(alert.level)}</span><strong>${Math.round(alert.confidence * 100)}%</strong></div><h3>${escapeHtml(alert.title)}</h3><ul>${alert.evidence.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul><p>${escapeHtml(alert.suggestion)}</p></article>
  `).join("");
}

function renderCatReports(catReports) {
  return catReports.map((catReport) => {
    const { name, report, accent, avatar, initials, id } = catReport;
    return `
    <article class="cat-report-card" style="--cat-accent:${escapeHtml(accent)}">
      <div class="cat-report-head">
        ${renderCatAvatar({ id, name, initials, accent, avatar })}
        <div>
          <p class="eyebrow">Cat report</p>
          <h3>${escapeHtml(name)} · ${escapeHtml(report.dateLabel)}</h3>
        </div>
        <span class="risk-badge ${escapeHtml(report.overall === "review" ? "review" : report.overall === "watch" ? "watch" : "normal")}">${labelForRisk(report.overall)}</span>
      </div>
      <p>${escapeHtml(report.summary)}</p>
      <div class="cat-report-metrics">${renderMetrics([["Events", report.totalEvents], ["Eating", report.counts.eating], ["Litter", report.counts.litter], ["Active", report.counts.active], ["Resting", report.counts.resting], ["Vocal", report.counts.vocal]])}</div>
      ${report.alerts.length === 0 ? `<p class="cat-report-empty">No warnings for this cat.</p>` : `<ul class="cat-report-alerts">${report.alerts.map((alert) => `<li><strong>${escapeHtml(alert.title)}</strong> — ${escapeHtml(alert.evidence[0])}</li>`).join("")}</ul>`}
    </article>
  `;}).join("");
}

function renderMetrics(metrics) {
  return metrics.map(([label, value]) => `<div class="metric"><span>${escapeHtml(label)}</span><strong>${value}</strong></div>`).join("");
}

function renderEventCards(events, emptyCopy, cat = null) {
  if (events.length === 0) return `<div class="empty-state"><h3>No timeline events</h3><p>${escapeHtml(emptyCopy)}</p></div>`;
  return [...events].sort((a, b) => new Date(b.time).getTime() - new Date(a.time).getTime()).map((event) => `
    <article class="timeline-item"><div class="timeline-meta"><span>${formatTime(event.time)}</span><span class="risk-dot ${escapeHtml(event.riskLevel)}"></span></div>${cat ? `<div class="timeline-cat">Tagged: ${escapeHtml(cat.name)}</div>` : ""}<h3>${escapeHtml(event.state)}</h3><p>${escapeHtml(event.summary)}</p><div class="timeline-foot"><span>${escapeHtml(formatToken(event.behaviorLabel))}</span><span>${Math.round(event.confidence * 100)}%</span></div></article>
  `).join("");
}

function filterEvents(events, filter) {
  if (filter === "all") return events;
  return events.filter((event) => {
    const label = event.behaviorLabel || "";
    const sound = event.soundType || "";
    if (filter === "active") return isActiveLabel(label);
    if (filter === "eating") return label.includes("eating") || label.includes("nutrition");
    if (filter === "litter") return label.includes("littering");
    if (filter === "vocal") return /meow|yowl|caterwaul|chirp/.test(sound);
    if (filter === "warning") return event.riskLevel !== "normal" || event.signals.length > 0;
    return true;
  });
}

function isActiveLabel(label) {
  if (label.includes("inactive")) return false;
  return /active|walking|jumping|climbing|play/.test(label);
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
  return String(value).replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
}

function normalizeEventCat(event, fallbackIndex = 0) {
  if (!event || typeof event !== "object") {
    return {
      catId: state.cats[0]?.id || "cat_0",
      time: new Date().toISOString()
    };
  }

  const rawCatId = String(event.catId || "").trim().toLowerCase();
  const safeEvent = {
    id: String(event.id || `evt_${Date.now()}_${Math.random().toString(16).slice(2)}`),
    catId: rawCatId,
    time: new Date(event.time || Date.now()).toISOString(),
    source: String(event.source || "api"),
    state: String(event.state || "Unknown state"),
    intent: String(event.intent || "unknown"),
    behaviorLabel: String(event.behaviorLabel || "unknown"),
    soundType: String(event.soundType || "unknown"),
    confidence: Number(event.confidence || 0),
    riskLevel: String(event.riskLevel || "normal"),
    signals: Array.isArray(event.signals) ? event.signals.map((item) => String(item)) : [],
    summary: String(event.summary || "The model returned an uncertain observation."),
    suggestion: String(event.suggestion || "Keep observing and add context.")
  };

  if (isKnownCatId(rawCatId)) return { ...safeEvent, catId: rawCatId };
  return { ...safeEvent, catId: pickFallbackCatId(event, fallbackIndex) };
}

function isKnownCatId(id) {
  if (typeof id !== "string") return false;
  if (!state.cats.length) return id.trim().length > 0;
  return state.cats.some((cat) => cat.id === id.trim().toLowerCase());
}

function pickFallbackCatId(event, fallbackIndex = 0) {
  if (!state.cats.length) return "cat_unknown";
  const key = `${fallbackIndex}-${event.id || ""}-${event.time || ""}-${event.state || ""}`;
  let hash = 0;
  for (let i = 0; i < key.length; i++) {
    hash = (hash * 31 + key.charCodeAt(i)) >>> 0;
  }
  return state.cats[hash % state.cats.length].id;
}
