/**
 * theme.ts —— 益语智库手机端 design tokens。
 *
 * 视觉方向：与桌面端保持一致的"滴答清单·airy blue"风格。
 * - 主色 #5B7BFE airy blue（替代原浓墨色板）
 * - 页面底色 #F9FAFB slate-50；卡片底色 #FFFFFF 纯白
 * - 卡片由 hairline border (#E5E7EB) + 轻 airy shadow 双重撑结构
 * - 大圆角主力 rounded-2xl(16) / rounded-3xl(24) / rounded-[32px] 三档
 * - 状态色严格照搬桌面 Tailwind 50/600 配对（emerald/amber/rose/violet）
 *
 * 兼容性策略：
 *   - `palette` 字段名保持不变（300+ 处直接引用），值切到 airy blue 体系。
 *   - 例如 `palette.inkBlack` 仍可用，现在等价于 gray-800 (#1F2937)。
 *   - 新代码推荐用语义化别名：`palette.airyBlue` / `palette.surfaceCard` 等。
 */

import { Platform } from "react-native";

// ─── Palette（语义命名 + 旧字段兼容）───────────────────────────────────
//
// 注意：旧字段名保留（inkBlack/inkLight/inkBlue/paperRice 等），但值已
// 替换为 airy blue 色板。所有 300+ 处旧引用自动跟随。
// 新代码请优先使用语义名（airyBlue / surfaceCanvas / surfaceCard / 等）。

export const palette = {
  // ─── 主色（airy blue 系）─────────────────────────────────
  airyBlue: "#5B7BFE", // 桌面主色
  airyBlueDark: "#4B66D8", // hover / pressed
  airyBlueLight: "#7A95FF", // 二级强调
  airyBlueBg: "#EEF4FF", // 浅蓝白底（被选 / 高亮）
  airyBlueBgStrong: "#DDE7FF", // 浅蓝深 (button hover bg)
  airyBlueRing: "rgba(91,123,254,0.16)", // ring-1 半透明
  airyBlueBorder: "#C9D6FF", // 浅蓝描边
  airyBlueBorderSoft: "#DDE4F3", // 更淡的蓝描边
  airyShadow: "rgba(91,123,254,0.12)", // airy box-shadow

  // ─── 文字层 ─────────────────────────────────────────────
  textPrimary: "#1F2937", // gray-800 桌面 body
  textSecondary: "#4B5563", // gray-600
  textTertiary: "#6B7280", // gray-500
  textMuted: "#94A3B8", // slate-400
  textOnAccent: "#FFFFFF",
  textNumeric: "#1F2937",

  // ─── 纸张层 ─────────────────────────────────────────────
  surfaceCanvas: "#F9FAFB", // 页面底色 slate-50（桌面 body）
  surfaceCard: "#FFFFFF", // 卡片底色 白
  surfaceMuted: "#F1F5F9", // slate-100（灰底 chip）
  surfaceMutedSoft: "#F8FAFF", // 极浅蓝底（hover/selected）
  surfaceElevated: "#FFFFFF",

  // ─── 边框 ───────────────────────────────────────────────
  borderSubtle: "#E5E7EB", // gray-200 桌面卡片边
  borderDivider: "#F1F5F9", // slate-100 分隔线
  borderStrong: "#CBD5E1", // slate-300 加强分隔

  // ─── 状态色（Tailwind 50/600 对，照搬桌面）─────────────
  emerald: "#10B981", // emerald-500
  emeraldBg: "#ECFDF5", // emerald-50
  emeraldText: "#059669", // emerald-600
  amber: "#F59E0B", // amber-500
  amberBg: "#FFFBEB", // amber-50
  amberText: "#B45309", // amber-700
  rose: "#F43F5E", // rose-500
  roseBg: "#FFF1F2", // rose-50
  roseText: "#E11D48", // rose-600
  violet: "#8B5CF6", // violet-500
  violetBg: "#F5F3FF", // violet-50
  violetText: "#7C3AED", // violet-600
  sky: "#0EA5E9",
  skyBg: "#F0F9FF",

  // ─── 旧字段兼容（保留 name，重新映射值）──────────────────
  // 墨色家族 → 文字色
  inkBlack: "#1F2937", // 原浓墨 → gray-800 主文字
  inkLight: "#374151", // gray-700
  inkBlue: "#5B7BFE", // ★ 原黛蓝 → airy blue 主色（很多卡片标题用过它）
  inkBronze: "#6B7280", // gray-500

  // 点缀色 → airy + rose
  cinnabar: "#F43F5E", // 朱砂 → rose-500（退出登录 / 错误用）
  cinnabarTint: "rgba(244,63,94,0.08)",
  cinnabarBorder: "rgba(244,63,94,0.32)",
  reedYellow: "#F59E0B", // 缃色 → amber-500
  bambooGreen: "#10B981", // 竹青 → emerald-500

  // 纸张 → 蓝白
  paperRice: "#F9FAFB", // 宣纸米 → slate-50
  paperSmoke: "#FFFFFF", // 烟灰白 → 纯白
  paperBleached: "#FFFFFF",
  paperMoon: "#F1F5F9", // 月白 → slate-100
} as const;

