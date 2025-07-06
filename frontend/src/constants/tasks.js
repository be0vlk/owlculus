export const TASK_STATUS = {
  NOT_STARTED: 'not_started',
  IN_PROGRESS: 'in_progress',
  BLOCKED: 'blocked',
  COMPLETED: 'completed',
}

export const TASK_PRIORITY = {
  LOW: 'low',
  MEDIUM: 'medium',
  HIGH: 'high',
}

export const TASK_STATUS_LABELS = {
  [TASK_STATUS.NOT_STARTED]: 'Not Started',
  [TASK_STATUS.IN_PROGRESS]: 'In Progress',
  [TASK_STATUS.BLOCKED]: 'Blocked',
  [TASK_STATUS.COMPLETED]: 'Completed',
}

export const TASK_PRIORITY_LABELS = {
  [TASK_PRIORITY.LOW]: 'Low',
  [TASK_PRIORITY.MEDIUM]: 'Medium',
  [TASK_PRIORITY.HIGH]: 'High',
}

export const TASK_STATUS_COLORS = {
  [TASK_STATUS.NOT_STARTED]: 'grey',
  [TASK_STATUS.IN_PROGRESS]: 'deep-purple-lighten-3',
  [TASK_STATUS.BLOCKED]: 'warning',
  [TASK_STATUS.COMPLETED]: 'success',
}

export const TASK_PRIORITY_COLORS = {
  [TASK_PRIORITY.LOW]: 'grey',
  [TASK_PRIORITY.MEDIUM]: 'default',
  [TASK_PRIORITY.HIGH]: 'warning',
}

export const TASK_PRIORITY_ICONS = {
  [TASK_PRIORITY.LOW]: 'mdi-chevron-down',
  [TASK_PRIORITY.MEDIUM]: 'mdi-minus',
  [TASK_PRIORITY.HIGH]: 'mdi-chevron-up',
}
