import { Platform } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { spacing } from "./theme";

export const webPreviewChrome = {
  topInset: 62,
  bottomInset: 24,
  statusBarHeight: 56,
  islandWidth: 124,
  islandHeight: 34,
  islandTop: 10,
  horizontalPadding: 18,
} as const;

/**
 * 全局 zIndex 栈。所有 Sheet / Drawer / FAB / Modal 必须从这里取值，
 * 杜绝 50 / 100 / 999 这种各组件自定数字互相抢的情况。
 *
 * 注意：RN 原生 <Modal> 的层级永远在 JS zIndex 之上，所以"任何可能被原生
 * Modal 盖住的浮层都必须自己也用 RN Modal 包裹"——这跟 zIndex 数字无关。
 */
export const zLayer = {
  base: 0,
  contentRaised: 5,
  tabBar: 10,
  fab: 20,
  drawerBackdrop: 80,
  overlay: 100,
  sheet: 200,
  picker: 300,
  toast: 400,
} as const;

const WEB_PREVIEW_TOP_INSET = webPreviewChrome.topInset;
const WEB_PREVIEW_BOTTOM_INSET = webPreviewChrome.bottomInset;

export function useAppChromeInsets() {
  const insets = useSafeAreaInsets();
  const topInset = Math.max(insets.top, Platform.OS === "web" ? WEB_PREVIEW_TOP_INSET : 0);
  const bottomInset = Math.max(insets.bottom, Platform.OS === "web" ? WEB_PREVIEW_BOTTOM_INSET : 0);

  return {
    rawInsets: insets,
    topInset,
    bottomInset,
    headerTopPadding: topInset + spacing.md,
    screenTopPadding: topInset + spacing.lg,
    screenBottomPadding: bottomInset + spacing.lg,
    overlayBottomPadding: bottomInset + spacing.lg,
    floatingMenuTopInset: topInset + 48,
    tabBarHeight: 72 + bottomInset,
    tabBarPaddingBottom: bottomInset + spacing.sm,
    tabBarPaddingTop: spacing.sm,
  };
}
