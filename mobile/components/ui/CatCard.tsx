import { StyleSheet, Text, View } from 'react-native';

import { Theme } from '@/constants/Theme';
import type { CatProfile } from '@/types';

type CatCardProps = {
  cat: CatProfile;
};

export function CatCard({ cat }: CatCardProps) {
  return (
    <View style={styles.card}>
      <View style={[styles.avatar, { backgroundColor: `${cat.accent}33`, borderColor: cat.accent }]}>
        <Text style={[styles.initials, { color: cat.accent }]}>{cat.initials}</Text>
      </View>
      <View style={styles.body}>
        <Text style={styles.name}>{cat.name}</Text>
        <Text style={styles.meta}>{cat.age}</Text>
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
    alignItems: 'center',
  },
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
  name: { color: Theme.text, fontSize: 16, fontWeight: '700' },
  meta: { color: Theme.muted, fontSize: 13 },
});
