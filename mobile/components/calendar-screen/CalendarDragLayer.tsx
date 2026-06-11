import { Animated, Text, View } from "react-native";
import { palette } from "../../lib/theme";
import type { TaskRecord } from "../../lib/types";

interface Props {
  styles: any;
  draggingTask: TaskRecord | null;
  dragOpacity: Animated.Value;
  dragScale: Animated.Value;
  dragTranslate: Animated.ValueXY;
}

export default function CalendarDragLayer({
  styles,
  draggingTask,
  dragOpacity,
  dragScale,
  dragTranslate,
}: Props) {
  if (!draggingTask) {
    return null;
  }

  return (
    <View pointerEvents="none" style={styles.dragLayer}>
      <Animated.View
        style={[
          styles.dragDot,
          {
            backgroundColor:
              draggingTask.priority === "high" ? palette.cinnabar : palette.inkBlack,
            opacity: dragOpacity,
            transform: [
              { translateX: dragTranslate.x },
              { translateY: dragTranslate.y },
              { scale: dragScale },
            ],
          },
        ]}
      >
        <Text style={styles.dragDotText}>{draggingTask.title.charAt(0)}</Text>
      </Animated.View>
    </View>
  );
}
