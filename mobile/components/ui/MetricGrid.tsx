import { StyleSheet, Text, View } from 'react-native';

import { Theme } from '@/constants/Theme';

type Metric = {
  label: string;
  value: string | number;
};

type MetricGridProps = {
  metrics: Metric[];
};

export function MetricGrid({ metrics }: MetricGridProps) {
  return (
    <View style={styles.grid}>
      {metrics.map((metric) => (
        <View key={metric.label} style={styles.item}>
          <Text style={styles.value}>{metric.value}</Text>
          <Text style={styles.label}>{metric.label}</Text>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  item: {
    width: '48%',
    backgroundColor: Theme.panel2,
    borderWidth: 1,
    borderColor: Theme.line,
    borderRadius: 10,
    padding: 12,
    gap: 4,
  },
  value: {
    color: Theme.text,
    fontSize: 22,
    fontWeight: '700',
  },
  label: {
    color: Theme.muted,
    fontSize: 12,
  },
});
