import type { ReactNode } from "react";
import type { TaskRecord } from "../../lib/types";
import TaskSection from "./TaskSection";

interface InboxTaskListProps {
  title: string;
  hint: string;
  tasks: readonly TaskRecord[];
  renderTask: (task: TaskRecord) => ReactNode;
}

export default function InboxTaskList({ title, hint, tasks, renderTask }: InboxTaskListProps) {
  return <TaskSection title={title} hint={hint} tasks={tasks} renderTask={renderTask} />;
}
