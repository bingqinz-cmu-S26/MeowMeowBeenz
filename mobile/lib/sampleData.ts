import type { ScenarioType, TimelineEvent } from '@/types';

const scenarioCatalog = {
  live: {
    state: 'Alert and vocal',
    intent: 'attention_or_food_seeking',
    behaviorLabel: 'active_walking',
    soundType: 'repeated_meow',
    confidence: 0.74,
    riskLevel: 'normal' as const,
    signals: ['unusual_vocalization'],
    summary: 'Mochi is active and producing repeated meows, which often points to attention or food seeking.',
    suggestion: 'Check the usual routine first: food, water, door access, and recent play time.',
  },
  lowActivity: {
    state: 'Extended resting',
    intent: 'resting_or_low_energy',
    behaviorLabel: 'inactive_lying.resting',
    soundType: 'quiet',
    confidence: 0.82,
    riskLevel: 'watch' as const,
    signals: ['low_activity_alert'],
    summary: 'Mochi has stayed in a resting posture with little movement compared with active periods.',
    suggestion: 'Watch appetite and litter behavior. If low activity persists, consider a vet check-in.',
  },
  nightYowl: {
    state: 'Night vocalization',
    intent: 'attention_or_discomfort',
    behaviorLabel: 'inactive_lying.crouch',
    soundType: 'caterwauling',
    confidence: 0.69,
    riskLevel: 'watch' as const,
    signals: ['unusual_vocalization'],
    summary: 'A high-intensity nighttime vocalization was detected while the cat appeared inactive.',
    suggestion: 'Check for immediate needs and monitor whether this repeats tonight.',
  },
  litterConcern: {
    state: 'Repeated litter activity',
    intent: 'litter_box_attempt',
    behaviorLabel: 'maintenance_littering.digging',
    soundType: 'short_meow',
    confidence: 0.77,
    riskLevel: 'watch' as const,
    signals: ['possible_litter_box_issue'],
    summary: 'Mochi appears to be repeatedly digging or visiting the litter area without a clear output event.',
    suggestion: 'Check the litter box and monitor for urination or defecation events.',
  },
  appetiteGap: {
    state: 'Food solicitation without eating',
    intent: 'food_seeking',
    behaviorLabel: 'active_rubbing',
    soundType: 'repeated_meow',
    confidence: 0.71,
    riskLevel: 'watch' as const,
    signals: ['possible_appetite_change'],
    summary: 'Mochi vocalized near a routine feeding context, but no eating event has been logged.',
    suggestion: 'Check food and water. If appetite remains low for 24 hours, consider contacting a vet.',
  },
  grooming: {
    state: 'Focused grooming',
    intent: 'self_grooming_or_irritation',
    behaviorLabel: 'maintenance_scratching',
    soundType: 'quiet',
    confidence: 0.73,
    riskLevel: 'watch' as const,
    signals: ['possible_skin_ear_discomfort'],
    summary: 'Repeated scratching or focused grooming was detected.',
    suggestion: 'Inspect the skin and ears if this repeats or appears intense.',
  },
  conflict: {
    state: 'Resting with distress-like audio',
    intent: 'ambiguous_discomfort',
    behaviorLabel: 'inactive_lying.resting',
    soundType: 'distress_like_yowl',
    confidence: 0.58,
    riskLevel: 'review' as const,
    signals: ['multimodal_conflict', 'unusual_vocalization'],
    summary: 'Video suggests resting, but the vocal pattern sounds distress-like. The signals do not fully agree.',
    suggestion: 'Review the clip and check for visible discomfort before drawing conclusions.',
  },
  eating: {
    state: 'Eating detected',
    intent: 'nutrition',
    behaviorLabel: 'maintenance_nutrition.eating',
    soundType: 'quiet',
    confidence: 0.86,
    riskLevel: 'normal' as const,
    signals: [],
    summary: 'Mochi appears to be eating with a steady posture and low vocal activity.',
    suggestion: 'Log this as a normal appetite signal.',
  },
  play: {
    state: 'Playful movement',
    intent: 'play_or_social_engagement',
    behaviorLabel: 'active_playfight.playing',
    soundType: 'chirp',
    confidence: 0.79,
    riskLevel: 'normal' as const,
    signals: [],
    summary: 'Mochi is moving actively with playful vocal cues.',
    suggestion: 'This looks like a normal enrichment or social play moment.',
  },
};

export const scenarioTypes: ScenarioType[] = [
  { id: 'lowActivity', label: 'Low activity' },
  { id: 'nightYowl', label: 'Night yowl' },
  { id: 'litterConcern', label: 'Litter concern' },
  { id: 'appetiteGap', label: 'Appetite gap' },
  { id: 'grooming', label: 'Grooming spike' },
  { id: 'conflict', label: 'A/V conflict' },
  { id: 'eating', label: 'Eating' },
  { id: 'play', label: 'Play' },
];

export function normalizeEvent(input: Partial<TimelineEvent> & { source?: string }): TimelineEvent {
  return {
    id: `evt_${Date.now()}_${Math.random().toString(16).slice(2)}`,
    time: new Date().toISOString(),
    source: input.source || 'live_capture',
    state: input.state || 'Unknown state',
    intent: input.intent || 'unknown',
    behaviorLabel: input.behaviorLabel || 'unknown',
    soundType: input.soundType || 'unknown',
    confidence: Number(input.confidence || 0),
    riskLevel: input.riskLevel || 'normal',
    signals: Array.isArray(input.signals) ? input.signals : [],
    summary: input.summary || 'The model returned an uncertain observation.',
    suggestion: input.suggestion || 'Keep observing and add more context.',
  };
}

export function createScenarioEvent(type = 'live'): TimelineEvent {
  const scenario = scenarioCatalog[type as keyof typeof scenarioCatalog] || scenarioCatalog.live;
  return normalizeEvent({
    ...scenario,
    source: type === 'live' ? 'live_capture' : 'demo_scenario',
  });
}

export function createSeedEvents(): TimelineEvent[] {
  const now = Date.now();
  const seed = [
    { type: 'eating', minutesAgo: 520 },
    { type: 'play', minutesAgo: 410 },
    { type: 'lowActivity', minutesAgo: 180 },
    { type: 'nightYowl', minutesAgo: 45 },
    { type: 'conflict', minutesAgo: 16 },
  ];

  return seed.map((item) => {
    const event = createScenarioEvent(item.type);
    return { ...event, time: new Date(now - item.minutesAgo * 60 * 1000).toISOString() };
  });
}
