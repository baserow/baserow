// A chat that is being canceled is still running on the backend until the
// worker acknowledges the stop, so both statuses count as running.
export const RUNNING_STATUSES = ['in_progress', 'canceling']

export function isChatRunning(status) {
  return RUNNING_STATUSES.includes(status)
}
