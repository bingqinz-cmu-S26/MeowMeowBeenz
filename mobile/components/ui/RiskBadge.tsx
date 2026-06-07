import { StyleSheet, Text, View } from 'react-native';

import { Theme, riskColor, riskLabel, type RiskLevel } from '@/constants/Theme';

type RiskBadgeProps = {
  level: RiskLevel;
};

export function RiskBadge({ level }: RiskBadgeProps) {
  const color = riskColor(level);
  return (
    <View style={[styles.badge, { borderColor: color, backgroundColor: `${color}22` }]}>
      <Text style={[styles.text, { color }]}>{riskLabel(level)}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    borderWidth: 1,
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  text: {
    fontSize: 12,
    fontWeight: '700',
    textTransform: 'uppercase',
  },
});
