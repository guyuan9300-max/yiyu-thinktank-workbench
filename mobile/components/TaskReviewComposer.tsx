import { useState } from "react";
import {
  ActivityIndicator,
  Alert,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { useAppChromeInsets } from "../lib/app-chrome";
import { saveTaskReview } from "../lib/task-review-service";
import { colors, palette, typography, iconStroke } from "../lib/theme";
import type { TaskRecord } from "../lib/types";

interface Props {
  readonly task: TaskRecord;
  readonly onClose: () => void;
  readonly onSaved: (task: TaskRecord) => void;
}

export default function TaskReviewComposer({ task, onClose, onSaved }: Props) {
  const chrome = useAppChromeInsets();
  const [reviewNote, setReviewNote] = useState(task.completionNote ?? "");
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    const trimmed = reviewNote.trim();
    if (!trimmed) {
      Alert.alert("请先填写复盘", "保存前需要输入复盘内容。");
      return;
    }
    setSaving(true);
    try {
      const { task: updatedTask } = saveTaskReview(task.id, trimmed);
      onSaved(updatedTask);
    } catch (error) {
      const message = error instanceof Error ? error.message : "复盘保存失败";
      Alert.alert("保存失败", message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <View style={s.overlay}>
      {/* Header */}
      <View style={[s.header, { paddingTop: chrome.headerTopPadding + 8 }]}>
        <Text style={s.headerTitle}>任务复盘</Text>
        <TouchableOpacity
          style={[s.doneButton, saving && { opacity: 0.6 }]}
          onPress={handleSave}
          disabled={saving}
        >
          {saving ? (
            <ActivityIndicator size="small" color={palette.paperRice} />
          ) : (
            <Text style={s.doneButtonText}>完成</Text>
          )}
        </TouchableOpacity>
      </View>

      {/* Editor */}
      <View style={s.editorArea}>
        <TextInput
          style={s.editor}
          value={reviewNote}
          onChangeText={setReviewNote}
          placeholder="记录本次任务的产出、遇到的问题及沉淀的经验..."
          placeholderTextColor={palette.textTertiary}
          multiline
          autoFocus
          textAlignVertical="top"
        />
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  overlay: {
    position: "absolute", top: 0, left: 0, right: 0, bottom: 0,
    backgroundColor: palette.paperRice, zIndex: 60,
  },
  header: {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    paddingHorizontal: 20, paddingBottom: 12,
    borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: palette.borderSubtle,
  },
  headerTitle: { fontSize: 17, fontWeight: "600", color: palette.inkBlack, marginLeft: 4 },
  doneButton: {
    backgroundColor: colors.brand, paddingHorizontal: 20, paddingVertical: 8,
    borderRadius: 20, minWidth: 64, alignItems: "center",
  },
  doneButtonText: { fontSize: 14, fontWeight: "600", color: palette.paperRice },

  editorArea: { flex: 1, paddingHorizontal: 28, paddingTop: 24, paddingBottom: 32 },
  editor: {
    flex: 1, fontSize: 16, lineHeight: 28, color: palette.inkBlack,
  },
});
