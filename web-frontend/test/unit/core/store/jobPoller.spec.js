import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { actions } from '@baserow/modules/core/store/job'

describe('job store poller', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  test('keeps polling after one failed poll', async () => {
    const dispatch = vi.fn(async (name) => {
      if (name === 'updateAll') {
        throw new Error('502 Bad Gateway')
      }
    })

    await actions.updateAllAndScheduleNext({ dispatch }, [7])

    expect(dispatch).toHaveBeenCalledWith('updateAll', [7])
    expect(dispatch).toHaveBeenCalledWith('tryScheduleNextUpdate')
  })
})
