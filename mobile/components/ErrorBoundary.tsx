import React from "react";
import { View, Text, TouchableOpacity, StyleSheet, ScrollView } from "react-native";
import { colors } from "../lib/theme";

type FallbackViewProps = {
  error: Error;
  onReset: () => void;
  title?: string;
  hint?: string;
};

/** 共享的 fallback 视觉，供 class ErrorBoundary 与 expo-router 的 RouteErrorFallback 复用。 */
function FallbackView({ error, onReset, title, hint }: FallbackViewProps) {
  return (
    <View style={styles.container}>
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <Text style={styles.emoji}>🛠️</Text>
        <Text style={styles.title}>{title ?? "页面出了点问题"}</Text>
        <Text style={styles.hint}>
          {hint ?? "刚才这个界面遇到了异常。你的数据没有丢失，点下方按钮重试即可。"}
        </Text>
        <TouchableOpacity style={styles.button} onPress={onReset} activeOpacity={0.85}>
          <Text style={styles.buttonText}>重试</Text>
        </TouchableOpacity>
        {__DEV__ ? (
          <Text style={styles.devDetail} selectable>
            {error.message}
          </Text>
        ) : null}
      </ScrollView>
    </View>
  );
}

/**
 * expo-router 的 per-route 错误边界 fallback。
 * 在任一 tab 路由文件里 `export function ErrorBoundary(props) { return <RouteErrorFallback {...props} label="consult" /> }`，
 * expo-router 会自动用它包裹整个路由（含该屏的 hooks），单屏渲染异常不再拖垮全局。
 */
export function RouteErrorFallback({
  error,
  retry,
  label,
  title,
  hint,
}: {
  error: Error;
  retry: () => Promise<void>;
  label?: string;
  title?: string;
  hint?: string;
}) {
  const where = label ? `[RouteErrorBoundary:${label}]` : "[RouteErrorBoundary]";
  // eslint-disable-next-line no-console
  console.error(where, error?.message ?? error);
  return <FallbackView error={error} onReset={() => void retry()} title={title} hint={hint} />;
}

type ErrorBoundaryProps = {
  children: React.ReactNode;
  /** 出现在 fallback 顶部的标题 */
  title?: string;
  /** fallback 的辅助说明 */
  hint?: string;
  /** 用于区分是哪一层边界（日志标识），如 "root" / "consult" / "profile" */
  label?: string;
  /** 点击「重试」时额外执行的副作用（如重新拉取数据）。重置内部错误态在此之前发生。 */
  onReset?: () => void;
  /** 自定义 fallback 渲染；提供时覆盖默认 UI。 */
  renderFallback?: (error: Error, reset: () => void) => React.ReactNode;
};

type ErrorBoundaryState = {
  error: Error | null;
};

/**
 * 渲染期 / 生命周期错误的边界。
 *
 * 背景：在此之前整个 App 没有任何 ErrorBoundary（git 历史确认从初版起就缺），
 * 任一页面渲染期抛错（后端返回畸形数据即可触发）都会冒泡到根，导致整屏白屏、
 * 只能强杀重启且无任何提示。此组件给出可恢复出口。
 *
 * 注意：ErrorBoundary 只能捕获「渲染 / 生命周期 / 构造」期间的同步错误，
 * 无法捕获事件回调、setTimeout、async 中的 rejection —— 那些仍需各自 try/catch。
 */
export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: { componentStack?: string }) {
    // 保留可诊断信息，但不泄露给用户。后续可在此接入上报。
    const where = this.props.label ? `[ErrorBoundary:${this.props.label}]` : "[ErrorBoundary]";
    // eslint-disable-next-line no-console
    console.error(where, error?.message ?? error, info?.componentStack ?? "");
  }

  reset = () => {
    this.setState({ error: null });
    this.props.onReset?.();
  };

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;

    if (this.props.renderFallback) {
      return this.props.renderFallback(error, this.reset);
    }

    return (
      <FallbackView
        error={error}
        onReset={this.reset}
        title={this.props.title}
        hint={this.props.hint}
      />
    );
  }
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    flexGrow: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 32,
    paddingVertical: 48,
  },
  emoji: {
    fontSize: 40,
    marginBottom: 16,
  },
  title: {
    fontSize: 18,
    fontWeight: "800",
    color: colors.text,
    marginBottom: 10,
    textAlign: "center",
  },
  hint: {
    fontSize: 14,
    lineHeight: 21,
    color: colors.textSecondary,
    textAlign: "center",
    marginBottom: 28,
  },
  button: {
    backgroundColor: colors.brand,
    paddingHorizontal: 40,
    paddingVertical: 14,
    borderRadius: 16,
  },
  buttonText: {
    color: colors.textOnBrand,
    fontSize: 15,
    fontWeight: "800",
  },
  devDetail: {
    marginTop: 24,
    fontSize: 12,
    color: colors.error,
    textAlign: "center",
  },
});
