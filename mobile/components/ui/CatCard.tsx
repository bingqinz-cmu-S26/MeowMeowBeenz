import { Pressable, StyleSheet, Text, View } from 'react-native';

import { Theme } from '@/constants/Theme';
import type { CatProfile, CatStatus } from '@/types';

type CatCardProps = {
  cat: CatProfile;
  onPress?: () => void;
  onEventsPress?: () => void;
  onAlertsPress?: () => void;
};

function statusColor(status: CatStatus): string {
  if (status === 'alert' || status === 'review') return Theme.red;
  if (status === 'watch') return Theme.yellow;
  if (status === 'perfect') return Theme.cyan;
  return Theme.green;
}

function MiniLinkBox({
  label,
  value,
  onPress,
}: {
  label: string;
  value: string;
  onPress?: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      disabled={!onPress}
      style={({ pressed }) => [styles.miniBox, onPress && pressed && styles.pressed]}>
      <Text style={styles.miniLabel}>{label}</Text>
      <Text style={styles.miniValue}>{value}</Text>
    </Pressable>
  );
}

export function CatCard({ cat, onPress, onEventsPress, onAlertsPress }: CatCardProps) {
  const status: CatStatus = cat.status ?? 'nice';
  const room = cat.room ?? '—';
  const routine = cat.routine ?? '—';
  const eventCount = cat.eventCount ?? 0;
  const alertCount = cat.alertCount ?? 0;

  return (
    <View style={styles.card}>
      <Pressable
        onPress={onPress}
        disabled={!onPress}
        style={({ pressed }) => [styles.main, onPress && pressed && styles.pressed]}>
        <Text style={styles.emoji}>🐱</Text>
        <View style={styles.body}>
          <View style={styles.nameRow}>
            <Text style={styles.name}>{cat.name}</Text>
            <Text style={[styles.status, { color: statusColor(status) }]}>{status}</Text>
          </View>
          <Text style={styles.meta}>{cat.age}</Text>
          <Text style={styles.detail}>
            <Text style={styles.detailLabel}>Room </Text>
            {room}
          </Text>
          <Text style={styles.detail}>
            <Text style={styles.detailLabel}>Routine </Text>
            {routine}
          </Text>
        </View>
      </Pressable>

      <View style={styles.linkRow}>
        <MiniLinkBox label="Events" value={String(eventCount)} onPress={onEventsPress} />
        <MiniLinkBox label="Alerts" value={String(alertCount)} onPress={onAlertsPress} />
      </View>
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
    gap: 10,
  },
  main: {
    flexDirection: 'row',
    gap: 12,
    alignItems: 'flex-start',
  },
  pressed: { opacity: 0.8 },
  emoji: {
    fontSize: 28,
    lineHeight: 32,
    width: 32,
    textAlign: 'center',
  },
  body: { flex: 1, gap: 4 },
  nameRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 8,
  },
  name: { color: Theme.text, fontSize: 16, fontWeight: '700', flex: 1 },
  meta: { color: Theme.muted, fontSize: 13 },
  detail: { color: Theme.muted, fontSize: 12, lineHeight: 17 },
  detailLabel: { color: Theme.soft, fontWeight: '700' },
  status: {
    fontSize: 12,
    fontWeight: '700',
    textTransform: 'uppercase',
  },
  linkRow: {
    flexDirection: 'row',
    gap: 8,
  },
  miniBox: {
    flex: 1,
    backgroundColor: Theme.panel,
    borderWidth: 1,
    borderColor: Theme.line,
    borderRadius: 10,
    paddingVertical: 10,
    paddingHorizontal: 12,
    gap: 2,
  },
  miniLabel: {
    color: Theme.soft,
    fontSize: 11,
    fontWeight: '700',
    textTransform: 'uppercase',
  },
  miniValue: {
    color: Theme.text,
    fontSize: 18,
    fontWeight: '700',
  },
});
