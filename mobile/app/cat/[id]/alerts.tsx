import { LinearGradient } from 'expo-linear-gradient';
import { router, useLocalSearchParams } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Theme } from '@/constants/Theme';
import { useApp } from '@/context/AppContext';

export default function CatAlertsScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { cats } = useApp();
  const cat = cats.find((item) => item.id === id);

  return (
    <LinearGradient colors={['#111312', '#171812', '#101716']} style={styles.gradient}>
      <SafeAreaView style={styles.safe}>
        <View style={styles.container}>
          <Pressable
            onPress={() => router.back()}
            style={({ pressed }) => [styles.backButton, pressed && styles.pressed]}
            accessibilityLabel="Go back"
            accessibilityRole="button">
            <Text style={styles.backText}>← Back</Text>
          </Pressable>

          <View style={styles.hero}>
            <Text style={styles.eyebrow}>Alerts</Text>
            <Text style={styles.title}>{cat?.name ?? 'Cat'}</Text>
            <Text style={styles.subtitle}>Warnings & signals</Text>
          </View>

          <View style={styles.placeholder}>
            <Text style={styles.placeholderTitle}>Coming soon</Text>
            <Text style={styles.placeholderBody}>
              Per-cat alerts will appear here once the API is connected.
            </Text>
          </View>
        </View>
      </SafeAreaView>
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  gradient: { flex: 1 },
  safe: { flex: 1 },
  container: {
    flex: 1,
    paddingHorizontal: 20,
    gap: 16,
  },
  backButton: {
    paddingTop: 8,
    paddingVertical: 4,
    paddingRight: 12,
    alignSelf: 'flex-start',
  },
  backText: {
    color: Theme.soft,
    fontSize: 16,
    fontWeight: '600',
  },
  pressed: { opacity: 0.75 },
  hero: { gap: 6 },
  eyebrow: {
    color: Theme.soft,
    fontSize: 11,
    fontWeight: '700',
    textTransform: 'uppercase',
  },
  title: {
    color: Theme.text,
    fontSize: 28,
    fontWeight: '700',
  },
  subtitle: {
    color: Theme.muted,
    fontSize: 14,
  },
  placeholder: {
    backgroundColor: Theme.panel,
    borderWidth: 1,
    borderColor: Theme.line,
    borderRadius: 14,
    padding: 16,
    gap: 8,
  },
  placeholderTitle: {
    color: Theme.text,
    fontSize: 18,
    fontWeight: '700',
  },
  placeholderBody: {
    color: Theme.muted,
    fontSize: 14,
    lineHeight: 20,
  },
});
