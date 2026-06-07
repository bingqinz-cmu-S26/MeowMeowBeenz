import { StyleSheet, Text, View } from 'react-native';

import { Theme, riskColor } from '@/constants/Theme';
import type { TimelineEvent } from '@/types';

type TimelineCardProps = {
  event: TimelineEvent;
};

export function TimelineCard({ event }: TimelineCardProps) {
  const time = new Date(event.time).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
  return (
    <View style={styles.card}>
      <View style={styles.header}>
        <Text style={styles.time}>{time}</Text>
        <Text style={[styles.risk, { color: riskColor(event.riskLevel) }]}>{event.riskLevel}</Text>
      </View>
      <Text style={styles.state}>{event.state}</Text>
      <Text style={styles.summary}>{event.summary}</Text>
      <Text style={styles.meta}>{event.intent} · {Math.round(event.confidence * 100)}% confidence</Text>
      {event.signals.length > 0 ? (
        <View style={styles.chips}>
          {event.signals.map((signal) => (
            <View key={signal} style={styles.chip}>
              <Text style={styles.chipText}>{signal}</Text>
            </View>
          ))}
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: Theme.panel2,
    borderWidth: 1,
    borderColor: Theme.line,
    borderRadius: 12,
    padding: 12,
    gap: 6,
  },
  header: { flexDirection: 'row', justifyContent: 'space-between' },
  time: { color: Theme.soft, fontSize: 12, fontWeight: '700' },
  risk: { fontSize: 12, fontWeight: '700', textTransform: 'uppercase' },
  state: { color: Theme.text, fontSize: 16, fontWeight: '700' },
  summary: { color: Theme.muted, fontSize: 13, lineHeight: 18 },
  meta: { color: Theme.muted, fontSize: 12 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 4 },
  chip: {
    borderWidth: 1,
    borderColor: Theme.line,
    borderRadius: 999,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  chipText: { color: Theme.soft, fontSize: 11 },
});
