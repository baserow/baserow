export const CHAT_RUNS_PAGE = 'chat_runs'
export const CHAT_RUN_CHANGED_MESSAGE = 'chat_run_changed'

export const RUN_CREATED = 'run.created'
export const RUN_STARTED = 'run.started'
export const TEXT_DELTA = 'text.delta'
export const PROGRESS = 'progress'
export const RUN_CANCEL_REQUESTED = 'run.cancel_requested'
export const RUN_FINISHED = 'run.finished'

export const RUN_STATUS = {
  QUEUED: 'queued',
  RUNNING: 'running',
  COMPLETED: 'completed',
  CANCELLED: 'cancelled',
  FAILED: 'failed',
}

export const STATUS_CHECK_MS = 5000
export const MAX_RECONNECT_ATTEMPTS = 3
export const MAX_FINISHED_FOLLOWERS = 20

export const isTerminalStatus = (status) =>
  [RUN_STATUS.COMPLETED, RUN_STATUS.CANCELLED, RUN_STATUS.FAILED].includes(
    status
  )