// ─── Colors（保留扁平 string 结构，全 app 已有 300+ 处直接当 color 用）──

export const colors = {
  // 主色 —— airy blue 系
  brand: palette.airyBlue, // #5B7BFE 桌面主色
  brandLight: palette.airyBlueLight,
  brandDark: palette.airyBlueDark,
  brandBg: palette.airyBlueBg, // #EEF4FF
  brandBg2: palette.airyBlueBgStrong, // #DDE7FF
  brandRing: palette.airyBlueRing,

  // 点缀色 —— 用作错误/退出（rose-500）
  accent: palette.cinnabar, // #F43F5E rose-500
  accentLight: palette.amber,
  accentDark: palette.roseText, // #E11D48
  accentBg: palette.roseBg,
  accentBg2: palette.cinnabarTint,

  // 纸张
  background: palette.surfaceCanvas, // #F9FAFB
  surface: palette.surfaceCard, // #FFFFFF
  surfaceSecondary: palette.surfaceMuted, // #F1F5F9
  surfaceDone: palette.surfaceMutedSoft,
  panel: palette.surfaceCard,
  panelSecondary: palette.surfaceMuted,
  softBlueSurface: palette.surfaceMutedSoft, // #F8FAFF
  softBlueSurfaceStrong: palette.airyBlueBg, // #EEF4FF
  softBlueText: palette.airyBlue,
  busySurface: palette.amberBg,

  // 文字
  text: palette.textPrimary,
  textSecondary: palette.textSecondary,
  textTertiary: palette.textTertiary,
  textOnBrand: "#FFFFFF",

  // 边框
  border: palette.borderSubtle, // #E5E7EB
  borderLight: palette.borderDivider, // #F1F5F9
  borderFocus: palette.airyBlue,
  divider: palette.borderDivider,
  headerPill: palette.surfaceMuted,

  // 优先级（保留语义，色值换到 Tailwind 体系）
  priorityHigh: palette.rose,
  priorityHighBg: palette.roseBg,
  priorityHighBorder: "rgba(244,63,94,0.32)",
  priorityNormal: palette.airyBlue,
  priorityNormalBg: palette.airyBlueBg,
  priorityNormalBorder: palette.airyBlueBorder,
  priorityLow: palette.textTertiary,
  priorityLowBg: palette.surfaceMuted,
  priorityLowBorder: palette.borderSubtle,

  // 状态
  statusTodo: palette.textTertiary,
  statusDoing: palette.airyBlue,
  statusDone: palette.emerald,
  statusDoneBg: palette.emeraldBg,
  statusDoneBorder: "rgba(16,185,129,0.32)",

  // 语义状态色
  error: palette.rose,
  warning: palette.amber,
  success: palette.emerald,
  info: palette.airyBlue,

  // 事件线
  eventLine: palette.violet,
  eventLineBg: palette.violetBg,
  eventLineBorder: "rgba(139,92,246,0.24)",

  // 客户
  clientBg: palette.airyBlueBg,
  clientBorder: palette.airyBlueBorder,
  clientText: palette.airyBlue,
} as const;

// ─── Typography ──────────────────────────────────────────────────────

const sansSerifFamily = Platform.select({
  ios: "PingFang SC",
  android: undefined,
  default: undefined,
});

const monoFamily = Platform.select({
  ios: "Menlo",
  android: "monospace",
  default: "monospace",
});

/**
 * 旧字号原值（保留 export 名）。桌面端字号 10/11/12/13/15，手机略放大
 * 一档（12/13/14/15/17）保证 mobile 触控可读性，但比例与桌面一致。
 */
export const fontSize = {
  xs: 11,
  sm: 12,
  md: 13,
  lg: 15,
  xl: 17,
  xxl: 22,
  title: 28,
} as const;

