import "react-native-gesture-handler";
import { Slot, useRouter, useSegments } from "expo-router";
import { useEffect, useMemo, useState } from "react";
import { Platform, View, StyleSheet, Text, TouchableOpacity, useWindowDimensions } from "react-native";
import { StatusBar } from "expo-status-bar";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { AuthProvider, useAuth } from "../lib/auth-context";
import { ErrorBoundary } from "../components/ErrorBoundary";
import { colors, shadow } from "../lib/theme";

function RootNavigator() {
  const { isLoading, user } = useAuth();
  const segments = useSegments();
  const router = useRouter();

  useEffect(() => {
    if (isLoading) return;

    const inAuthGroup = segments[0] === "login";

    if (!user && !inAuthGroup) {
      router.replace("/login");
    } else if (user && inAuthGroup) {
      router.replace("/(tabs)/tasks");
    }
  }, [isLoading, user, segments, router]);

  return (
    <>
      <StatusBar style="dark" />
      <Slot />
    </>
  );
}

export default function RootLayout() {
  const { width } = useWindowDimensions();
  const [debugPanelOptIn, setDebugPanelOptIn] = useState(false);

  useEffect(() => {
    if (Platform.OS !== "web") return;
    try {
      const search = window.location.search ?? "";
      setDebugPanelOptIn(search.includes("debugPanel=1"));
    } catch {
      setDebugPanelOptIn(false);
    }
  }, []);

  const showDebugPanel = useMemo(() => {
    if (!__DEV__) return false;
    if (Platform.OS !== "web") return false;
    if (!debugPanelOptIn) return false;
    return width >= 1280;
  }, [debugPanelOptIn, width]);

  const inner = (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <ErrorBoundary label="root">
          <AuthProvider>
            <RootNavigator />
          </AuthProvider>
        </ErrorBoundary>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );

  // Web: wrap in phone-sized frame for desktop preview
  if (Platform.OS === "web") {
    return (
      <View style={webStyles.wrapper}>
        <View style={webStyles.shell}>
          <View style={webStyles.browserBar}>
            <View style={webStyles.browserDots}>
              <View style={[webStyles.browserDot, webStyles.browserDotRed]} />
              <View style={[webStyles.browserDot, webStyles.browserDotAmber]} />
              <View style={[webStyles.browserDot, webStyles.browserDotGreen]} />
            </View>
            <View style={webStyles.browserAddress}>
              <Text style={webStyles.browserAddressText}>Android / Web 调试预览</Text>
            </View>
            <View style={webStyles.browserSpacer} />
          </View>
          <View style={webStyles.canvas}>
            {inner}
          </View>
        </View>
        {showDebugPanel ? (
          <View style={webStyles.debugPanel}>
            <Text style={webStyles.debugTitle}>调试面板</Text>
            <TouchableOpacity style={webStyles.debugBtn} onPress={() => { (window as any).__yiyu_debug_create?.(); }}>
              <Text style={webStyles.debugBtnText}>+ 新建任务</Text>
            </TouchableOpacity>
            <TouchableOpacity style={webStyles.debugBtn} onPress={() => { (window as any).__yiyu_debug_record?.(); }}>
              <Text style={webStyles.debugBtnText}>🎙 速记</Text>
            </TouchableOpacity>
          </View>
        ) : null}
      </View>
    );
  }

  return inner;
}

const webStyles = StyleSheet.create({
  wrapper: {
    flex: 1,
    backgroundColor: colors.panel,
    flexDirection: "row" as any,
    alignItems: "center",
    justifyContent: "center",
    gap: 44,
    paddingHorizontal: 28,
    paddingVertical: 24,
  },
  shell: {
    width: 440,
    height: 920,
    backgroundColor: "#F4F6FB",
    borderRadius: 28,
    overflow: "hidden",
    position: "relative" as any,
    borderWidth: 1,
    borderColor: "rgba(126,133,157,0.18)",
    ...shadow.phone,
    boxShadow: "0 20px 64px rgba(0,0,0,0.22)" as any,
  },
  browserBar: {
    height: 58,
    paddingHorizontal: 16,
    borderBottomWidth: 1,
    borderBottomColor: "rgba(126,133,157,0.14)",
    backgroundColor: "#EDF1F8",
    flexDirection: "row" as any,
    alignItems: "center",
    gap: 12,
  },
  browserDots: {
    flexDirection: "row" as any,
    alignItems: "center",
    gap: 6,
  },
  browserDot: {
    width: 10,
    height: 10,
    borderRadius: 999,
  },
  browserDotRed: {
    backgroundColor: "#F87171",
  },
  browserDotAmber: {
    backgroundColor: "#FBBF24",
  },
  browserDotGreen: {
    backgroundColor: "#34D399",
  },
  browserAddress: {
    flex: 1,
    height: 36,
    borderRadius: 14,
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: "rgba(126,133,157,0.14)",
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: 14,
  },
  browserAddressText: {
    color: "#5E657A",
    fontSize: 13,
    fontWeight: "700",
  },
  browserSpacer: {
    width: 36,
  },
  canvas: {
    flex: 1,
    backgroundColor: "#FFFFFF",
  },
  debugPanel: {
    width: 168,
    gap: 16,
  },
  debugTitle: {
    color: "#7E859D",
    fontSize: 14,
    fontWeight: "700",
    marginBottom: 8,
  },
  debugBtn: {
    backgroundColor: colors.panelSecondary,
    borderRadius: 18,
    paddingVertical: 20,
    paddingHorizontal: 18,
    alignItems: "center",
  },
  debugBtnText: {
    color: "#FFFFFF",
    fontSize: 14,
    fontWeight: "800",
  },
});
