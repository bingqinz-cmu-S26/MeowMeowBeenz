import { router } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { Theme } from '@/constants/Theme';
import { useAuth } from '@/context/AuthContext';

function initials(name: string): string {
  return name.slice(0, 2).toUpperCase();
}

export function AccountButton() {
  const { user } = useAuth();
  const label = user?.username || '?';

  return (
    <Pressable
      onPress={() => router.push('/account')}
      style={({ pressed }) => [styles.button, pressed && styles.pressed]}
      accessibilityLabel="Open account"
      accessibilityRole="button">
      <View style={styles.avatar}>
        <Text style={styles.initials}>{initials(label)}</Text>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    marginTop: 2,
  },
  pressed: { opacity: 0.75 },
  avatar: {
    width: 44,
    height: 44,
    borderRadius: 22,
    borderWidth: 1,
    borderColor: Theme.line,
    backgroundColor: Theme.panel2,
    alignItems: 'center',
    justifyContent: 'center',
  },
  initials: {
    color: Theme.soft,
    fontSize: 14,
    fontWeight: '700',
  },
});
