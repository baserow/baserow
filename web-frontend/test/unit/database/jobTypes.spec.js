import {
  ButtonFieldDispatchJobDropped,
  ButtonFieldDispatchJobType,
} from '@baserow/modules/database/jobTypes'

describe('ButtonFieldDispatchJobType', () => {
  const type = new ButtonFieldDispatchJobType({ app: {} })

  test('a finished job resolves the click waiting on it', async () => {
    const waiting = ButtonFieldDispatchJobType.waitFor({ id: 7 })
    const done = { id: 7, state: 'finished', results: [], client_actions: [] }

    await type.afterUpdate(done, done)

    await expect(waiting).resolves.toEqual(done)
  })

  test('a failed job rejects the click waiting on it', async () => {
    const waiting = ButtonFieldDispatchJobType.waitFor({ id: 8 })
    const failed = { id: 8, state: 'failed', human_readable_error: 'nope' }

    await type.afterUpdate(failed, failed)

    await expect(waiting).rejects.toEqual(failed)
  })

  test('a cancelled job rejects the click waiting on it', async () => {
    const waiting = ButtonFieldDispatchJobType.waitFor({ id: 12 })
    const cancelled = { id: 12, state: 'cancelled' }

    await type.afterUpdate(cancelled, cancelled)

    await expect(waiting).rejects.toEqual(cancelled)
  })

  test('an update that is not final leaves the click waiting', async () => {
    let settled = false
    ButtonFieldDispatchJobType.waitFor({ id: 9 }).finally(() => {
      settled = true
    })

    const started = { id: 9, state: 'started' }
    await type.afterUpdate(started, started)
    await Promise.resolve()

    expect(settled).toBe(false)
  })

  test('two clicks polling at once each get their own outcome', async () => {
    const first = ButtonFieldDispatchJobType.waitFor({ id: 10 })
    const second = ButtonFieldDispatchJobType.waitFor({ id: 11 })

    const finished = { id: 11, state: 'finished', results: [] }
    const failed = { id: 10, state: 'failed' }
    await type.afterUpdate(finished, finished)
    await type.afterUpdate(failed, failed)

    await expect(second).resolves.toMatchObject({ id: 11 })
    await expect(first).rejects.toMatchObject({ id: 10 })
  })

  test('a job removed from the store drops the click waiting on it', async () => {
    const waiting = ButtonFieldDispatchJobType.waitFor({ id: 13 })

    type.beforeDelete({ id: 13, state: 'started' })

    await expect(waiting).rejects.toBeInstanceOf(ButtonFieldDispatchJobDropped)
  })
})
