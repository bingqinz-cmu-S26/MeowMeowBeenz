import { ReactNode } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { Theme } from '@/constants/Theme';

type PanelProps = {
  eyebrow?: string;
  title?: string;
  right?: ReactNode;
  children: ReactNode;
};

export function Panel({ eyebrow, title, right, children }: PanelProps) {
  return (
    <View style={styles.panel}>
      {(eyebrow || title || right) && (
        <View style={styles.header}>
          <View style={styles.headerText}>
            {eyebrow ? <Text style={styles.eyebrow}>{eyebrow}</Text> : null}
            {title ? <Text style={styles.title}>{title}</Text> : null}
          </View>
          {right}
        </View>
      )}
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  panel: {
    backgroundColor: Theme.panel,
    borderWidth: 1,
    borderColor: Theme.line,
    borderRadius: 14,
    padding: 14,
    gap: 12,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: 12,
  },
  headerText: { flex: 1, gap: 4 },
  eyebrow: {
    color: Theme.soft,
    fontSize: 11,
    fontWeight: '700',
    textTransform: 'uppercase',
  },
  title: {
    color: Theme.text,
    fontSize: 20,
    fontWeight: '700',
  },
});
