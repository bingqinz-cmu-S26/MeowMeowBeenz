import { Pressable, StyleSheet, Text } from 'react-native';

import { Theme } from '@/constants/Theme';

type ActionButtonProps = {
  label: string;
  onPress: () => void;
  variant?: 'primary' | 'ghost';
};

export function ActionButton({ label, onPress, variant = 'ghost' }: ActionButtonProps) {
  const primary = variant === 'primary';
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.button,
        primary ? styles.primary : styles.ghost,
        pressed && styles.pressed,
      ]}>
      <Text style={[styles.text, primary && styles.primaryText]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderWidth: 1,
  },
  primary: {
    backgroundColor: Theme.button,
    borderColor: Theme.button,
  },
  ghost: {
    backgroundColor: 'transparent',
    borderColor: Theme.line,
  },
  pressed: { opacity: 0.7 },
  text: { color: Theme.text, fontSize: 13, fontWeight: '600', textAlign: 'center' },
  primaryText: { color: Theme.buttonText },
});
