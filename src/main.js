import { askAgent } from "./agentClient.js?v=5";
import { buildDailyReport, buildRangeReport } from "./healthRules.js?v=3";
import { connectLiveKit, disconnectLiveKit, isLiveKitConnected } from "./livekitClient.js?v=1";
import { analyzeUploadedClip } from "./modelAdapter.js?v=4";
import { createScenarioEvent, createSeedEvents, scenarioTypes } from "./sampleData.js?v=2";

const storageKey = "meowmeowbeenz-events";

const catProfiles = [
  {
    id: "mochi",
    name: "Mochi",
    initials: "Mo",
    age: "3 yrs",
    breed: "Domestic shorthair",
    room: "Living room",
    routine: "Breakfast, couch naps, window watch",
    accent: "#66d19e"
  },
  {
    id: "miso",
    name: "Miso",
    initials: "Mi",
    age: "5 yrs",
    breed: "Tabby mix",
    room: "Bedroom",
    routine: "Long sleep blocks, quiet grooming",
    accent: "#e4bd5b"
  },
  {
    id: "bean",
    name: "Bean",
    initials: "Be",
    age: "1 yr",
    breed: "Tuxedo",
    room: "Kitchen",
    routine: "Play bursts, snack patrol, chirps",
    accent: "#76c7d8"
  }
];

const state = {
  activeTab: "home",
  reportRange: "day",
  activityFilter: "all",
  mediaEnabled: false,
  stream: null,
  uploadedClipUrl: "",
  clipAnalysis: null,
  events: loadEvents(),
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
  clipUpload: document.querySelector("#clipUpload"),
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
  metricGrid: document.querySelector("#metricGrid"),
  alertsList: document.querySelector("#alertsList"),
  rangeButtons: document.querySelectorAll(".range-button")
};

bindEvents();
renderScenarioButtons();
render();

