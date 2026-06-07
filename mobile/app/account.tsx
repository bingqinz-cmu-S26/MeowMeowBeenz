import { LinearGradient } from 'expo-linear-gradient';
import { router } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ActionButton } from '@/components/ui/ActionButton';
import { Panel } from '@/components/ui/Panel';
import { Theme } from '@/constants/Theme';
import { useAuth } from '@/context/AuthContext';

export default function AccountScreen() {
  const { user, logout } = useAuth();

  const handleSignOut = async () => {
    await logout();
    router.replace('/(auth)');
  };

  return (
    <LinearGradient colors={['#111312', '#171812', '#101716']} style={styles.gradient}>
      <SafeAreaView style={styles.safe}>
        <View style={styles.container}>
          <View style={styles.topBar}>
            <Pressable
              onPress={() => router.back()}
              style={({ pressed }) => [styles.backButton, pressed && styles.pressed]}
              accessibilityLabel="Go back"
              accessibilityRole="button">
              <Text style={styles.backText}>← Back</Text>
            </Pressable>
          </View>

          <View style={styles.hero}>
            <Text style={styles.eyebrow}>Account</Text>
            <Text style={styles.title}>{user?.username}</Text>
            <Text style={styles.subtitle}>Signed in to MeowMeowBeenz</Text>
          </View>

          <Panel eyebrow="Profile" title="Your account">
            <View style={styles.row}>
              <Text style={styles.label}>Username</Text>
              <Text style={styles.value}>{user?.username}</Text>
            </View>
            {user?.createdAt ? (
              <View style={styles.row}>
                <Text style={styles.label}>Joined</Text>
                <Text style={styles.value}>
                  {new Date(user.createdAt).toLocaleDateString()}
                </Text>
              </View>
            ) : null}
          </Panel>

          <ActionButton label="Sign out" onPress={handleSignOut} variant="primary" />
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
    paddingTop: 8,
    gap: 16,
  },
  topBar: {
    flexDirection: 'row',
    justifyContent: 'flex-start',
  },
  backButton: {
    paddingVertical: 4,
    paddingRight: 12,
  },
  backText: {
    color: Theme.soft,
    fontSize: 16,
    fontWeight: '600',
  },
  pressed: { opacity: 0.75 },
  hero: { gap: 6, marginBottom: 4 },
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
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: 12,
  },
  label: { color: Theme.muted, fontSize: 13 },
  value: { color: Theme.text, fontSize: 13, fontWeight: '600' },
});
