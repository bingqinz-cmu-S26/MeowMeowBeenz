import { StyleSheet, Text, View } from 'react-native';

import { FilterChips } from '@/components/ui/FilterChips';
import { MetricGrid } from '@/components/ui/MetricGrid';
import { Panel } from '@/components/ui/Panel';
import { Screen } from '@/components/ui/Screen';
import { ScreenHeader } from '@/components/ui/ScreenHeader';
import { TimelineCard } from '@/components/ui/TimelineCard';
import { Theme } from '@/constants/Theme';
import { useApp } from '@/context/AppContext';
import type { ActivityFilter, TimelineEvent } from '@/types';

const filters: { id: ActivityFilter; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'activity', label: 'Activity' },
  { id: 'eating', label: 'Eating' },
  { id: 'litter', label: 'Litter' },
  { id: 'vocal', label: 'Vocal' },
  { id: 'warnings', label: 'Warnings' },
];

function matchesFilter(event: TimelineEvent, filter: ActivityFilter): boolean {
  const label = event.behaviorLabel || '';
  const sound = event.soundType || '';
  if (filter === 'all') return true;
  if (filter === 'eating') return label.includes('eating') || label.includes('nutrition');
  if (filter === 'litter') return label.includes('littering');
  if (filter === 'vocal') return sound.includes('meow') || sound.includes('yowl') || sound.includes('caterwaul');
  if (filter === 'warnings') return event.riskLevel !== 'normal';
  return label.includes('active') || label.includes('play') || label.includes('walking');
}

export default function ActivityScreen() {
  const { events, report, activityFilter, setActivityFilter } = useApp();
  const filtered = [...events].reverse().filter((event) => matchesFilter(event, activityFilter));

  return (
    <Screen>
      <ScreenHeader
        eyebrow="Behavior rhythm"
        title="Activity"
        subtitle={report.summary}
      />

      <Panel eyebrow="Rhythm report" title={`${report.totalEvents} observations`}>
        <MetricGrid
          metrics={[
            { label: 'Active', value: report.counts.active },
            { label: 'Resting', value: report.counts.resting },
            { label: 'Eating', value: report.counts.eating },
            { label: 'Vocal', value: report.counts.vocal },
          ]}
        />
        <View style={styles.rings}>
          {[
            { label: 'Readiness', value: report.counts.active },
            { label: 'Activity', value: report.counts.active + report.counts.grooming },
            { label: 'Rest', value: report.counts.resting },
            { label: 'Quiet', value: Math.max(0, report.totalEvents - report.counts.vocal) },
          ].map((ring) => (
            <View key={ring.label} style={styles.ring}>
              <Text style={styles.ringValue}>{ring.value}</Text>
              <Text style={styles.ringLabel}>{ring.label}</Text>
            </View>
          ))}
        </View>
      </Panel>

      <Panel eyebrow="Activity log" title="Filtered events">
        <FilterChips options={filters} value={activityFilter} onChange={setActivityFilter} />
        <View style={styles.stack}>
          {filtered.map((event) => (
            <TimelineCard key={event.id} event={event} />
          ))}
        </View>
      </Panel>
    </Screen>
  );
}

const styles = StyleSheet.create({
  rings: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  ring: {
    width: '47%',
    backgroundColor: Theme.panel2,
    borderWidth: 1,
    borderColor: Theme.green,
    borderRadius: 999,
    paddingVertical: 14,
    alignItems: 'center',
    gap: 4,
  },
  ringValue: { color: Theme.text, fontSize: 20, fontWeight: '700' },
  ringLabel: { color: Theme.muted, fontSize: 12 },
  stack: { gap: 10 },
});
