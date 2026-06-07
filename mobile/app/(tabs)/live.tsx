import { StyleSheet, Text, View } from 'react-native';

import { ActionButton } from '@/components/ui/ActionButton';
import { Panel } from '@/components/ui/Panel';
import { RiskBadge } from '@/components/ui/RiskBadge';
import { Screen } from '@/components/ui/Screen';
import { ScreenHeader } from '@/components/ui/ScreenHeader';
import { TimelineCard } from '@/components/ui/TimelineCard';
import { Theme } from '@/constants/Theme';
import { useApp } from '@/context/AppContext';
import { scenarioTypes } from '@/lib/sampleData';

export default function LiveScreen() {
  const { events, analyzeNow, seedDemo, clearTimeline, addScenario } = useApp();
  const latest = events[events.length - 1];

  return (
    <Screen>
      <ScreenHeader
        eyebrow="Live monitor"
        title="Live"
        subtitle="Camera preview, model output, and timeline events."
      />

      <Panel eyebrow="Media" title="Camera preview">
        <View style={styles.preview}>
          <Text style={styles.previewEmoji}>🐱</Text>
          <Text style={styles.previewText}>Camera preview will connect here on device builds.</Text>
        </View>
        <View style={styles.actions}>
          <ActionButton label="Analyze now" onPress={analyzeNow} variant="primary" />
          <ActionButton label="Load demo day" onPress={seedDemo} />
        </View>
      </Panel>

      {latest ? (
        <Panel eyebrow="Latest output" title={latest.state} right={<RiskBadge level={latest.riskLevel} />}>
          <Text style={styles.summary}>{latest.summary}</Text>
          <Text style={styles.meta}>
            {latest.intent} · {Math.round(latest.confidence * 100)}% confidence
          </Text>
          <Text style={styles.suggestion}>{latest.suggestion}</Text>
        </Panel>
      ) : null}

      <Panel eyebrow="Demo controls" title="Inject scenarios">
        <View style={styles.scenarios}>
          {scenarioTypes.map((scenario) => (
            <ActionButton key={scenario.id} label={scenario.label} onPress={() => addScenario(scenario.id)} />
          ))}
        </View>
      </Panel>

      <Panel
        eyebrow="Timeline"
        title={`${events.length} events`}
        right={<ActionButton label="Clear" onPress={clearTimeline} />}>
        <View style={styles.stack}>
          {[...events].reverse().map((event) => (
            <TimelineCard key={event.id} event={event} />
          ))}
        </View>
      </Panel>
    </Screen>
  );
}

const styles = StyleSheet.create({
  preview: {
    minHeight: 180,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: Theme.line,
    backgroundColor: Theme.panel2,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    padding: 16,
  },
  previewEmoji: { fontSize: 42 },
  previewText: { color: Theme.muted, textAlign: 'center', fontSize: 13 },
  actions: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  scenarios: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  stack: { gap: 10 },
  summary: { color: Theme.muted, fontSize: 14, lineHeight: 20 },
  meta: { color: Theme.soft, fontSize: 12 },
  suggestion: { color: Theme.text, fontSize: 13 },
});
