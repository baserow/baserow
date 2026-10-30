export const CHAT_RUNS_PAGE = 'chat_runs'
export const CHAT_RUN_CHANGED_MESSAGE = 'chat_run_changed'

export const RUN_CREATED = 'run.created'
export const RUN_STARTED = 'run.started'
export const TEXT_DELTA = 'text.delta'
export const PROGRESS = 'progress'
export const STEP = 'step'
export const RUN_CANCEL_REQUESTED = 'run.cancel_requested'
export const RUN_FINISHED = 'run.finished'
export const RUN_BASELINE = 'run.baseline'
export const RUN_HEARTBEAT = 'run.heartbeat'

export const STEP_STATUS = Object.freeze({
  RUNNING: 'running',
  DONE: 'done',
  FAILED: 'failed',
  STOPPED: 'stopped',
})

export const RUN_STATUS = {
  QUEUED: 'queued',
  RUNNING: 'running',
  COMPLETED: 'completed',
  CANCELLED: 'cancelled',
  FAILED: 'failed',
}

export const STATUS_CHECK_MS = 5000
// A quiet stream sends a heartbeat about every 5 s, so this much silence means it stalled.
export const STREAM_IDLE_MS = 15000
export const MAX_RECONNECT_ATTEMPTS = 3
export const MAX_FINISHED_FOLLOWERS = 20

export const isTerminalStatus = (status) =>
  [RUN_STATUS.COMPLETED, RUN_STATUS.CANCELLED, RUN_STATUS.FAILED].includes(
    status
  )
