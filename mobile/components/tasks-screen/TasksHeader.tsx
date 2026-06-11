import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { ChevronDown } from "lucide-react-native";
import { colors } from "../../lib/theme";

interface TasksHeaderProps {
  dateText: string;
  filterLabel: string;
  topPadding: number;
  onOpenFilter: () => void;
}

export default function TasksHeader({
  dateText,
  filterLabel,
  topPadding,
  onOpenFilter,
}: TasksHeaderProps) {
  return (
    <View style={[styles.header, { paddingTop: topPadding }]}>
      <View style={styles.headerRow}>
        <Text style={styles.date}>{dateText}</Text>
        <TouchableOpacity style={styles.filterDropdown} onPress={onOpenFilter}>
          <Text style={styles.filterDropdownText}>{filterLabel}</Text>
          <ChevronDown size={16} strokeWidth={2} color={colors.brand} />
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  header: {
    backgroundColor: "#F7F8FB",
    paddingBottom: 16,
    paddingHorizontal: 20,
  },
  headerRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  date: {
    fontSize: 16,
    fontWeight: "700",
    color: colors.text,
  },
  filterDropdown: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  filterDropdownText: {
    color: colors.brand,
    fontSize: 14,
    fontWeight: "700",
  },
});
