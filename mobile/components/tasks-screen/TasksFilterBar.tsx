import { Modal, StyleSheet, Text, TouchableOpacity, View } from "react-native";

interface FilterOption<T extends string> {
  key: T;
  label: string;
}

interface TasksFilterBarProps<T extends string> {
  visible: boolean;
  floatingMenuTopInset: number;
  selectedKey: T;
  filters: readonly FilterOption<T>[];
  onSelect: (key: T) => void;
  onClose: () => void;
}

export default function TasksFilterBar<T extends string>({
  visible,
  floatingMenuTopInset,
  selectedKey,
  filters,
  onSelect,
  onClose,
}: TasksFilterBarProps<T>) {
  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <TouchableOpacity
        style={[styles.menuOverlay, { paddingTop: floatingMenuTopInset }]}
        activeOpacity={1}
        onPress={onClose}
      >
        <View style={styles.menuCard}>
          {filters.map((filter) => (
            <TouchableOpacity
              key={filter.key}
              style={[styles.menuItem, selectedKey === filter.key && styles.menuItemActive]}
              onPress={() => onSelect(filter.key)}
            >
              <Text style={[styles.menuItemText, selectedKey === filter.key && styles.menuItemTextActive]}>
                {filter.label}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </TouchableOpacity>
    </Modal>
  );
}

const styles = StyleSheet.create({
  menuOverlay: {
    flex: 1,
    backgroundColor: "rgba(17,24,39,0.14)",
    paddingHorizontal: 18,
  },
  menuCard: {
    marginTop: 20,
    marginLeft: "auto",
    width: 180,
    borderRadius: 20,
    backgroundColor: "#FFFFFF",
    paddingVertical: 8,
    shadowColor: "#111827",
    shadowOffset: { width: 0, height: 12 },
    shadowOpacity: 0.14,
    shadowRadius: 26,
    elevation: 10,
  },
  menuItem: {
    paddingHorizontal: 18,
    paddingVertical: 14,
  },
  menuItemActive: {
    backgroundColor: "#EEF4FF",
  },
  menuItemText: {
    fontSize: 14,
    fontWeight: "600",
    color: "#475467",
  },
  menuItemTextActive: {
    color: "#5B7BFE",
  },
});
