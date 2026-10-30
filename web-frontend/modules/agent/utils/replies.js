import { RUN_STATUS } from '@baserow/modules/core/chatRuns/constants'

const FAILED_REPLY_NOTICES = {
  timeout: 'agent.replyTimedOut',
  interrupted: 'agent.replyInterrupted',
  not_started: 'agent.replyNotStarted',
  not_ready: 'agent.replyNotReady',
  not_allowed: 'agent.replyNotAllowed',
}

/** A stopped reply's note or an unfinished one's error, as translation keys. */
export function replyOutcome({ status, error_code: errorCode, replying }) {
  if (replying || !status || status === RUN_STATUS.COMPLETED) return {}
  if (status === RUN_STATUS.CANCELLED) return { note: 'agent.replyStopped' }
  if (status === RUN_STATUS.FAILED) {
    return { error: FAILED_REPLY_NOTICES[errorCode] || 'agent.replyFailed' }
  }
  return { error: 'agent.replyInterrupted' }
}
