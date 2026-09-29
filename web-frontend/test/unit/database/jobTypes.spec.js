import { vi } from 'vitest'
import {
  ButtonFieldDispatchJobDropped,
  ButtonFieldDispatchJobType,
  DISPATCH_JOB_DEADLINE_MS,
} from '@baserow/modules/database/jobTypes'

describe('ButtonFieldDispatchJobType', () => {
  const store = { dispatch: vi.fn() }
  const type = new ButtonFieldDispatchJobType({ app: { $store: store } })

  beforeEach(() => store.dispatch.mockClear())

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

  test('a waited job is left for its click to remove', async () => {
    ButtonFieldDispatchJobType.waitFor({ id: 14 })
    const done = { id: 14, state: 'finished' }

    await type.afterUpdate(done, done)

    expect(store.dispatch).not.toHaveBeenCalled()
  })

  test('a job no click waits on is removed once it ends', async () => {
    const failed = { id: 15, state: 'failed' }

    await type.afterUpdate(failed, failed)

    expect(store.dispatch).toHaveBeenCalledWith('job/forceDelete', failed)
  })

  test('a job no click waits on stays while it runs', async () => {
    const started = {
      id: 16,
      state: 'started',
      created_on: new Date().toISOString(),
    }

    await type.afterUpdate(started, started)

    expect(store.dispatch).not.toHaveBeenCalled()
  })

  test('a job no click waits on is removed once past the deadline', async () => {
    const started = {
      id: 17,
      state: 'started',
      created_on: new Date(
        Date.now() - DISPATCH_JOB_DEADLINE_MS - 1000
      ).toISOString(),
    }

    await type.afterUpdate(started, started)

    expect(store.dispatch).toHaveBeenCalledWith('job/forceDelete', started)
  })

  test('a started copy of a job its click already settled counts as ended', async () => {
    ButtonFieldDispatchJobType.waitFor({ id: 18 })
    const done = { id: 18, state: 'finished' }
    await type.afterUpdate(done, done)

    const late = {
      id: 18,
      type: 'button_field_dispatch',
      state: 'started',
      field_id: 2,
      row_id: 1,
      created_on: new Date().toISOString(),
    }

    expect(ButtonFieldDispatchJobType.isRunningOn(late, 2, 1)).toBe(false)
  })

  test('a job removed from the store drops the click waiting on it', async () => {
    const waiting = ButtonFieldDispatchJobType.waitFor({ id: 13 })

    type.beforeDelete({ id: 13, state: 'started' })

    await expect(waiting).rejects.toBeInstanceOf(ButtonFieldDispatchJobDropped)
  })
})
