import { LinearGradient } from 'expo-linear-gradient';
import { useState } from 'react';
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useAuth } from '@/context/AuthContext';
import { Theme } from '@/constants/Theme';

type Mode = 'login' | 'register';

export default function AuthScreen() {
  const { login, register, authLoading, error, clearError } = useAuth();
  const [mode, setMode] = useState<Mode>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  const switchMode = (nextMode: Mode) => {
    setMode(nextMode);
    clearError();
  };

  const handleSubmit = async () => {
    try {
      if (mode === 'login') {
        await login(username, password);
        return;
      }
      await register(username, password);
    } catch {
      // Error message is handled in AuthContext.
    }
  };

  return (
    <LinearGradient colors={['#111312', '#171812', '#101716']} style={styles.gradient}>
      <SafeAreaView style={styles.safe}>
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
          style={styles.container}>
          <View style={styles.hero}>
            <Text style={styles.eyebrow}>Cat wellness monitor</Text>
            <Text style={styles.title}>MeowMeowBeenz</Text>
            <Text style={styles.subtitle}>
              {mode === 'login' ? 'Sign in to continue.' : 'Create an account to get started.'}
            </Text>
          </View>

          <View style={styles.tabs}>
            <Pressable
              onPress={() => switchMode('login')}
              style={[styles.tab, mode === 'login' && styles.tabActive]}>
              <Text style={[styles.tabText, mode === 'login' && styles.tabTextActive]}>Login</Text>
            </Pressable>
            <Pressable
              onPress={() => switchMode('register')}
              style={[styles.tab, mode === 'register' && styles.tabActive]}>
              <Text style={[styles.tabText, mode === 'register' && styles.tabTextActive]}>Register</Text>
            </Pressable>
          </View>

          <View style={styles.form}>
            <TextInput
              value={username}
              onChangeText={setUsername}
              placeholder="Username"
              placeholderTextColor={Theme.muted}
              style={styles.input}
              autoCapitalize="none"
              autoCorrect={false}
            />
            <TextInput
              value={password}
              onChangeText={setPassword}
              placeholder="Password"
              placeholderTextColor={Theme.muted}
              style={styles.input}
              secureTextEntry
            />

            {error ? <Text style={styles.error}>{error}</Text> : null}

            <Pressable
              onPress={handleSubmit}
              disabled={authLoading}
              style={({ pressed }) => [styles.submit, pressed && styles.pressed, authLoading && styles.disabled]}>
              {authLoading ? (
                <ActivityIndicator color={Theme.buttonText} />
              ) : (
                <Text style={styles.submitText}>{mode === 'login' ? 'Sign in' : 'Create account'}</Text>
              )}
            </Pressable>
          </View>
        </KeyboardAvoidingView>
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
    justifyContent: 'center',
    gap: 20,
  },
  hero: { gap: 8 },
  eyebrow: {
    color: Theme.soft,
    fontSize: 12,
    fontWeight: '700',
    textTransform: 'uppercase',
  },
  title: {
    color: Theme.text,
    fontSize: 34,
    fontWeight: '700',
  },
  subtitle: {
    color: Theme.muted,
    fontSize: 15,
    lineHeight: 22,
  },
  tabs: {
    flexDirection: 'row',
    gap: 8,
    backgroundColor: 'rgba(255,255,255,0.06)',
    borderWidth: 1,
    borderColor: Theme.line,
    borderRadius: 10,
    padding: 4,
  },
  tab: {
    flex: 1,
    borderRadius: 8,
    paddingVertical: 10,
    alignItems: 'center',
  },
  tabActive: {
    backgroundColor: Theme.button,
  },
  tabText: {
    color: Theme.muted,
    fontWeight: '700',
  },
  tabTextActive: {
    color: Theme.buttonText,
  },
  form: {
    backgroundColor: Theme.panel,
    borderWidth: 1,
    borderColor: Theme.line,
    borderRadius: 14,
    padding: 16,
    gap: 12,
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
  submit: {
    backgroundColor: Theme.button,
    borderRadius: 10,
    paddingVertical: 14,
    alignItems: 'center',
  },
  submitText: {
    color: Theme.buttonText,
    fontWeight: '700',
    fontSize: 15,
  },
  pressed: { opacity: 0.8 },
  disabled: { opacity: 0.6 },
});