function bindEvents() {
  elements.tabs.forEach((button) => button.addEventListener("click", () => switchTab(button.dataset.tab)));
  elements.homeActions.forEach((card) => card.addEventListener("click", () => switchTab(card.dataset.goTab)));
  elements.enableMedia.addEventListener("click", startMediaPreview);
  elements.clipUpload.addEventListener("change", handleClipUpload);
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

function handleClipUpload() {
  const file = elements.clipUpload.files?.[0];
  if (!file) return;
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
  elements.mediaMessage.textContent = `${file.name} selected. Analyze clip will send only this file to the model.`;
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
  const file = elements.clipUpload.files?.[0];
  if (!file) {
    elements.mediaMessage.textContent = "Upload a clip first. LiveKit timeline analysis will come later.";
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
  state.events = [...state.events, event].slice(-80);
  saveEvents();
  render();
}

function render() {
  renderTabs();
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
  const cats = buildCatHomeState(report);
  const householdStatus = getHouseholdStatus(cats);
  const greeting = buildGreeting();
  elements.homeGreetingLabel.textContent = greeting.label;
  elements.homeGreeting.textContent = greeting.text;
  elements.homeOverallBadge.textContent = householdStatus;
  setRiskClass(elements.homeOverallBadge, riskFromCatStatus(householdStatus));
  elements.homeCatCount.textContent = `${cats.length} cats`;
  elements.homeSummary.textContent = buildHomeBrief(report, cats);
  elements.homeInsight.innerHTML = renderInsight(report, cats);
  elements.homeMetricGrid.innerHTML = renderHomeStats(report, cats, householdStatus);
  elements.homePreview.innerHTML = renderCatPreview(cats);
  elements.catRoster.innerHTML = renderCatRoster(cats);
}

function buildGreeting() {
  const hour = new Date().getHours();
  if (hour < 12) return { label: "Good morning", text: "Good morning, BingQ." };
  if (hour < 18) return { label: "Good afternoon", text: "Good afternoon, BingQ." };
  return { label: "Good evening", text: "Good evening, BingQ." };
}

function buildHomeBrief(report, cats) {
  const alertCount = cats.filter((cat) => cat.status === "alert").length;
  const watchCount = cats.filter((cat) => cat.status === "watch").length;
  if (report.totalEvents === 0) return `${cats.length} cats are set up. Add live observations or load the demo day to turn this into a real household check-in.`;
  if (alertCount > 0) return `${cats.length} cats checked in. One cat needs attention from today's behavior signals; the rest are kept in watch or normal status.`;
  if (watchCount > 0) return `${cats.length} cats checked in. One routine is worth watching, but there is not enough signal to call it a health issue.`;
  return `${cats.length} cats checked in. The household looks steady, with routines close to the recorded baseline.`;
}

function renderInsight(report, cats) {
  const alert = report.alerts[0];
  if (alert) {
    return `<strong>${escapeHtml(alert.title)}</strong><span>${escapeHtml(alert.evidence[0])}</span>`;
  }
  if (report.totalEvents > 0) {
    const best = cats.find((cat) => cat.status === "perfect") || cats[0];
    return `<strong>${escapeHtml(best.name)} looks ${escapeHtml(best.status)}</strong><span>Rest, food, activity, and vocalization signals will become stronger as the timeline grows.</span>`;
  }
  return `<strong>Build each cat's baseline</strong><span>MeowMeowBeenz works best after a few normal eating, activity, litter, vocal, and sleep observations.</span>`;
}

function buildCatHomeState(report) {
  const statuses = deriveCatStatuses(report);
  return catProfiles.map((cat, index) => ({
    ...cat,
    status: statuses[index],
    lastSeen: getCatLastSeen(cat, index, report),
    note: getCatStatusNote(cat, statuses[index], report),
    vitals: getCatVitals(cat, index, report)
  }));
}

function deriveCatStatuses(report) {
  const mochi = report.overall === "review" ? "alert" : report.overall === "watch" ? "watch" : report.totalEvents > 0 ? "perfect" : "nice";
  const miso = report.counts.resting >= 3 && report.counts.vocal <= 1 ? "perfect" : report.counts.active === 0 && report.totalEvents > 2 ? "watch" : "nice";
  const bean = report.counts.vocal >= 3 || report.counts.review > 0 ? "alert" : report.counts.active >= 2 ? "perfect" : "nice";
  return keepOneAlert([mochi, miso, bean]);
}

function keepOneAlert(statuses) {
  const firstAlertIndex = statuses.findIndex((status) => status === "alert");
  if (firstAlertIndex === -1) return statuses;
  return statuses.map((status, index) => (status === "alert" && index !== firstAlertIndex ? "watch" : status));
}

function getCatLastSeen(cat, index, report) {
  const latest = state.events[state.events.length - 1];
  if (index === 0 && latest) return `${formatTime(latest.time)} · ${formatToken(latest.behaviorLabel)}`;
  if (cat.id === "miso" && report.counts.resting > 0) return "Last rest block logged today";
  if (cat.id === "bean" && report.counts.active > 0) return "Active burst logged today";
  return cat.room;
}

function getCatStatusNote(cat, status, report) {
  if (status === "alert") return "Needs a closer look. Compare this with appetite, litter, and vocal patterns.";
  if (status === "watch") return "A routine changed enough to watch, but the signal is still early.";
  if (status === "perfect") return "Routine is matching the calm baseline in today's timeline.";
  if (report.totalEvents === 0) return "Profile ready. Waiting for live or uploaded observations.";
  return "No clear concern from current household signals.";
}

function getCatVitals(cat, index, report) {
  if (index === 0) return [["Events", report.totalEvents], ["Alerts", Math.min(report.alerts.length, 1)]];
  if (cat.id === "miso") return [["Rest", report.counts.resting], ["Groom", report.counts.grooming || 0]];
  return [["Active", report.counts.active], ["Vocal", report.counts.vocal]];
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
  return `<div class="cat-avatar" style="--cat-accent:${escapeHtml(cat.accent)}"><span>${escapeHtml(cat.initials)}</span></div>`;
}

function renderCatStatus(status) {
  return `<span class="cat-status ${escapeHtml(status)}">${escapeHtml(status)}</span>`;
}

function renderMediaState() {
  const file = elements.clipUpload.files?.[0];
  const hasVideoClip = Boolean(file?.type.startsWith("video/"));
  elements.mediaStatus.textContent = file ? "Clip ready" : state.mediaEnabled ? "Media on" : "Media off";
  elements.mediaStatus.classList.toggle("active", state.mediaEnabled || Boolean(file));
  elements.videoFallback.classList.toggle("hidden", state.mediaEnabled || hasVideoClip);
  if (!state.mediaEnabled && !hasVideoClip) {
    elements.videoFallback.querySelector("p").textContent = file ? "Audio clip selected" : "Camera preview appears here";
  }
}

function renderScenarioButtons() {
  elements.scenarioButtons.innerHTML = scenarioTypes.map((scenario) => `<button class="scenario-button" data-scenario="${escapeHtml(scenario.id)}" type="button">${escapeHtml(scenario.label)}</button>`).join("");
  elements.scenarioButtons.querySelectorAll(".scenario-button").forEach((button) => button.addEventListener("click", () => addEvent(createScenarioEvent(button.dataset.scenario))));
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
    elements.currentStatus.innerHTML = `<div class="empty-state"><h3>No clip analysis yet</h3><p>Upload a video or audio clip, then run Analyze clip to see the model response here.</p></div>`;
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
  elements.activityCount.textContent = `${events.length} events`;
  elements.activitySummary.textContent = buildActivitySummary(report, watch);
  elements.activityRings.innerHTML = renderActivityRings(watch);
  elements.activityMetrics.innerHTML = renderWatchMetricCards(watch);
  elements.activityBars.innerHTML = renderActivityBars(report.counts);
  elements.activityList.innerHTML = renderEventCards(events, "No events match this filter yet.");
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
  elements.rangeButtons.forEach((button) => button.classList.toggle("active", button.dataset.range === state.reportRange));
  elements.reportDate.textContent = report.dateLabel;
  elements.overallBadge.textContent = labelForRisk(report.overall);
  setRiskClass(elements.overallBadge, report.overall);
  elements.reportSummary.textContent = report.summary;
  elements.metricGrid.innerHTML = renderMetrics([["Events", report.totalEvents], ["Eating", report.counts.eating], ["Litter", report.counts.litter], ["Active", report.counts.active], ["Resting", report.counts.resting], ["Vocal", report.counts.vocal]]);
  if (report.alerts.length === 0) {
    elements.alertsList.innerHTML = `<div class="empty-state"><h3>No warnings yet</h3><p>The assistant is building a behavior baseline. This is not a medical diagnosis.</p></div>`;
    return;
  }
  elements.alertsList.innerHTML = report.alerts.map((alert) => `
    <article class="alert-card ${escapeHtml(alert.level)}"><div class="alert-head"><span>${escapeHtml(alert.level)}</span><strong>${Math.round(alert.confidence * 100)}%</strong></div><h3>${escapeHtml(alert.title)}</h3><ul>${alert.evidence.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul><p>${escapeHtml(alert.suggestion)}</p></article>
  `).join("");
}

function renderMetrics(metrics) {
  return metrics.map(([label, value]) => `<div class="metric"><span>${escapeHtml(label)}</span><strong>${value}</strong></div>`).join("");
}

function renderEventCards(events, emptyCopy) {
  if (events.length === 0) return `<div class="empty-state"><h3>No timeline events</h3><p>${escapeHtml(emptyCopy)}</p></div>`;
  return [...events].reverse().map((event) => `
    <article class="timeline-item"><div class="timeline-meta"><span>${formatTime(event.time)}</span><span class="risk-dot ${escapeHtml(event.riskLevel)}"></span></div><h3>${escapeHtml(event.state)}</h3><p>${escapeHtml(event.summary)}</p><div class="timeline-foot"><span>${escapeHtml(formatToken(event.behaviorLabel))}</span><span>${Math.round(event.confidence * 100)}%</span></div></article>
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

function loadEvents() {
  try {
    const current = JSON.parse(localStorage.getItem(storageKey));
    if (current) return current;
    return JSON.parse(localStorage.getItem("mochi-monitor-events")) || [];
  } catch {
    return [];
  }
}

function saveEvents() {
  localStorage.setItem(storageKey, JSON.stringify(state.events));
}
