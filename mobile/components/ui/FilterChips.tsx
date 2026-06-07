import { Pressable, ScrollView, StyleSheet, Text } from 'react-native';

import { Theme } from '@/constants/Theme';

type FilterChipsProps<T extends string> = {
  options: { id: T; label: string }[];
  value: T;
  onChange: (value: T) => void;
};

export function FilterChips<T extends string>({ options, value, onChange }: FilterChipsProps<T>) {
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.row}>
      {options.map((option) => {
        const active = option.id === value;
        return (
          <Pressable
            key={option.id}
            onPress={() => onChange(option.id)}
            style={[styles.chip, active && styles.active]}>
            <Text style={[styles.text, active && styles.activeText]}>{option.label}</Text>
          </Pressable>
        );
      })}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  row: { gap: 8, paddingVertical: 2 },
  chip: {
    borderWidth: 1,
    borderColor: Theme.line,
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 8,
    backgroundColor: Theme.panel2,
  },
  active: {
    backgroundColor: Theme.button,
    borderColor: Theme.button,
  },
  text: { color: Theme.muted, fontSize: 12, fontWeight: '600' },
  activeText: { color: Theme.buttonText },
});
