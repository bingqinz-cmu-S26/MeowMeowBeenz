import { LinearGradient } from 'expo-linear-gradient';
import { ReactNode } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Theme } from '@/constants/Theme';

type ScreenProps = {
  children: ReactNode;
  footer?: ReactNode;
};

export function Screen({ children, footer }: ScreenProps) {
  return (
    <LinearGradient colors={['#111312', '#171812', '#101716']} style={styles.gradient}>
      <SafeAreaView style={styles.safe} edges={['top']}>
        <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
          {children}
        </ScrollView>
        {footer ? <View style={styles.footer}>{footer}</View> : null}
      </SafeAreaView>
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  gradient: { flex: 1 },
  safe: { flex: 1 },
  content: {
    paddingHorizontal: 16,
    paddingBottom: 24,
    gap: 14,
  },
  footer: {
    borderTopWidth: 1,
    borderTopColor: Theme.line,
    backgroundColor: Theme.panel,
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
});
