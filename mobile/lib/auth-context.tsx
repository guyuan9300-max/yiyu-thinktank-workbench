import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import * as storage from "./storage";
import type { SessionUser } from "./types";
import * as api from "./api";
import {
  initializeRuntime,
  startAuthenticatedRuntime,
  stopAuthenticatedRuntime,
} from "./runtime";

interface AuthState {
  isLoading: boolean;
  user: SessionUser | null;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  /** 用调用方传入的新 SessionUser 立即替换内存里的 user（头像上传等用）。 */
  applyUser: (user: SessionUser) => void;
  /** 主动从云端拉最新 SessionUser 并替换本地 state。 */
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthState>({
  isLoading: true,
  user: null,
  signIn: async () => {},
  signOut: async () => {},
  applyUser: () => {},
  refreshUser: async () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isLoading, setIsLoading] = useState(true);
  const [user, setUser] = useState<SessionUser | null>(null);

  useEffect(() => {
    (async () => {
      try {
        await initializeRuntime();
        const token = await storage.getItem("yiyu_access_token");
        if (token) {
          const me = await api.getMe();
          setUser(me);
        }
      } catch {
        await api.clearTokens();
      } finally {
        setIsLoading(false);
      }
    })();
  }, []);

  useEffect(() => {
    if (isLoading) return;
    if (user) {
      void startAuthenticatedRuntime(user);
      return;
    }
    void stopAuthenticatedRuntime({ clearSessionState: true });
  }, [isLoading, user]);

  // 认证彻底失效(api 层 refresh 也失败)时把内存 user 置空 → RootNavigator 自动跳回
  // 登录页，避免"假登录"(token 失效却停在 tabs)。这正是 api 层一直缺的"上层 signOut"。
  useEffect(() => {
    api.setAuthFailureHandler(() => {
      setUser(null);
    });
    return () => api.setAuthFailureHandler(null);
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    await initializeRuntime();
    const res = await api.login(email, password);
    setUser(res.user);
  }, []);

  const signOut = useCallback(async () => {
    await api.logout();
    setUser(null);
  }, []);

  const applyUser = useCallback((next: SessionUser) => {
    setUser(next);
  }, []);

  const refreshUser = useCallback(async () => {
    try {
      const me = await api.getMe();
      setUser(me);
    } catch {
      // 拉取失败保留旧 user —— 401 会在 api 层走 refresh，再失败上层 signOut。
    }
  }, []);

  const value = useMemo(
    () => ({ isLoading, user, signIn, signOut, applyUser, refreshUser }),
    [isLoading, user, signIn, signOut, applyUser, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  return useContext(AuthContext);
}
