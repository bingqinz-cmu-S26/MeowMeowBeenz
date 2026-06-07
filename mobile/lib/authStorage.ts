import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

const TOKEN_KEY = 'meowmeowbeenz_token';

const canUseSecureStore = Platform.OS !== 'web';

export async function getToken(): Promise<string | null> {
  if (!canUseSecureStore) {
    return globalThis.sessionStorage?.getItem(TOKEN_KEY) ?? null;
  }
  return SecureStore.getItemAsync(TOKEN_KEY);
}

export async function setToken(token: string): Promise<void> {
  if (!canUseSecureStore) {
    globalThis.sessionStorage?.setItem(TOKEN_KEY, token);
    return;
  }
  await SecureStore.setItemAsync(TOKEN_KEY, token);
}

export async function clearToken(): Promise<void> {
  if (!canUseSecureStore) {
    globalThis.sessionStorage?.removeItem(TOKEN_KEY);
    return;
  }
  await SecureStore.deleteItemAsync(TOKEN_KEY);
}
