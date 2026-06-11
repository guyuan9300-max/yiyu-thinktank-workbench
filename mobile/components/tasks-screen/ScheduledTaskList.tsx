import type { ReactNode } from "react";
import type { TaskRecord } from "../../lib/types";
import TaskSection from "./TaskSection";

interface ScheduledTaskListProps {
  title: string;
  tasks: readonly TaskRecord[];
  renderTask: (task: TaskRecord) => ReactNode;
}

export default function ScheduledTaskList({ title, tasks, renderTask }: ScheduledTaskListProps) {
  return <TaskSection title={title} tasks={tasks} renderTask={renderTask} />;
}
