import { StyleSheet, Text, View } from 'react-native';

import { FilterChips } from '@/components/ui/FilterChips';
import { MetricGrid } from '@/components/ui/MetricGrid';
import { Panel } from '@/components/ui/Panel';
import { RiskBadge } from '@/components/ui/RiskBadge';
import { Screen } from '@/components/ui/Screen';
import { ScreenHeader } from '@/components/ui/ScreenHeader';
import { Theme } from '@/constants/Theme';
import { useApp } from '@/context/AppContext';
import type { ReportRange } from '@/types';

const ranges: { id: ReportRange; label: string }[] = [
  { id: 'day', label: 'Day' },
  { id: 'week', label: 'Week' },
  { id: 'month', label: 'Month' },
];

export default function HealthScreen() {
  const { report, reportRange, setReportRange } = useApp();

  return (
    <Screen>
      <ScreenHeader
        eyebrow="Health report"
        title="Health"
        subtitle={report.dateLabel}
      />

      <Panel eyebrow="Range" title="Household health" right={<RiskBadge level={report.overall} />}>
        <FilterChips options={ranges} value={reportRange} onChange={setReportRange} />
        <Text style={styles.summary}>{report.summary}</Text>
        <MetricGrid
          metrics={[
            { label: 'Events', value: report.totalEvents },
            { label: 'Eating', value: report.counts.eating },
            { label: 'Litter', value: report.counts.litter },
            { label: 'Active', value: report.counts.active },
            { label: 'Resting', value: report.counts.resting },
            { label: 'Vocal', value: report.counts.vocal },
          ]}
        />
      </Panel>

      <Panel eyebrow="Warnings" title={`${report.alerts.length} alerts`}>
        <View style={styles.stack}>
          {report.alerts.length === 0 ? (
            <Text style={styles.empty}>No warnings in this range. Keep building the baseline.</Text>
          ) : (
            report.alerts.map((alert) => (
              <View key={alert.signal} style={styles.alert}>
                <View style={styles.alertHeader}>
                  <Text style={styles.alertTitle}>{alert.title}</Text>
                  <RiskBadge level={alert.level} />
                </View>
                {alert.evidence.map((item) => (
                  <Text key={item} style={styles.evidence}>• {item}</Text>
                ))}
                <Text style={styles.suggestion}>{alert.suggestion}</Text>
              </View>
            ))
          )}
        </View>
      </Panel>
    </Screen>
  );
}

const styles = StyleSheet.create({
  summary: { color: Theme.muted, fontSize: 14, lineHeight: 20 },
  stack: { gap: 10 },
  empty: { color: Theme.muted, fontSize: 13 },
  alert: {
    backgroundColor: Theme.panel2,
    borderWidth: 1,
    borderColor: Theme.line,
    borderRadius: 12,
    padding: 12,
    gap: 8,
  },
  alertHeader: { flexDirection: 'row', justifyContent: 'space-between', gap: 8, alignItems: 'center' },
  alertTitle: { color: Theme.text, fontSize: 15, fontWeight: '700', flex: 1 },
  evidence: { color: Theme.muted, fontSize: 13, lineHeight: 18 },
  suggestion: { color: Theme.soft, fontSize: 13, lineHeight: 18 },
});
