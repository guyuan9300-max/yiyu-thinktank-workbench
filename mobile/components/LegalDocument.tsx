import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { ArrowLeft } from "lucide-react-native";
import { useAppChromeInsets } from "../lib/app-chrome";
import {
  colors,
  spacing,
  layout,
  palette,
  typography,
  presets,
  iconStroke,
} from "../lib/theme";

interface LegalDocumentProps {
  readonly title: string;
  readonly body: string;
  readonly onClose: () => void;
}

// 协议内容页：直接落在 canvas 上，不再用卡片包；正文行高 1.7 制造"阅读纸张"质感。
export default function LegalDocument({ title, body, onClose }: LegalDocumentProps) {
  const chrome = useAppChromeInsets();
  return (
    <SafeAreaView style={styles.container} edges={["left", "right"]}>
      <View style={[presets.pageHeader, { paddingTop: chrome.headerTopPadding }]}>
        <TouchableOpacity onPress={onClose} style={styles.backButton}>
          <ArrowLeft size={22} color={palette.inkBlack} strokeWidth={iconStroke} />
        </TouchableOpacity>
        <Text style={presets.pageHeaderTitle}>{title}</Text>
        <View style={styles.headerSpacer} />
      </View>
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={[
          styles.scrollContent,
          { paddingBottom: chrome.screenBottomPadding + spacing.xxxl },
        ]}
        showsVerticalScrollIndicator
      >
        <Text style={styles.body}>{body}</Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  backButton: { width: 36, height: 36, alignItems: "center", justifyContent: "center" },
  headerSpacer: { width: 36 },
  scroll: { flex: 1 },
  scrollContent: {
    paddingHorizontal: layout.screenPaddingH,
    paddingTop: spacing.lg,
  },
  body: {
    ...typography.body, // 15/400/22
    color: palette.inkBlack,
    lineHeight: 26, // 比 body 默认 22 再宽，制造长文阅读舒适度
  },
});
