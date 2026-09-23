import { ButtonFieldDispatchJobType } from '@baserow/modules/database/jobTypes'

describe('ButtonFieldDispatchJobType', () => {
  const type = new ButtonFieldDispatchJobType({ app: {} })

  test('a finished job resolves the click waiting on it', async () => {
    const waiting = ButtonFieldDispatchJobType.waitFor({ id: 7 })
    const done = { id: 7, state: 'finished', results: [], client_actions: [] }

    await type.afterUpdate({ id: 7 }, done)

    await expect(waiting).resolves.toEqual(done)
  })

  test('a failed job rejects the click waiting on it', async () => {
    const waiting = ButtonFieldDispatchJobType.waitFor({ id: 8 })
    const failed = { id: 8, state: 'failed', human_readable_error: 'nope' }

    await type.afterUpdate({ id: 8 }, failed)

    await expect(waiting).rejects.toEqual(failed)
  })

  test('an update that is not final leaves the click waiting', async () => {
    let settled = false
    ButtonFieldDispatchJobType.waitFor({ id: 9 }).finally(() => {
      settled = true
    })

    await type.afterUpdate({ id: 9 }, { id: 9, state: 'started' })
    await Promise.resolve()

    expect(settled).toBe(false)
  })

  test('two clicks polling at once each get their own outcome', async () => {
    const first = ButtonFieldDispatchJobType.waitFor({ id: 10 })
    const second = ButtonFieldDispatchJobType.waitFor({ id: 11 })

    await type.afterUpdate(
      { id: 11 },
      { id: 11, state: 'finished', results: [] }
    )
    await type.afterUpdate({ id: 10 }, { id: 10, state: 'failed' })

    await expect(second).resolves.toMatchObject({ id: 11 })
    await expect(first).rejects.toMatchObject({ id: 10 })
  })
})
