import { useEffect, useRef } from "react";
import { AppState, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { WifiOff, ChevronRight, X } from "lucide-react-native";
import { colors } from "../../lib/theme";
import type { RecoveryTrigger } from "../../lib/smart-input-recovery";

interface SmartInputRecoveryControllerProps {
  queuedCount: number;
  hasRecoveredDraft: boolean;
  isRecovering: boolean;
  onRequestRecovery: (trigger: RecoveryTrigger) => void;
  onOpenRecoveredDraft: () => void;
  onDismissRecoveredDraft: () => void;
  onDismissQueuedRecovery: () => void;
}

export default function SmartInputRecoveryController({
  queuedCount,
  hasRecoveredDraft,
  isRecovering,
  onRequestRecovery,
  onOpenRecoveredDraft,
  onDismissRecoveredDraft,
  onDismissQueuedRecovery,
}: SmartInputRecoveryControllerProps) {
  const appStateRef = useRef(AppState.currentState);

  useEffect(() => {
    onRequestRecovery("tasks_enter");
  }, [onRequestRecovery]);

  useEffect(() => {
    const subscription = AppState.addEventListener("change", (nextState) => {
      const wasInactive = appStateRef.current !== "active";
      appStateRef.current = nextState;
      if (nextState === "active" && wasInactive) {
        onRequestRecovery("app_active");
      }
    });
    return () => {
      subscription.remove();
    };
  }, [onRequestRecovery]);

  if (hasRecoveredDraft) {
    return (
      <View style={styles.bannerWrap}>
        <View style={styles.banner}>
          <TouchableOpacity style={styles.bannerPrimary} activeOpacity={0.82} onPress={onOpenRecoveredDraft}>
            <View style={styles.bannerCopy}>
              <Text style={styles.bannerTitle}>已恢复暂存草稿</Text>
              <Text style={styles.bannerText}>草稿已恢复但未自动打断当前操作，点此继续编辑。</Text>
            </View>
            <ChevronRight size={18} color="#5B7BFE" />
          </TouchableOpacity>
          <TouchableOpacity style={styles.bannerIconButton} activeOpacity={0.78} onPress={onDismissRecoveredDraft}>
            <X size={16} color={colors.textSecondary} />
          </TouchableOpacity>
        </View>
      </View>
    );
  }

  if (queuedCount <= 0) {
    return null;
  }

  return (
    <View style={styles.bannerWrap}>
      <View style={styles.banner}>
        <TouchableOpacity
          style={styles.bannerPrimary}
          activeOpacity={0.82}
          disabled={isRecovering}
          onPress={() => onRequestRecovery("manual")}
        >
          <WifiOff size={16} color="#5B7BFE" />
          <View style={styles.bannerCopy}>
            <Text style={styles.bannerTitle}>{isRecovering ? "正在恢复暂存语音..." : `发现 ${queuedCount} 条暂存语音`}</Text>
            <Text style={styles.bannerText}>点击手动恢复，不再自动弹出任务创建页。</Text>
          </View>
          <ChevronRight size={18} color="#5B7BFE" />
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.bannerIconButton}
          activeOpacity={0.78}
          onPress={onDismissQueuedRecovery}
        >
          <X size={16} color={colors.textSecondary} />
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  bannerWrap: {
    paddingHorizontal: 20,
    paddingTop: 8,
  },
  banner: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#EEF4FF",
    borderWidth: 1,
    borderColor: "#C9D6FF",
    borderRadius: 18,
    paddingLeft: 14,
    paddingRight: 10,
    paddingVertical: 12,
  },
  bannerPrimary: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  bannerCopy: {
    flex: 1,
  },
  bannerActions: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  bannerIconButton: {
    width: 28,
    height: 28,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 14,
  },
  bannerTitle: {
    fontSize: 13,
    fontWeight: "800",
    color: "#4B66D8",
  },
  bannerText: {
    marginTop: 2,
    fontSize: 12,
    lineHeight: 18,
    color: colors.textSecondary,
  },
});
