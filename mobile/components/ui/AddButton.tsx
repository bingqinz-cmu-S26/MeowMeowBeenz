import { Pressable, StyleSheet, Text } from 'react-native';

import { Theme } from '@/constants/Theme';

type AddButtonProps = {
  onPress: () => void;
};

export function AddButton({ onPress }: AddButtonProps) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [styles.button, pressed && styles.pressed]}
      accessibilityLabel="Add cat"
      accessibilityRole="button">
      <Text style={styles.text}>Add</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    borderWidth: 1,
    borderColor: Theme.line,
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 6,
    backgroundColor: Theme.panel2,
    marginTop: 2,
  },
  pressed: { opacity: 0.75 },
  text: {
    color: Theme.soft,
    fontSize: 12,
    fontWeight: '700',
  },
});
