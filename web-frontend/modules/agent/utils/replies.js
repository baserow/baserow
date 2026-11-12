import {
  RUN_ERROR_CODE,
  RUN_STATUS,
} from '@baserow/modules/core/chatRuns/constants'

import { AGENT_REPLY_ERROR_CODE } from '@baserow/modules/agent/constants'

/** A reply's status: its run's, or waiting while held calls are decided. */
export const AGENT_REPLY_STATUS = Object.freeze({
  ...RUN_STATUS,
  WAITING: 'waiting',
})

export const APPROVAL_STATUS = Object.freeze({
  PENDING: 'pending',
  APPROVED: 'approved',
  REJECTED: 'rejected',
})

const FAILED_REPLY_NOTICES = {
  [RUN_ERROR_CODE.TIMEOUT]: 'agent.replyTimedOut',
  [RUN_ERROR_CODE.INTERRUPTED]: 'agent.replyInterrupted',
  [RUN_ERROR_CODE.NOT_STARTED]: 'agent.replyNotStarted',
  [AGENT_REPLY_ERROR_CODE.NOT_READY]: 'agent.replyNotReady',
  [AGENT_REPLY_ERROR_CODE.NOT_ALLOWED]: 'agent.replyNotAllowed',
  [AGENT_REPLY_ERROR_CODE.RUN_LIMIT_REACHED]: 'agent.replyRunLimitReached',
  [AGENT_REPLY_ERROR_CODE.TRIGGER_MESSAGE_FAILED]:
    'agent.replyTriggerMessageFailed',
  [AGENT_REPLY_ERROR_CODE.TRIGGER_OFF]: 'agent.replyTriggerOff',
}

/** A stopped reply's note or an unfinished one's error, as translation keys. */
export function replyOutcome({ status, error_code: errorCode, replying }) {
  if (
    replying ||
    !status ||
    status === AGENT_REPLY_STATUS.COMPLETED ||
    status === AGENT_REPLY_STATUS.WAITING
  ) {
    return {}
  }
  if (status === AGENT_REPLY_STATUS.CANCELLED) {
    return { note: 'agent.replyStopped' }
  }
  if (status === AGENT_REPLY_STATUS.FAILED) {
    return { error: FAILED_REPLY_NOTICES[errorCode] || 'agent.replyFailed' }
  }
  return { error: 'agent.replyInterrupted' }
}

/** The approvals of a reply that still wait for a decision. */
export function pendingApprovals(reply) {
  return Array.isArray(reply?.approvals)
    ? reply.approvals.filter(
        (approval) => approval?.status === APPROVAL_STATUS.PENDING
      )
    : []
}
