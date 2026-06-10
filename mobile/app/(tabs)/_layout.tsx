import { View, TouchableOpacity, StyleSheet, Text } from "react-native";
import { Tabs } from "expo-router";
import { ListTodo, Calendar, MessageSquare, User } from "lucide-react-native";
import { palette, typography, iconStroke } from "../../lib/theme";
import { useAppChromeInsets } from "../../lib/app-chrome";
import SuperFAB from "../../components/SuperFAB";

export default function TabLayout() {
  return (
    <>
      <Tabs
        screenOptions={{
          headerShown: false,
        }}
        tabBar={(props) => <CustomTabBar {...props} />}
      >
        <Tabs.Screen name="tasks" options={{ title: "任务" }} />
        <Tabs.Screen name="calendar" options={{ title: "日历" }} />
        <Tabs.Screen name="consult" options={{ title: "咨询" }} />
        <Tabs.Screen name="profile" options={{ title: "我的" }} />
      </Tabs>
    </>
  );
}

const TAB_ICONS = {
  tasks: ListTodo,
  calendar: Calendar,
  consult: MessageSquare,
  profile: User,
} as const;

const TAB_LABELS: Record<string, string> = {
  tasks: "任务",
  calendar: "日历",
  consult: "咨询",
  profile: "我的",
};

function CustomTabBar({ state, navigation }: { state: any; navigation: any }) {
  const chrome = useAppChromeInsets();
  const leftTabs = state.routes.slice(0, 2);  // 任务, 日历
  const rightTabs = state.routes.slice(2, 4); // 咨询, 我的

  const renderTab = (route: { name: string; key: string }, index: number) => {
    const routeName = route.name as keyof typeof TAB_ICONS;
    const Icon = TAB_ICONS[routeName];
    const label = TAB_LABELS[routeName] ?? routeName;
    const isFocused = state.routes[state.index].name === routeName;

    const onPress = () => {
      const event = navigation.emit({ type: "tabPress", target: route.key, canPreventDefault: true });
      if (!isFocused && !event.defaultPrevented) {
        navigation.navigate(route.name);
      }
    };

    return (
      <TouchableOpacity key={route.key} style={s.tab} onPress={onPress} activeOpacity={0.7}>
        {Icon && (
          <Icon
            size={22}
            strokeWidth={iconStroke}
            color={isFocused ? palette.airyBlue : palette.textTertiary}
          />
        )}
        <Text style={[s.tabLabel, isFocused && s.tabLabelActive]}>{label}</Text>
      </TouchableOpacity>
    );
  };

  return (
    <View
      style={[
        s.tabBarContainer,
        {
          height: chrome.tabBarHeight,
          paddingBottom: chrome.tabBarPaddingBottom,
          paddingTop: chrome.tabBarPaddingTop,
        },
      ]}
    >
      {/* Left tabs */}
      {leftTabs.map(renderTab)}

      {/* Center FAB - embedded in tab bar, protruding up */}
      <View style={s.fabWrapper}>
        <SuperFAB
          onCreateTask={() => {
            navigation.navigate("tasks", { modal: "create", trigger: String(Date.now()) });
          }}
          onSmartInput={() => {
            navigation.navigate("tasks", { modal: "smart", trigger: String(Date.now()) });
          }}
          onRecordNote={() => {
            navigation.navigate("tasks", { modal: "record", trigger: String(Date.now()) });
          }}
        />
      </View>

      {/* Right tabs */}
      {rightTabs.map(renderTab)}
    </View>
  );
}

const s = StyleSheet.create({
  tabBarContainer: {
    flexDirection: "row",
    alignItems: "flex-end",
    justifyContent: "space-around",
    backgroundColor: palette.surfaceCard, // 白底，与桌面滴答清单一致
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: palette.borderSubtle,
    overflow: "visible", // FAB 浮出 -30，Android 需要显式 visible
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: -4 },
    shadowOpacity: 0.04,
    shadowRadius: 12,
    elevation: 8,
  },
  tab: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: 4,
  },
  tabLabel: {
    ...typography.label,
    color: palette.textTertiary,
  },
  tabLabelActive: {
    color: palette.airyBlue,
    fontWeight: "700",
  },
  fabWrapper: {
    width: 80, // 92 → 80，给左右两组 tab 留更多对称空间
    alignItems: "center",
    marginTop: -30,
  },
});
