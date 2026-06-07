import { router } from 'expo-router';
import { StyleSheet, Text, View } from 'react-native';

import { AccountButton } from '@/components/ui/AccountButton';
import { AddButton } from '@/components/ui/AddButton';
import { CatCard } from '@/components/ui/CatCard';
import { MetricGrid } from '@/components/ui/MetricGrid';
import { Panel } from '@/components/ui/Panel';
import { RiskBadge } from '@/components/ui/RiskBadge';
import { Screen } from '@/components/ui/Screen';
import { ScreenHeader } from '@/components/ui/ScreenHeader';
import { Theme } from '@/constants/Theme';
import { useApp } from '@/context/AppContext';

export default function HomeScreen() {
  const { cats, report } = useApp();

  return (
    <Screen>
      <ScreenHeader
        title="MeowMeowBeenz"
        right={<AccountButton />}
      />

      <Panel eyebrow="Today" title="Household overview" right={<RiskBadge level={report.overall} />}>
        <MetricGrid
          metrics={[
            { label: 'Cats', value: cats.length },
            { label: 'Household', value: report.overall },
            { label: 'Events', value: report.totalEvents },
            { label: 'Warnings', value: report.alerts.length },
          ]}
        />
        <View style={styles.insight}>
          <Text style={styles.insightTitle}>
            {report.alerts[0]?.title || 'Building baseline'}
          </Text>
          <Text style={styles.insightBody}>
            {report.alerts[0]?.suggestion || 'Add live observations or demo events to sharpen household insights.'}
          </Text>
        </View>
      </Panel>

      <Panel
        eyebrow="Cat roster"
        title="Profiles"
        right={<AddButton onPress={() => router.push('/add-cat')} />}>
        <View style={styles.stack}>
          {cats.length === 0 ? (
            <Text style={styles.empty}>No cats yet. Tap Add to create one.</Text>
          ) : (
            cats.map((cat) => <CatCard key={cat.id} cat={cat} />)
          )}
        </View>
      </Panel>
    </Screen>
  );
}

const styles = StyleSheet.create({
  stack: { gap: 10 },
  insight: {
    backgroundColor: Theme.panel2,
    borderWidth: 1,
    borderColor: Theme.line,
    borderRadius: 10,
    padding: 12,
    gap: 6,
  },
  insightTitle: { color: Theme.text, fontWeight: '700', fontSize: 14 },
  insightBody: { color: Theme.muted, fontSize: 13, lineHeight: 18 },
  empty: { color: Theme.muted, fontSize: 13 },
});
