import { useEffect, useRef } from "react";
import { Animated, StyleSheet, View } from "react-native";
import { palette } from "../lib/theme";

// 7 根声波柱的相对高度系数（中间高、两侧低），与智能输入面板保持一致的观感。
const BAR_MULTIPLIERS = [0.52, 0.78, 1.1, 1.42, 1.1, 0.78, 0.52] as const;

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

interface WaveformProps {
  // 是否正在录音（且未暂停）——决定声波是跳动还是回落到静止。
  readonly isActive: boolean;
  // 归一化到 0..1 的实时音量（由 recorder metering 换算），驱动柱高。
  readonly meter: number;
  readonly barColor?: string;
  readonly accentColor?: string;
}

/**
 * 录音声波：柱高随实时音量（metering）跳动。无音量数据时（如 Android 系统语音识别
 * 拿不到 metering）调用方传一个温和的固定 meter 即可呈现"正在录"的节奏感。
 */
export default function Waveform({
  isActive,
  meter,
  barColor = palette.textSecondary,
  accentColor = palette.cinnabar,
}: WaveformProps) {
  const values = useRef(BAR_MULTIPLIERS.map(() => new Animated.Value(0.22))).current;

  useEffect(() => {
    // 收集本轮启动的 spring 动画，卸载/重跑时停掉，避免在已卸载组件上继续写 Animated.Value。
    const animations = values.map((value, index) => {
      const next = isActive
        ? clamp(0.18 + meter * 1.6 * BAR_MULTIPLIERS[index], 0.22, 2.2)
        : 0.22;
      const animation = Animated.spring(value, {
        toValue: next,
        useNativeDriver: true,
        speed: 18,
        bounciness: isActive ? 8 : 4,
      });
      animation.start();
      return animation;
    });
    return () => {
      animations.forEach((animation) => animation.stop());
    };
  }, [isActive, meter, values]);

  return (
    <View style={s.row}>
      {values.map((value, index) => (
        <Animated.View
          key={`wave-${index}`}
          style={[
            s.bar,
            { backgroundColor: index === 3 ? accentColor : barColor },
            { opacity: isActive ? 1 : 0.5, transform: [{ scaleY: value }] },
          ]}
        />
      ))}
    </View>
  );
}

const s = StyleSheet.create({
  row: {
    height: 52,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    marginTop: 8,
    marginBottom: 20,
  },
  bar: {
    width: 7,
    height: 32,
    borderRadius: 999,
  },
});
