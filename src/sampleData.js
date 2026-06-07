const scenarioCatalog = {
  live: {
    state: "Alert and vocal",
    intent: "attention_or_food_seeking",
    behaviorLabel: "active_walking",
    soundType: "repeated_meow",
    confidence: 0.74,
    riskLevel: "normal",
    signals: ["unusual_vocalization"],
    summary: "The cat is active and producing repeated meows, which often points to attention or food seeking.",
    suggestion: "Check the usual routine first: food, water, door access, and recent play time."
  },
  lowActivity: {
    state: "Extended resting",
    intent: "resting_or_low_energy",
    behaviorLabel: "inactive_lying.resting",
    soundType: "quiet",
    confidence: 0.82,
    riskLevel: "watch",
    signals: ["low_activity_alert"],
    summary: "The cat has stayed in a resting posture with little movement compared with active periods.",
    suggestion: "Watch appetite and litter behavior. If low activity persists, consider a vet check-in."
  },
  nightYowl: {
    state: "Night vocalization",
    intent: "attention_or_discomfort",
    behaviorLabel: "inactive_lying.crouch",
    soundType: "caterwauling",
    confidence: 0.69,
    riskLevel: "watch",
    signals: ["unusual_vocalization"],
    summary: "A high-intensity nighttime vocalization was detected while the cat appeared inactive.",
    suggestion: "Check for immediate needs and monitor whether this repeats tonight."
  },
  litterConcern: {
    state: "Repeated litter activity",
    intent: "litter_box_attempt",
    behaviorLabel: "maintenance_littering.digging",
    soundType: "short_meow",
    confidence: 0.77,
    riskLevel: "watch",
    signals: ["possible_litter_box_issue"],
    summary: "The cat appears to be repeatedly digging or visiting the litter area without a clear output event.",
    suggestion: "Check the litter box and monitor for urination or defecation events."
  },
  appetiteGap: {
    state: "Food solicitation without eating",
    intent: "food_seeking",
    behaviorLabel: "active_rubbing",
    soundType: "repeated_meow",
    confidence: 0.71,
    riskLevel: "watch",
    signals: ["possible_appetite_change"],
    summary: "The cat vocalized near a routine feeding context, but no eating event has been logged.",
    suggestion: "Check food and water. If appetite remains low for 24 hours, consider contacting a vet."
  },
  grooming: {
    state: "Focused grooming",
    intent: "self_grooming_or_irritation",
    behaviorLabel: "maintenance_scratching",
    soundType: "quiet",
    confidence: 0.73,
    riskLevel: "watch",
    signals: ["possible_skin_ear_discomfort"],
    summary: "Repeated scratching or focused grooming was detected.",
    suggestion: "Inspect the skin and ears if this repeats or appears intense."
  },
  conflict: {
    state: "Resting with distress-like audio",
    intent: "ambiguous_discomfort",
    behaviorLabel: "inactive_lying.resting",
    soundType: "distress_like_yowl",
    confidence: 0.58,
    riskLevel: "review",
    signals: ["multimodal_conflict", "unusual_vocalization"],
    summary: "Video suggests resting, but the vocal pattern sounds distress-like. The signals do not fully agree.",
    suggestion: "Review the clip and check for visible discomfort before drawing conclusions."
  },
  eating: {
    state: "Eating detected",
    intent: "nutrition",
    behaviorLabel: "maintenance_nutrition.eating",
    soundType: "quiet",
    confidence: 0.86,
    riskLevel: "normal",
    signals: [],
    summary: "The cat appears to be eating with a steady posture and low vocal activity.",
    suggestion: "Log this as a normal appetite signal."
  },
  play: {
    state: "Playful movement",
    intent: "play_or_social_engagement",
    behaviorLabel: "active_playfight.playing",
    soundType: "chirp",
    confidence: 0.79,
    riskLevel: "normal",
    signals: [],
    summary: "This looks like a normal enrichment or social play moment.",
    suggestion: "This looks like a normal enrichment or social play moment."
  }
};

const scenarioToCat = {
  live: "luna",
  lowActivity: "milo",
  nightYowl: "saffron",
  litterConcern: "milo",
  appetiteGap: "luna",
  grooming: "saffron",
  conflict: "milo",
  eating: "luna",
  play: "milo"
};

export function createScenarioEvent(type = "live", catId = null) {
  const scenario = scenarioCatalog[type] || scenarioCatalog.live;
  const assignedCat = catId || scenarioToCat[type] || scenarioToCat.live;
  return normalizeEvent({
    ...scenario,
    catId: assignedCat,
    source: type === "live" ? "live_capture" : "demo_scenario"
  });
}

export function createSeedEvents() {
  const now = new Date();
  const seed = [
    { type: "eating", minutesAgo: 520, catId: "luna" },
    { type: "play", minutesAgo: 410, catId: "milo" },
    { type: "lowActivity", minutesAgo: 180, catId: "milo" },
    { type: "nightYowl", minutesAgo: 45, catId: "saffron" },
    { type: "conflict", minutesAgo: 16, catId: "milo" }
  ];

  return seed.map((item) => {
    const event = createScenarioEvent(item.type, item.catId);
    const time = new Date(now.getTime() - item.minutesAgo * 60 * 1000);
    return { ...event, time: time.toISOString() };
  });
}

export function normalizeEvent(input) {
  const catId = typeof input.catId === "string" && input.catId.trim() ? input.catId : "luna";
  return {
    id: `evt_${Date.now()}_${Math.random().toString(16).slice(2)}`,
    catId,
    time: new Date().toISOString(),
    source: input.source || "live_capture",
    state: input.state || "Unknown state",
    intent: input.intent || "unknown",
    behaviorLabel: input.behaviorLabel || "unknown",
    soundType: input.soundType || "unknown",
    confidence: Number(input.confidence || 0),
    riskLevel: input.riskLevel || "normal",
    signals: Array.isArray(input.signals) ? input.signals : [],
    summary: input.summary || "The model returned an uncertain observation.",
    suggestion: input.suggestion || "Keep observing and add more context."
  };
}

export const scenarioTypes = [
  { id: "lowActivity", label: "Low activity" },
  { id: "nightYowl", label: "Night yowl" },
  { id: "litterConcern", label: "Litter concern" },
  { id: "appetiteGap", label: "Appetite gap" },
  { id: "grooming", label: "Grooming spike" },
  { id: "conflict", label: "A/V conflict" },
  { id: "eating", label: "Eating" },
  { id: "play", label: "Play" }
];
