import type { EventLineRecord, SmartTaskDraft, TaskRecord } from "../../lib/types";
import TaskDetail from "../TaskDetail";
import CreateTask from "../CreateTask";
import RecordNote from "../RecordNote";
import SmartInputSheet from "../SmartInputSheet";
import TaskReviewComposer from "../TaskReviewComposer";

interface TaskModalCoordinatorProps {
  selectedTask: TaskRecord | null;
  showCreate: boolean;
  showSmartInput: boolean;
  showRecord: boolean;
  reviewTaskContext: TaskRecord | null;
  editingTask: TaskRecord | null;
  smartDraft: SmartTaskDraft | null;
  createPreset: { dueDate?: string; dueTime?: string };
  smartInputPreset: { dueDate?: string; dueTime?: string };
  todayKey: string;
  recordTaskContext: TaskRecord | null;
  recordAutoStart?: boolean;
  selectedTaskEventLine?: EventLineRecord | null;
  onCloseSelectedTask: () => void;
  onStartReview: (task: TaskRecord) => void;
  onRecordFromTaskDetail: () => void;
  onUpdateTask: (taskId: string, updates: Partial<TaskRecord>) => void;
  onDeleteTask?: (task: TaskRecord) => void | Promise<void>;
  onReplaceSelectedTask: (task: TaskRecord) => void;
  onOpenClientWorkspace?: (clientId: string, clientName?: string | null) => void;
  onOpenEventLine?: (eventLineId: string) => void;
  onOpenConsult?: (task: TaskRecord) => void;
  onCloseCreate: () => void;
  onCreated: () => void;
  onCloseSmartInput: () => void;
  onApplySmartDraft: (draft: SmartTaskDraft) => void;
  onUploadedRecord: (task: TaskRecord) => void;
  onCloseRecord: () => void;
  onCloseReview: () => void;
  onSavedReview: (updatedTask: TaskRecord) => void;
}

export default function TaskModalCoordinator(props: TaskModalCoordinatorProps) {
  return (
    <>
      {props.selectedTask ? (
        <TaskDetail
          task={props.selectedTask}
          eventLine={props.selectedTaskEventLine}
          onClose={props.onCloseSelectedTask}
          onStartReview={props.onStartReview}
          onRecord={props.onRecordFromTaskDetail}
          onUpdate={props.onUpdateTask}
          onDeleteTask={props.onDeleteTask}
          onTaskReplaced={props.onReplaceSelectedTask}
          onOpenClientWorkspace={props.onOpenClientWorkspace}
          onOpenEventLine={props.onOpenEventLine}
          onOpenConsult={props.onOpenConsult}
        />
      ) : null}

      {props.showCreate ? (
        <CreateTask
          task={props.editingTask}
          draft={props.smartDraft}
          onClose={props.onCloseCreate}
          onCreated={props.onCreated}
          preset={props.createPreset}
        />
      ) : null}

      {props.showSmartInput ? (
        <SmartInputSheet
          autoStart
          referenceDate={props.todayKey}
          onClose={props.onCloseSmartInput}
          onApplyDraft={props.onApplySmartDraft}
        />
      ) : null}

      {props.showRecord ? (
        <RecordNote
          taskContext={props.recordTaskContext}
          autoStart={props.recordAutoStart || Boolean(props.recordTaskContext)}
          onUploaded={props.onUploadedRecord}
          onClose={props.onCloseRecord}
        />
      ) : null}

      {props.reviewTaskContext ? (
        <TaskReviewComposer
          task={props.reviewTaskContext}
          onClose={props.onCloseReview}
          onSaved={props.onSavedReview}
        />
      ) : null}
    </>
  );
}
