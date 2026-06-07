import { LinearGradient } from 'expo-linear-gradient';
import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ActionButton } from '@/components/ui/ActionButton';
import { Panel } from '@/components/ui/Panel';
import { Theme } from '@/constants/Theme';
import { useApp } from '@/context/AppContext';
import { isValidBirthDate } from '@/lib/cats';

export default function EditCatScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { cats, updateCat } = useApp();
  const cat = cats.find((item) => item.id === id);

  const [name, setName] = useState('');
  const [birthDate, setBirthDate] = useState('');
  const [device, setDevice] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!cat) return;
    setName(cat.name);
    setBirthDate(cat.birthDate);
    setDevice(cat.device || '');
  }, [cat]);

  const handleSave = async () => {
    if (!cat || !id) return;

    const trimmedName = name.trim();
    const trimmedBirthDate = birthDate.trim();
    const trimmedDevice = device.trim();

    if (!trimmedName) {
      setError('Name is required.');
      return;
    }
    if (!isValidBirthDate(trimmedBirthDate)) {
      setError('Birth date must use YYYY-MM-DD and cannot be in the future.');
      return;
    }

    setSaving(true);
    setError(null);
    try {
      await updateCat(id, {
        name: trimmedName,
        birthDate: trimmedBirthDate,
        device: trimmedDevice || undefined,
      });
      router.back();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not update cat.');
    } finally {
      setSaving(false);
    }
  };

  if (!cat) {
    return (
      <LinearGradient colors={['#111312', '#171812', '#101716']} style={styles.gradient}>
        <SafeAreaView style={styles.safe}>
          <View style={styles.container}>
            <Pressable onPress={() => router.back()} style={styles.backButton}>
              <Text style={styles.backText}>← Back</Text>
            </Pressable>
            <Text style={styles.missing}>Cat not found.</Text>
          </View>
        </SafeAreaView>
      </LinearGradient>
    );
  }

  return (
    <LinearGradient colors={['#111312', '#171812', '#101716']} style={styles.gradient}>
      <SafeAreaView style={styles.safe}>
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
          style={styles.flex}>
          <ScrollView
            contentContainerStyle={styles.scrollContent}
            keyboardShouldPersistTaps="handled"
            showsVerticalScrollIndicator={false}>
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
              <Text style={styles.eyebrow}>Cat profile</Text>
              <Text style={styles.title}>{cat.name}</Text>
              <Text style={styles.subtitle}>{cat.age}</Text>
            </View>

            <Panel eyebrow="Edit" title="Update info">
              <TextInput
                value={name}
                onChangeText={setName}
                placeholder="Name"
                placeholderTextColor={Theme.muted}
                style={styles.input}
              />
              <TextInput
                value={birthDate}
                onChangeText={setBirthDate}
                placeholder="Birth date (YYYY-MM-DD)"
                placeholderTextColor={Theme.muted}
                style={styles.input}
                autoCapitalize="none"
                autoCorrect={false}
              />
              <TextInput
                value={device}
                onChangeText={setDevice}
                placeholder="Worn device (optional)"
                placeholderTextColor={Theme.muted}
                style={styles.input}
                autoCapitalize="none"
                autoCorrect={false}
              />
              {error ? <Text style={styles.error}>{error}</Text> : null}
              <ActionButton
                label={saving ? 'Saving...' : 'Save changes'}
                onPress={handleSave}
                variant="primary"
              />
              {saving ? <ActivityIndicator color={Theme.button} /> : null}
            </Panel>
          </ScrollView>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  gradient: { flex: 1 },
  safe: { flex: 1 },
  flex: { flex: 1 },
  scrollContent: {
    paddingHorizontal: 20,
    paddingBottom: 24,
    gap: 16,
  },
  topBar: {
    flexDirection: 'row',
    justifyContent: 'flex-start',
    paddingTop: 8,
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
  input: {
    borderWidth: 1,
    borderColor: Theme.line,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 12,
    color: Theme.text,
    backgroundColor: Theme.panel2,
  },
  error: {
    color: Theme.red,
    fontSize: 13,
  },
  missing: {
    color: Theme.muted,
    fontSize: 15,
    marginTop: 24,
  },
  container: {
    flex: 1,
    paddingHorizontal: 20,
    gap: 16,
  },
});
