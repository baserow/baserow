import { toolActivity } from '@baserow/modules/core/toolPresentationTypes'
import {
  RUN_ERROR_CODE,
  RUN_STATUS,
} from '@baserow/modules/core/chatRuns/constants'

import {
  AGENT_REPLY_ERROR_CODE,
  ASK_PERSON_TOOL,
} from '@baserow/modules/agent/constants'

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
  [AGENT_REPLY_ERROR_CODE.PROVIDER_AUTH_FAILED]:
    'agent.replyProviderAuthFailed',
  [AGENT_REPLY_ERROR_CODE.PROVIDER_RATE_LIMITED]:
    'agent.replyProviderRateLimited',
  [AGENT_REPLY_ERROR_CODE.PROVIDER_UNAVAILABLE]:
    'agent.replyProviderUnavailable',
}

/**
 * A stopped or queued reply's note, or an unfinished one's error, as keys.
 * Only a reply without a run waits its turn; a run's own queued status is
 * transient, so one that ended on it was interrupted.
 *
 * @param {object} reply A saved reply, or a followed run's status and error.
 * @param {string} [reply.status] The reply's or the run's status.
 * @param {string} [reply.error_code] Why a failed reply failed, or
 *   `not_started` for a cancelled one that never ran.
 * @param {string|null} [reply.run_id] The run the reply belongs to, if any.
 * @param {boolean} [reply.replying] Whether its run is still being followed.
 * @param {object|null} [reply.stopped_by] The person who stopped it, if any.
 * @param {number} [userId] The viewer, who isn't named for their own stop.
 * @returns {{note?: string, noteParams?: object, error?: string}} Translation
 *   keys to show, with the note's parameters.
 */
export function replyOutcome(
  {
    status,
    error_code: errorCode,
    run_id: runId,
    replying,
    stopped_by: stoppedBy,
  },
  userId
) {
  if (
    replying ||
    !status ||
    status === AGENT_REPLY_STATUS.COMPLETED ||
    status === AGENT_REPLY_STATUS.WAITING
  ) {
    return {}
  }
  if (status === AGENT_REPLY_STATUS.QUEUED && !runId) {
    return { note: 'agent.replyWaitingForPreviousRun' }
  }
  if (status === AGENT_REPLY_STATUS.CANCELLED) {
    if (stoppedBy && stoppedBy.id !== userId) {
      return {
        note: 'agent.replyStoppedBy',
        noteParams: { name: stoppedBy.name },
      }
    }
    return {
      note:
        errorCode === RUN_ERROR_CODE.NOT_STARTED
          ? 'agent.replyCancelledBeforeStart'
          : 'agent.replyStopped',
    }
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

export function isQuestionStep(step) {
  return (step?.presentation_type || step?.tool) === ASK_PERSON_TOOL
}

export function approvalItem(step, approval, registry, t) {
  const {
    title,
    input,
    failureHint,
    status,
    changesData,
    partial,
    links: activityLinks,
    itemErrors,
  } = toolActivity(step, registry, t)
  return {
    id: approval.id,
    status: approval.status,
    stepStatus: status,
    changesData,
    links: activityLinks,
    tool: approval.tool,
    toolLabel:
      step.input?.server && step.input?.tool
        ? t('agent.toolMCPNamed', {
            server: step.input.server,
            tool: step.input.tool,
          })
        : null,
    title,
    input,
    failureHint,
    partial,
    itemErrors,
  }
}
