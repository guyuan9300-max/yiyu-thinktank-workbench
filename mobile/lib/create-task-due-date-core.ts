export interface CreateTaskDueDatePreset {
  dueDate?: string;
  dueTime?: string;
}

export interface BuildCreateTaskDueDateInput {
  customDate: string | null;
  customTime: string | null;
  preset?: CreateTaskDueDatePreset | null;
  dateCleared: boolean;
}

export function buildCreateTaskDueDate(input: BuildCreateTaskDueDateInput): string | undefined {
  if (input.dateCleared) {
    return undefined;
  }

  if (input.customDate) {
    return input.customTime ? `${input.customDate}T${input.customTime}` : input.customDate;
  }

  if (input.preset?.dueDate) {
    const time = input.customTime || input.preset.dueTime;
    return time ? `${input.preset.dueDate}T${time}` : input.preset.dueDate;
  }

  return undefined;
}
