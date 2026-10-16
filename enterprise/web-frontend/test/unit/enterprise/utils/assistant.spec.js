import { describe, expect, test } from 'vitest'

import { runOutcomeKey } from '@baserow_enterprise/utils/assistant'

describe('runOutcomeKey', () => {
  test.each([
    ['cancelled', 'interrupted', 'assistant.runErrorInterrupted'],
    ['failed', 'not_started', 'assistant.runErrorNotStarted'],
    ['failed', 'added_later', 'assistant.runErrorFailed'],
    [null, null, null],
    [undefined, undefined, null],
  ])('a run that ended %s with %j reads as %s', (status, errorCode, key) => {
    expect(runOutcomeKey({ run_status: status, error_code: errorCode })).toBe(
      key
    )
  })
})
