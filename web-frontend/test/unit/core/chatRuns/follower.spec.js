import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { TestApp } from '@baserow/test/helpers/testApp'
import { ChatRunType } from '@baserow/modules/core/chatRuns/chatRunType'
import service from '@baserow/modules/core/services/chatRuns'
import { compareCursors } from '@baserow/modules/core/chatRuns/cursor'

vi.mock('@baserow/modules/core/services/chatRuns', () => ({ default: vi.fn() }))

class FakeChatRunType extends ChatRunType {
  static getType() {
    return 'fake'
  }
  onEvent = vi.fn()
  openStream = vi.fn(() => new Promise(() => {}))
}

const record = (cursor, kind, data = {}, metadata = {}) => ({
  cursor: `generation:${cursor}-0`,
  kind,
  data,
  ...metadata,
})

describe('core HTTP run follower without a product adapter', () => {
  let testApp, store, type, api
  const current = () => store.getters['chatRuns/getFollower']('run')
  const accept = (value) =>
    store.dispatch('chatRuns/acceptRecord', { runId: 'run', record: value })
  const follow = (options = {}) =>
    store.dispatch('chatRuns/follow', {
      runId: 'run',
      runType: 'fake',
      chatId: 1,
      attach: false,
      ...options,
    })

  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    testApp = new TestApp()
    testApp.authenticate({ id: 1, first_name: 'Test' })
    store = testApp.store
    type = new FakeChatRunType({ app: testApp.getApp() })
    testApp.getRegistry().register('chatRunType', type)
    api = {
      get: vi.fn().mockResolvedValue({ status: 'running' }),
      cancel: vi.fn().mockResolvedValue({ status: 'running' }),
    }
    service.mockReturnValue(api)
  })
  afterEach(async () => {
    await store.dispatch('chatRuns/disconnect')
    testApp.getRegistry().unregister('chatRunType', 'fake')
    await testApp.afterEach()
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  test('folds Redis order with non-consecutive IDs and ignores duplicate/older records', async () => {
    await follow()
    await accept(record('10', 'text.delta', { segment: 0, text: 'Hello' }))
    await accept(record('51', 'text.delta', { segment: 0, text: ' there' }))
    await accept(record('51', 'text.delta', { segment: 0, text: ' duplicate' }))
    await accept(record('10', 'text.delta', { segment: 0, text: ' old' }))
    expect(current().view.text).toBe('Hello there')
    expect(type.onEvent).toHaveBeenCalledTimes(2)
    expect(current().cursor).toBe('generation:51-0')
  })

  test('unknown events advance the cursor and replay has no live effects', async () => {
    await follow()
    await accept(record('10', 'future.kind', {}, { replay: true }))
    expect(current().cursor).toBe('generation:10-0')
    expect(type.onEvent).toHaveBeenLastCalledWith(
      current(),
      expect.objectContaining({ kind: 'future.kind' }),
      false
    )
  })

  test('an unexpected generation preserves known text and waits for the durable result', async () => {
    await follow({ controller: new AbortController() })
    await accept(record('10', 'text.delta', { segment: 0, text: 'Known' }))
    await accept({
      ...record('11', 'text.delta', { segment: 0, text: ' suffix' }),
      cursor: 'other:11-0',
    })
    await flushPromises()
    expect(current()).toMatchObject({
      replayUnavailable: true,
      view: { text: 'Known' },
    })
    expect(type.openStream).not.toHaveBeenCalled()
    api.get.mockResolvedValue({
      status: 'completed',
      message: { id: 9, content: 'Complete answer' },
    })
    await vi.advanceTimersByTimeAsync(5000)
    expect(current()).toMatchObject({
      finished: true,
      view: { text: 'Complete answer' },
    })
  })

  test('an explicit reset replaces state and never fires a live effect', async () => {
    await follow()
    await accept(record('10', 'text.delta', { segment: 0, text: 'Old' }))
    await accept({
      ...record('11', 'text.delta', { segment: 1, text: 'Baseline' }),
      cursor: 'other:11-0',
      reset: true,
    })
    expect(current().view.text).toBe('Baseline')
    expect(type.onEvent.mock.calls.at(-1)[2]).toBe(false)
  })

  test('a baseline may reuse the submitted cursor and unavailable suffixes are ignored', async () => {
    await follow({ controller: new AbortController() })
    await accept(record('10', 'text.delta', { segment: 0, text: 'Known' }))
    await accept({ kind: 'run.replay_unavailable', data: {} })
    await accept(
      record('11', 'text.delta', { segment: 0, text: ' invalid tail' })
    )
    expect(current().view.text).toBe('Known')
    await accept(
      record(
        '10',
        'text.delta',
        { segment: 1, text: 'Baseline' },
        { reset: true, replay: true }
      )
    )
    expect(current().view.text).toBe('Baseline')
    expect(current().replayUnavailable).toBe(false)
    expect(type.onEvent.mock.calls.at(-1)[2]).toBe(false)
  })

  test('adopting the original response closes a racing discovery follower without reconnecting it', async () => {
    type.openStream.mockImplementation(
      (follower, onRecord, signal) =>
        new Promise((resolve, reject) => {
          signal.addEventListener('abort', () => reject(new Error('closed')))
        })
    )
    await follow({ attach: true })
    await flushPromises()
    const discovered = type.openStream.mock.calls[0][2]
    const original = new AbortController()
    await follow({ controller: original })
    await flushPromises()
    expect(discovered.aborted).toBe(true)
    expect(original.signal.aborted).toBe(false)
    expect(current().streaming).toBe(true)
    expect(type.openStream).toHaveBeenCalledTimes(1)
  })

  test('missing Redis completion recovers the primary saved result and late output cannot change it', async () => {
    const controller = new AbortController()
    await follow({ controller })
    await accept(record('10', 'text.delta', { segment: 0, text: 'Partial' }))
    const message = { id: 9, content: 'Saved' }
    api.get.mockResolvedValue({ status: 'completed', error_code: '', message })
    await vi.advanceTimersByTimeAsync(5000)
    await accept(record('11', 'text.delta', { segment: 0, text: ' Late' }))
    expect(current()).toMatchObject({
      finished: true,
      view: { message, text: 'Saved' },
    })
    expect(controller.signal.aborted).toBe(true)
  })

  test('reconnect is read-only, bounded, and durable checks keep running after retries stop', async () => {
    type.openStream.mockRejectedValue(new Error('offline'))
    await follow({ attach: true })
    await flushPromises()
    await vi.advanceTimersByTimeAsync(20000)
    expect(type.openStream).toHaveBeenCalledTimes(3)
    expect(api.get.mock.calls.length).toBeGreaterThan(3)
    api.get.mockResolvedValue({
      status: 'failed',
      error_code: 'interrupted',
      message: null,
    })
    await vi.advanceTimersByTimeAsync(5000)
    expect(current()).toMatchObject({
      finished: true,
      view: { status: 'failed', errorCode: 'interrupted' },
    })
  })

  test('lifecycle and subscription confirmations do not renew an exhausted reconnect budget', async () => {
    type.openStream.mockRejectedValue(new Error('offline'))
    await follow({ attach: true })
    await flushPromises()
    expect(type.openStream).toHaveBeenCalledTimes(3)
    for (let i = 0; i < 3; i++) {
      await store.dispatch('chatRuns/handleChanged', {
        runId: 'run',
        runType: 'fake',
        chatId: 1,
      })
      await store.dispatch('chatRuns/handlePageAdd', {
        run_type: 'fake',
        chat_id: 1,
      })
      await follow({ attach: true })
      await flushPromises()
    }
    expect(type.openStream).toHaveBeenCalledTimes(3)
    expect(current().finished).toBe(false)
  })

  test('Stop is run-scoped and remains usable with unavailable output', async () => {
    await follow()
    await accept({ kind: 'run.replay_unavailable', data: {} })
    await store.dispatch('chatRuns/cancelRun', 'run')
    await store.dispatch('chatRuns/cancelRun', 'run')
    expect(api.cancel).toHaveBeenCalledExactlyOnceWith('run')
    expect(current().stopRequested).toBe(true)
  })

  test('the bounded outcome cache keeps active and protected runs and resolves an evicted terminal waiter', async () => {
    await follow()
    const waiting = store.dispatch('chatRuns/waitUntilFinished', 'run')
    type.shouldRetainFollower = (follower) => follower.runId === 'handoff'
    for (const runId of [
      'handoff',
      ...Array.from({ length: 20 }, (_, i) => `finished-${i}`),
    ]) {
      await follow({ runId })
      await store.dispatch('chatRuns/applySnapshot', {
        runId,
        snapshot: { status: 'completed' },
      })
    }
    await follow({ runId: 'active' })

    await store.dispatch('chatRuns/applySnapshot', {
      runId: 'run',
      snapshot: { status: 'completed' },
    })
    await waiting

    expect(current()).toBeNull()
    expect(store.getters['chatRuns/getFollower']('active').finished).toBe(false)
    expect(store.getters['chatRuns/getFollower']('handoff').finished).toBe(true)
    expect(Object.keys(store.state.chatRuns.followers)).toHaveLength(22)
  })

  test('disconnect and reactivation discard old status and queued records without disturbing the new follower', async () => {
    const oldController = new AbortController()
    await follow({ controller: oldController })
    let oldStatus, newStatus
    api.get
      .mockImplementationOnce(
        () => new Promise((resolve) => (oldStatus = resolve))
      )
      .mockImplementationOnce(
        () => new Promise((resolve) => (newStatus = resolve))
      )
    const oldCheck = store.dispatch('chatRuns/checkStatus', 'run')
    await store.dispatch('chatRuns/disconnect')
    await accept(record('1', 'text.delta', { segment: 0, text: 'Suspended' }))
    expect(current().view.text).toBe('')

    const controller = new AbortController()
    await follow({ controller })
    const newCheck = store.dispatch('chatRuns/checkStatus', 'run')
    oldStatus({ status: 'completed', message: { id: 9, content: 'Old' } })
    await oldCheck
    await store.dispatch('chatRuns/acceptRecord', {
      runId: 'run',
      record: record('2', 'text.delta', { segment: 0, text: 'Old connection' }),
      controller: oldController,
    })
    expect(current()).toMatchObject({
      finished: false,
      checkingStatus: true,
      view: { text: '' },
    })
    expect(controller.signal.aborted).toBe(false)
    expect(type.onEvent).not.toHaveBeenCalled()

    newStatus({ status: 'running' })
    await newCheck
    await store.dispatch('chatRuns/acceptRecord', {
      runId: 'run',
      record: record('3', 'text.delta', { segment: 0, text: 'Current' }),
      controller,
    })
    expect(current()).toMatchObject({
      checkingStatus: false,
      view: { status: 'running', text: 'Current' },
    })
  })

  test('signed-out tabs close their followers and stop checking status', async () => {
    const controller = new AbortController()
    await follow({ controller })
    store.commit('auth/LOGOFF')
    await vi.advanceTimersByTimeAsync(15000)
    expect(controller.signal.aborted).toBe(true)
    expect(api.get).not.toHaveBeenCalled()
  })

  test('cursor ordering preserves decimal precision', () => {
    expect(
      compareCursors('g:99999999999999999-2', 'g:99999999999999998-99')
    ).toBe(1)
    expect(compareCursors('g:8-10', 'g:8-9')).toBe(1)
    expect(compareCursors('g:8-1', 'other:8-1')).toBeNull()
  })
})