export const typography = {
  displayLarge: {
    fontFamily: sansSerifFamily,
    fontSize: 32,
    lineHeight: 40,
    fontWeight: "700" as const,
    letterSpacing: -0.3,
  },
  titleHero: {
    fontFamily: sansSerifFamily,
    fontSize: 24,
    lineHeight: 32,
    fontWeight: "700" as const,
    letterSpacing: -0.2,
  },
  titlePage: {
    fontFamily: sansSerifFamily,
    fontSize: 20,
    lineHeight: 28,
    fontWeight: "700" as const,
    letterSpacing: -0.1,
  },
  titleCard: {
    fontFamily: sansSerifFamily,
    fontSize: 15,
    lineHeight: 22,
    fontWeight: "700" as const,
  },
  bodyLarge: {
    fontFamily: sansSerifFamily,
    fontSize: 15,
    lineHeight: 22,
    fontWeight: "500" as const,
  },
  body: {
    fontFamily: sansSerifFamily,
    fontSize: 14,
    lineHeight: 20,
    fontWeight: "400" as const,
  },
  caption: {
    fontFamily: sansSerifFamily,
    fontSize: 12,
    lineHeight: 16,
    fontWeight: "400" as const,
  },
  label: {
    fontFamily: sansSerifFamily,
    fontSize: 11,
    lineHeight: 14,
    fontWeight: "600" as const,
    letterSpacing: 0.2,
  },
  numericLarge: {
    fontFamily: sansSerifFamily,
    fontSize: 22,
    lineHeight: 28,
    fontWeight: "700" as const,
    fontVariant: ["tabular-nums" as const],
  },
  mono: {
    fontFamily: monoFamily,
    fontSize: 12,
    lineHeight: 16,
    fontWeight: "400" as const,
  },
} as const;

export const fontFamily = {
  sans: sansSerifFamily,
  mono: monoFamily,
} as const;

// ─── Spacing ─────────────────────────────────────────────────────────

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  xxl: 28,
  xxxl: 40,
} as const;

export const layout = {
  screenPaddingH: 16,
  rowHeightEntry: 56,
  iconSlotWidth: 44,
} as const;

// ─── Radius ──────────────────────────────────────────────────────────
//
// 桌面端圆角主力：rounded-[32px] 大卡 / rounded-3xl(24) 中卡 / rounded-2xl(16) 普通 /
// rounded-xl(12) 按钮 / rounded-full chip。手机端 1:1 对齐。

export const borderRadius = {
  sm: 10, // chip / 小徽章
  md: 16, // ★主力卡片 / 主按钮（rounded-2xl）
  lg: 20, // 中卡（rounded-[20px]）
  xl: 24, // 大卡（rounded-3xl）
  xxl: 32, // 超大卡（rounded-[32px]）
  full: 9999,
} as const;

// ─── Shadow ──────────────────────────────────────────────────────────
//
// 桌面端三档：
//   shadow-sm (`0 1px 2px rgba(0,0,0,0.05)`) 默认
//   airy (`0 8px 30px rgba(91,123,254,0.12)`) 重点卡片
//   `0 6px 18px rgba(91,123,254,0.28)` 主蓝按钮
//   `0 20px 50px rgba(15,23,42,0.12)` modal

export const shadow = {
  /** 卡片默认 —— 轻微 shadow-sm，与 border-gray-200 一起撑卡片 */
  card: {
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.04,
    shadowRadius: 3,
    elevation: 1,
  },
  /** 重点卡片（同步状态卡 / 今日卡）—— airy blue 蓝雾 shadow */
  softCard: {
    shadowColor: "#5B7BFE",
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.1,
    shadowRadius: 20,
    elevation: 4,
  },
  /** 主蓝 CTA 按钮 —— 较强 airy shadow */
  primaryButton: {
    shadowColor: "#5B7BFE",
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.28,
    shadowRadius: 14,
    elevation: 6,
  },
  /** modal / dialog —— 灰色深 shadow */
  elevated: {
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 20 },
    shadowOpacity: 0.18,
    shadowRadius: 40,
    elevation: 12,
  },
  fab: {
    shadowColor: "#5B7BFE",
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.32,
    shadowRadius: 18,
    elevation: 8,
  },
  phone: {
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 32 },
    shadowOpacity: 0.22,
    shadowRadius: 64,
    elevation: 18,
  },
} as const;

// ─── Icon defaults ────────────────────────────────────────────────────

/** lucide-react-native 全局描边粗细 —— 1.75 给细密但不毛的视觉 */
export const iconStroke = 1.75;

// ─── Component presets ───────────────────────────────────────────────
//
// 把"卡片 / 行 / 章节标题 / 按钮 / 分隔线"这些反复出现的视觉模式做成
// preset。所有 preset 都遵循桌面 airy blue 范式：
// - 卡片：白底 + #E5E7EB 边 + 轻 shadow-sm（重点卡用 airy shadow）
// - 主圆角 16（rounded-2xl）/ 大卡 24（rounded-3xl）
// - 主按钮：#5B7BFE 蓝填 + 白字 + airy shadow
// - 描边按钮：浅 gray-200 边 + gray-700 字
// - 退出按钮：rose-500 描边 + rose-500 字

