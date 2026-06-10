import { Text, TouchableOpacity, View } from "react-native";
import { ChevronDown, ChevronLeft, ChevronRight } from "lucide-react-native";
import { palette, iconStroke } from "../../lib/theme";

interface Props {
  styles: any;
  headerTitle: string;
  viewLabel: string;
  topPadding: number;
  onPrev: () => void;
  onNext: () => void;
  onOpenViewMenu: () => void;
}

export default function CalendarHeader({
  styles,
  headerTitle,
  viewLabel,
  topPadding,
  onPrev,
  onNext,
  onOpenViewMenu,
}: Props) {
  return (
    <View style={[styles.header, { paddingTop: topPadding }]}>
      <View style={styles.headerNav}>
        <TouchableOpacity onPress={onPrev} style={styles.navButton} activeOpacity={0.6}>
          <ChevronLeft size={20} strokeWidth={iconStroke} color={palette.inkBlack} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>{headerTitle}</Text>
        <TouchableOpacity onPress={onNext} style={styles.navButton} activeOpacity={0.6}>
          <ChevronRight size={20} strokeWidth={iconStroke} color={palette.inkBlack} />
        </TouchableOpacity>
      </View>
      <TouchableOpacity style={styles.viewSwitcher} onPress={onOpenViewMenu} activeOpacity={0.6}>
        <Text style={styles.viewSwitcherText}>{viewLabel}</Text>
        <ChevronDown size={14} strokeWidth={iconStroke} color={palette.inkBlack} />
      </TouchableOpacity>
    </View>
  );
}
