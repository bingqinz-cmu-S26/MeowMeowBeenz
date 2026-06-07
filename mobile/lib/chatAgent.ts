import { buildRangeReport } from '@/lib/healthRules';
import type { HealthReport, TimelineEvent } from '@/types';

export function answerOwnerQuestion(question: string, timeline: TimelineEvent[], report?: HealthReport): string {
  const normalized = question.trim().toLowerCase();
  const reportData = report || buildRangeReport(timeline, 'day');

  if (timeline.length === 0) {
    return 'I do not have any observations yet. Start a live analysis or add a demo event, then I can summarize state, vocalization, activity, appetite, and litter signals.';
  }
  if (mentions(normalized, ['worry', 'concern', 'vet', 'health', 'sick', 'bad'])) {
    return buildConcernAnswer(reportData);
  }
  if (mentions(normalized, ['meow', 'yowl', 'vocal', 'sound', 'cry'])) {
    return buildVocalAnswer(timeline);
  }
  return buildDailyAnswer(timeline, reportData);
}

function mentions(text: string, terms: string[]): boolean {
  return terms.some((term) => text.includes(term));
}

function buildConcernAnswer(report: HealthReport): string {
  if (report.alerts.length === 0) {
    return 'Based on the timeline, I do not see a warning signal yet. This is still a limited observation window, so keep building the baseline and watch appetite, litter behavior, and activity.';
  }
  const topAlert = report.alerts[0];
  return `I would mark today as ${report.overall}. The strongest signal is "${topAlert.title}" because ${topAlert.evidence[0]} This is not a diagnosis; it is a behavior change worth monitoring. ${topAlert.suggestion}`;
}

function buildVocalAnswer(timeline: TimelineEvent[]): string {
  const vocalEvents = timeline.filter((event) => {
    const sound = event.soundType || '';
    return sound.includes('meow') || sound.includes('yowl') || sound.includes('caterwaul') || sound.includes('chirp');
  });
  if (vocalEvents.length === 0) {
    return 'I do not see a vocalization event in the current timeline. If you heard one, run a live analysis during the sound so I can ground the answer in a clip.';
  }
  const latest = vocalEvents[vocalEvents.length - 1];
  return `The latest vocal event was "${latest.soundType}" with ${Math.round(latest.confidence * 100)}% confidence. The model interpreted it as ${latest.intent}. Evidence: ${latest.summary} I would check simple needs first and keep watching if it repeats.`;
}

function buildDailyAnswer(timeline: TimelineEvent[], report: HealthReport): string {
  const latest = timeline[timeline.length - 1];
  return `Today I have ${report.totalEvents} observations. Overall status is ${report.overall}. Latest state: ${latest.state}, interpreted as ${latest.intent} with ${Math.round(latest.confidence * 100)}% confidence. ${report.summary}`;
}
