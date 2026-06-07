import type { Alert, EventCounts, HealthReport, ReportRange, TimelineEvent } from '@/types';

const signalCopy: Record<string, { title: string; suggestion: string }> = {
  possible_appetite_change: {
    title: 'Possible appetite change',
    suggestion: 'Check food and water. If appetite stays low for 24 hours or combines with lethargy, consider contacting a vet.',
  },
  possible_litter_box_issue: {
    title: 'Possible litter box issue',
    suggestion: 'Check the litter box and watch for repeated attempts, straining, or missing output events.',
  },
  low_activity_alert: {
    title: 'Activity lower than expected',
    suggestion: 'Encourage gentle interaction and monitor appetite, litter behavior, and posture.',
  },
  possible_skin_ear_discomfort: {
    title: 'Possible skin or ear discomfort',
    suggestion: 'Inspect for repeated scratching, head shaking, or focused grooming if this continues.',
  },
  unusual_vocalization: {
    title: 'Unusual vocalization pattern',
    suggestion: 'Check immediate needs and monitor whether the vocal pattern repeats or intensifies.',
  },
  multimodal_conflict: {
    title: 'Audio-video mismatch',
    suggestion: 'Review the moment manually. Conflicting signals should be treated as uncertain, not diagnostic.',
  },
};

export function buildRangeReport(events: TimelineEvent[], range: ReportRange = 'day'): HealthReport {
  const scopedEvents = filterByRange(events, range);
  const counts = countEvents(scopedEvents);
  const alerts = [...alertsFromEventSignals(scopedEvents), ...alertsFromBehaviorMix(scopedEvents, counts)];
  const dedupedAlerts = dedupeAlerts(alerts);
  const overall = chooseOverallLevel(dedupedAlerts);

  return {
    dateLabel: labelForRange(range),
    range,
    totalEvents: scopedEvents.length,
    counts,
    alerts: dedupedAlerts,
    overall,
    summary: buildSummary(scopedEvents, dedupedAlerts, overall),
  };
}

function filterByRange(events: TimelineEvent[], range: ReportRange): TimelineEvent[] {
  const now = Date.now();
  const days = range === 'month' ? 30 : range === 'week' ? 7 : 1;
  const start = now - days * 24 * 60 * 60 * 1000;
  return events.filter((event) => new Date(event.time).getTime() >= start);
}

function labelForRange(range: ReportRange): string {
  if (range === 'month') return 'Last 30 days';
  if (range === 'week') return 'Last 7 days';
  return new Date().toLocaleDateString(undefined, { weekday: 'long', month: 'short', day: 'numeric' });
}

function countEvents(events: TimelineEvent[]): EventCounts {
  const counts: EventCounts = {
    eating: 0,
    litter: 0,
    active: 0,
    resting: 0,
    grooming: 0,
    vocal: 0,
    review: 0,
  };

  events.forEach((event) => {
    const label = event.behaviorLabel || '';
    const sound = event.soundType || '';
    if (label.includes('eating') || label.includes('nutrition')) counts.eating += 1;
    if (label.includes('littering')) counts.litter += 1;
    if (isActiveBehavior(label)) counts.active += 1;
    if (label.includes('inactive') || label.includes('resting') || label.includes('lying')) counts.resting += 1;
    if (label.includes('grooming') || label.includes('scratching') || label.includes('shake')) counts.grooming += 1;
    if (sound.includes('meow') || sound.includes('yowl') || sound.includes('caterwaul') || sound.includes('chirp')) counts.vocal += 1;
    if (event.riskLevel === 'review') counts.review += 1;
  });

  return counts;
}

function isActiveBehavior(label: string): boolean {
  if (label.includes('inactive')) return false;
  return label.includes('active') || label.includes('walking') || label.includes('jumping') || label.includes('climbing') || label.includes('play');
}

function alertsFromEventSignals(events: TimelineEvent[]): Alert[] {
  return events.flatMap((event) =>
    event.signals.map((signal) => createAlert(signal, [event.summary], event.confidence)),
  );
}

function alertsFromBehaviorMix(events: TimelineEvent[], counts: EventCounts): Alert[] {
  if (events.length === 0) return [];
  const alerts: Alert[] = [];
  if (counts.eating === 0 && events.length >= 3) {
    alerts.push(createAlert('possible_appetite_change', ["No eating event has been logged in today's timeline."], 0.62));
  }
  if (counts.resting >= 3 && counts.active <= 1) {
    alerts.push(createAlert('low_activity_alert', [`Resting events (${counts.resting}) are dominating active events (${counts.active}).`], 0.67));
  }
  if (counts.litter >= 2 && !events.some((e) => e.behaviorLabel.includes('urinating') || e.behaviorLabel.includes('defecating'))) {
    alerts.push(createAlert('possible_litter_box_issue', ['Repeated litter activity appears without a logged urination or defecation event.'], 0.7));
  }
  if (counts.grooming >= 2) {
    alerts.push(createAlert('possible_skin_ear_discomfort', [`Focused grooming/scratching events appeared ${counts.grooming} times.`], 0.64));
  }
  if (counts.vocal >= 3) {
    alerts.push(createAlert('unusual_vocalization', [`Vocal events appeared ${counts.vocal} times today.`], 0.66));
  }
  return alerts;
}

function createAlert(signal: string, evidence: string[], confidence: number): Alert {
  const copy = signalCopy[signal] || {
    title: 'Behavior change worth monitoring',
    suggestion: 'Keep observing and collect more context before drawing conclusions.',
  };
  return {
    signal,
    level: signal === 'multimodal_conflict' ? 'review' : 'watch',
    title: copy.title,
    evidence,
    suggestion: copy.suggestion,
    confidence,
  };
}

function dedupeAlerts(alerts: Alert[]): Alert[] {
  const bySignal = new Map<string, Alert>();
  alerts.forEach((alert) => {
    const existing = bySignal.get(alert.signal);
    if (!existing) {
      bySignal.set(alert.signal, alert);
      return;
    }
    bySignal.set(alert.signal, {
      ...existing,
      level: existing.level === 'review' || alert.level === 'review' ? 'review' : 'watch',
      confidence: Math.max(existing.confidence, alert.confidence),
      evidence: [...existing.evidence, ...alert.evidence].slice(0, 4),
    });
  });
  return Array.from(bySignal.values());
}

function chooseOverallLevel(alerts: Alert[]): HealthReport['overall'] {
  if (alerts.some((alert) => alert.level === 'review')) return 'review';
  if (alerts.length > 0) return 'watch';
  return 'normal';
}

function buildSummary(events: TimelineEvent[], alerts: Alert[], overall: HealthReport['overall']): string {
  if (events.length === 0) {
    return 'No observations have been logged yet. Start a live analysis or add demo events to build a baseline.';
  }
  if (overall === 'review') {
    return 'Some signals disagree or need human review. This is not a diagnosis, but it is worth checking the recent clips.';
  }
  if (overall === 'watch') {
    return 'Mochi has behavior changes worth monitoring today. Look at the evidence and watch whether the pattern continues.';
  }
  return "Today's observed behavior looks within the normal demo baseline.";
}
