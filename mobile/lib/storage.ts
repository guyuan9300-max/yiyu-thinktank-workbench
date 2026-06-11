import { Platform } from "react-native";

/**
 * Cross-platform secure storage.
 * - iOS/Android: uses expo-secure-store
 * - Web: uses localStorage (for dev preview)
 */

let _secureStore: typeof import("expo-secure-store") | null = null;

const SECURE_STORE_KEY_SAFE_PATTERN = /^[A-Za-z0-9._-]+$/;

function toSecureStoreKey(key: string): string {
  if (SECURE_STORE_KEY_SAFE_PATTERN.test(key)) {
    return key;
  }
  return key.replace(/[^A-Za-z0-9._-]/g, (char) => `_${char.charCodeAt(0).toString(16)}_`);
}

async function getSecureStore() {
  if (Platform.OS === "web") return null;
  if (!_secureStore) {
    _secureStore = await import("expo-secure-store");
  }
  return _secureStore;
}

export async function getItem(key: string): Promise<string | null> {
  const store = await getSecureStore();
  if (store) return store.getItemAsync(toSecureStoreKey(key));
  if (typeof localStorage !== "undefined") return localStorage.getItem(key);
  return null;
}

export async function setItem(key: string, value: string): Promise<void> {
  const store = await getSecureStore();
  if (store) {
    await store.setItemAsync(toSecureStoreKey(key), value);
    return;
  }
  if (typeof localStorage !== "undefined") localStorage.setItem(key, value);
}

export async function deleteItem(key: string): Promise<void> {
  const store = await getSecureStore();
  if (store) {
    await store.deleteItemAsync(toSecureStoreKey(key));
    return;
  }
  if (typeof localStorage !== "undefined") localStorage.removeItem(key);
}
