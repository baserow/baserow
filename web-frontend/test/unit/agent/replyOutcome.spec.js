import { describe, expect, test } from 'vitest'
import { replyOutcome } from '@baserow/modules/agent/utils/replies'

describe('replyOutcome', () => {
  test.each([
    ['not_allowed', 'agent.replyNotAllowed'],
    ['chat_run_limit_reached', 'agent.replyRunLimitReached'],
    ['trigger_message_failed', 'agent.replyTriggerMessageFailed'],
    ['trigger_off', 'agent.replyTriggerOff'],
    ['provider_auth_failed', 'agent.replyProviderAuthFailed'],
    ['provider_rate_limited', 'agent.replyProviderRateLimited'],
    ['provider_unavailable', 'agent.replyProviderUnavailable'],
    ['unknown', 'agent.replyFailed'],
  ])('a reply failed with %s shows %s', (errorCode, notice) => {
    expect(replyOutcome({ status: 'failed', error_code: errorCode })).toEqual({
      error: notice,
    })
  })
})
