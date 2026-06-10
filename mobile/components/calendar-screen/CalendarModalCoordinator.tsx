import TaskDetail from "../../components/TaskDetail";
import RecordNote from "../../components/RecordNote";
import TaskReviewComposer from "../../components/TaskReviewComposer";
import CreateTask from "../../components/CreateTask";
import SmartInputSheet from "../../components/SmartInputSheet";
import type { EventLineRecord, SmartTaskDraft, TaskRecord } from "../../lib/types";

interface Props {
  selectedTask: TaskRecord | null;
  selectedTaskEventLine?: EventLineRecord | null;
  recordTaskContext: TaskRecord | null;
  reviewTaskContext: TaskRecord | null;
  showCreate: boolean;
  showSmartInput: boolean;
  smartDraft: SmartTaskDraft | null;
  createPreset: { dueDate?: string; dueTime?: string };
  smartInputPreset: { dueDate?: string; dueTime?: string };
  selectedDateKey: string;
  onCloseSelectedTask: () => void;
  onStartReview: (task: TaskRecord) => void;
  onRecordFromTaskDetail: () => void;
  onUpdateTask: (taskId: string, updates: Partial<TaskRecord>) => void;
  onDeleteTask?: (task: TaskRecord) => void | Promise<void>;
  onReplaceSelectedTask: (task: TaskRecord) => void;
  onOpenClientWorkspace?: (clientId: string, clientName?: string | null) => void;
  onOpenEventLine?: (eventLineId: string) => void;
  onOpenConsult?: (task: TaskRecord) => void;
  onUploadedRecord: (task: TaskRecord) => void;
  onCloseRecord: () => void;
  onCloseReview: () => void;
  onSavedReview: () => void;
  onCloseCreate: () => void;
  onCreated: () => void;
  onCloseSmartInput: () => void;
  onApplySmartDraft: (draft: SmartTaskDraft) => void;
}

export default function CalendarModalCoordinator({
  selectedTask,
  selectedTaskEventLine,
  recordTaskContext,
  reviewTaskContext,
  showCreate,
  showSmartInput,
  smartDraft,
  createPreset,
  smartInputPreset,
  selectedDateKey,
  onCloseSelectedTask,
  onStartReview,
  onRecordFromTaskDetail,
  onUpdateTask,
  onDeleteTask,
  onReplaceSelectedTask,
  onOpenClientWorkspace,
  onOpenEventLine,
  onOpenConsult,
  onUploadedRecord,
  onCloseRecord,
  onCloseReview,
  onSavedReview,
  onCloseCreate,
  onCreated,
  onCloseSmartInput,
  onApplySmartDraft,
}: Props) {
  return (
    <>
      {selectedTask && (
        <TaskDetail
          task={selectedTask}
          eventLine={selectedTaskEventLine}
          onClose={onCloseSelectedTask}
          onStartReview={onStartReview}
          onRecord={onRecordFromTaskDetail}
          onUpdate={onUpdateTask}
          onDeleteTask={onDeleteTask}
          onTaskReplaced={onReplaceSelectedTask}
          onOpenClientWorkspace={onOpenClientWorkspace}
          onOpenEventLine={onOpenEventLine}
          onOpenConsult={onOpenConsult}
        />
      )}
      {recordTaskContext && (
        <RecordNote
          taskContext={recordTaskContext}
          autoStart
          onUploaded={onUploadedRecord}
          onClose={onCloseRecord}
        />
      )}
      {reviewTaskContext && (
        <TaskReviewComposer
          task={reviewTaskContext}
          onClose={onCloseReview}
          onSaved={onSavedReview}
        />
      )}
      {showCreate && (
        <CreateTask
          task={null}
          draft={smartDraft}
          onClose={onCloseCreate}
          onCreated={onCreated}
          preset={createPreset}
        />
      )}
      {showSmartInput && (
        <SmartInputSheet
          autoStart
          referenceDate={selectedDateKey}
          onClose={onCloseSmartInput}
          onApplyDraft={onApplySmartDraft}
        />
      )}
    </>
  );
}
