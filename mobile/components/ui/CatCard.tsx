import { StyleSheet, Text, View } from 'react-native';

import { Theme } from '@/constants/Theme';
import type { CatProfile } from '@/types';

type CatCardProps = {
  cat: CatProfile;
  status?: string;
  lastSeen?: string;
  note?: string;
  compact?: boolean;
};

export function CatCard({ cat, status = 'nice', lastSeen, note, compact = false }: CatCardProps) {
  return (
    <View style={[styles.card, compact && styles.compact]}>
      <View style={[styles.avatar, { backgroundColor: `${cat.accent}33`, borderColor: cat.accent }]}>
        <Text style={[styles.initials, { color: cat.accent }]}>{cat.initials}</Text>
      </View>
      <View style={styles.body}>
        <View style={styles.row}>
          <Text style={styles.name}>{cat.name}</Text>
          <Text style={styles.status}>{status}</Text>
        </View>
        {!compact && (
          <>
            <Text style={styles.meta}>{cat.breed} · {cat.age}</Text>
            <Text style={styles.meta}>{cat.room} · {cat.routine}</Text>
          </>
        )}
        {lastSeen ? <Text style={styles.meta}>Last seen {lastSeen}</Text> : null}
        {note ? <Text style={styles.note}>{note}</Text> : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: 'row',
    gap: 12,
    backgroundColor: Theme.panel2,
    borderWidth: 1,
    borderColor: Theme.line,
    borderRadius: 12,
    padding: 12,
  },
  compact: { alignItems: 'center' },
  avatar: {
    width: 44,
    height: 44,
    borderRadius: 22,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  initials: { fontWeight: '700', fontSize: 14 },
  body: { flex: 1, gap: 4 },
  row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  name: { color: Theme.text, fontSize: 16, fontWeight: '700' },
  status: { color: Theme.green, fontSize: 12, fontWeight: '700', textTransform: 'uppercase' },
  meta: { color: Theme.muted, fontSize: 12 },
  note: { color: Theme.soft, fontSize: 12 },
});