import type { ViewStyle, TextStyle } from "react-native";

export const presets = {
  /** 标准卡片 —— 白底 + 浅边 + 轻 shadow，圆角 16 */
  cardPaper: {
    backgroundColor: palette.surfaceCard,
    borderWidth: 1,
    borderColor: palette.borderSubtle,
    borderRadius: borderRadius.md, // 16
    ...shadow.card,
  } as ViewStyle,

  /** 大卡片 —— 重点容器，圆角 24 */
  cardPaperLarge: {
    backgroundColor: palette.surfaceCard,
    borderWidth: 1,
    borderColor: palette.borderSubtle,
    borderRadius: borderRadius.xl, // 24
    ...shadow.card,
  } as ViewStyle,

  /** 入口列表容器 —— 白底卡，hairline 分隔 */
  cardList: {
    backgroundColor: palette.surfaceCard,
    borderWidth: 1,
    borderColor: palette.borderSubtle,
    borderRadius: borderRadius.md, // 16
    paddingHorizontal: spacing.lg,
    overflow: "hidden" as const,
    ...shadow.card,
  } as ViewStyle,

  /** 列表行 —— 高 56（标准触控高度），icon 占 36 + 8 gap = 44 缩进 */
  rowEntry: {
    flexDirection: "row" as const,
    alignItems: "center" as const,
    height: layout.rowHeightEntry, // 56
  } as ViewStyle,

  /** hairline 分隔线 —— 左缩进 44，对齐 icon 槽 */
  dividerHairline: {
    height: 0.5,
    backgroundColor: palette.borderDivider, // slate-100
    marginLeft: layout.iconSlotWidth, // 44
  } as ViewStyle,

  /** 章节大标题 —— gray-800 + 700 字重 */
  sectionTitle: {
    ...typography.titlePage, // 20/700/28
    color: palette.textPrimary,
    marginTop: spacing.xxl,
    marginBottom: spacing.md,
  } as TextStyle,

  /** 描边按钮 —— 浅边 + 灰字，标准次要操作 */
  buttonOutline: {
    backgroundColor: palette.surfaceCard,
    borderWidth: 1,
    borderColor: palette.borderSubtle,
    borderRadius: borderRadius.md, // 16
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    alignItems: "center" as const,
    justifyContent: "center" as const,
  } as ViewStyle,

  buttonOutlineText: {
    ...typography.bodyLarge,
    color: palette.textPrimary,
    fontWeight: "600" as const,
  } as TextStyle,

  /** 主 CTA 按钮 —— airy blue 填 + 白字 + airy shadow */
  buttonPrimary: {
    backgroundColor: palette.airyBlue,
    borderRadius: borderRadius.md, // 16
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    alignItems: "center" as const,
    justifyContent: "center" as const,
    ...shadow.primaryButton,
  } as ViewStyle,

  buttonPrimaryText: {
    ...typography.bodyLarge,
    color: "#FFFFFF",
    fontWeight: "700" as const,
  } as TextStyle,

  /** 退出按钮 —— rose-500 描边 + rose 字 */
  buttonCinnabarOutline: {
    backgroundColor: palette.surfaceCard,
    borderWidth: 1,
    borderColor: palette.cinnabarBorder,
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    alignItems: "center" as const,
    justifyContent: "center" as const,
  } as ViewStyle,

  buttonCinnabarOutlineText: {
    ...typography.bodyLarge,
    color: palette.cinnabar,
    fontWeight: "600" as const,
  } as TextStyle,

  /** 标签胶囊 —— slate-100 底 + slate-600 字（参照桌面） */
  pillBadge: {
    paddingHorizontal: spacing.sm + 2, // 10
    paddingVertical: 2,
    borderRadius: borderRadius.full,
    backgroundColor: palette.surfaceMuted, // slate-100
    alignItems: "center" as const,
    justifyContent: "center" as const,
  } as ViewStyle,

  pillBadgeText: {
    ...typography.label,
    color: palette.textSecondary, // gray-600
  } as TextStyle,

  /** 二级页 header —— canvas 底，无下边线 */
  pageHeader: {
    flexDirection: "row" as const,
    alignItems: "center" as const,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    backgroundColor: palette.surfaceCanvas,
    borderBottomWidth: 0,
  } as ViewStyle,

  pageHeaderTitle: {
    ...typography.titleCard, // 15/700/22
    color: palette.textPrimary,
    flex: 1,
    textAlign: "center" as const,
    fontSize: 16,
  } as TextStyle,

  /** 辅助说明文字 */
  hintText: {
    ...typography.caption, // 12/400/16
    color: palette.textTertiary,
    lineHeight: 18,
  } as TextStyle,
} as const;
