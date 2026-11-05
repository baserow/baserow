import {
  RUN_ERROR_CODE,
  RUN_STATUS,
} from '@baserow/modules/core/chatRuns/constants'

import { AGENT_REPLY_ERROR_CODE } from '@baserow/modules/agent/constants'

const FAILED_REPLY_NOTICES = {
  [RUN_ERROR_CODE.TIMEOUT]: 'agent.replyTimedOut',
  [RUN_ERROR_CODE.INTERRUPTED]: 'agent.replyInterrupted',
  [RUN_ERROR_CODE.NOT_STARTED]: 'agent.replyNotStarted',
  [AGENT_REPLY_ERROR_CODE.NOT_READY]: 'agent.replyNotReady',
  [AGENT_REPLY_ERROR_CODE.NOT_ALLOWED]: 'agent.replyNotAllowed',
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
