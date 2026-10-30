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
  let testApp, store, type, api, realtime
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
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'Date'] })
    testApp = new TestApp()
    testApp.authenticate({ id: 1, first_name: 'Test' })
    store = testApp.store
    type = new FakeChatRunType({ app: testApp.getApp() })
    testApp.getRegistry().register('chatRunType', type)
    api = {
      get: vi.fn().mockResolvedValue({ status: 'running' }),
      cancel: vi.fn().mockResolvedValue({ status: 'running' }),
      stream: vi.fn().mockResolvedValue(),
    }
    service.mockReturnValue(api)
    realtime = Object.assign(store.app.$realtime, {
      connected: true,
      socket: {},
    })
    vi.spyOn(realtime, 'subscribe').mockImplementation(() => {})
    vi.spyOn(realtime, 'unsubscribe').mockImplementation(() => {})
  })
  afterEach(async () => {
    Object.assign(realtime, { connected: false, socket: null })
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
    await vi.advanceTimersByTimeAsync(15000)
    expect(current()).toMatchObject({
      finished: true,
      view: { text: 'Complete answer' },
    })
  })

  test('an explicit reset rebuilds output, keeps the run status and never fires a live effect', async () => {
    await follow()
    await accept(record('8', 'run.started'))
    await accept(record('9', 'run.cancel_requested'))
    await accept(record('10', 'text.delta', { segment: 0, text: 'Old' }))
    await accept({
      ...record('11', 'text.delta', { segment: 1, text: 'Baseline' }),
      cursor: 'other:11-0',
      reset: true,
    })
    expect(current().view).toMatchObject({
      text: 'Baseline',
      status: 'running',
      cancelRequested: true,
    })
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
        'run.baseline',
        { segment: 1, text: 'Baseline' },
        { replayed: true }
      )
    )
    expect(current().view.text).toBe('Baseline')
    expect(current().replayUnavailable).toBe(false)
    expect(type.onEvent.mock.calls.at(-1)[2]).toBe(false)
  })

  test('an open stream is the only status source while it sends heartbeats', async () => {
    await follow({ controller: new AbortController() })
    for (let second = 5; second <= 60; second += 5) {
      await vi.advanceTimersByTimeAsync(5000)
      await accept({ kind: 'run.heartbeat', data: {}, cursor: null })
    }
    await store.dispatch('chatRuns/handleChanged', {
      runId: 'run',
      runType: 'fake',
      chatId: 1,
    })
    await store.dispatch('chatRuns/cancelRun', 'run')
    expect(api.get).not.toHaveBeenCalled()
    expect(type.onEvent).not.toHaveBeenCalled()

    // Without output to stream, a change is read from the saved run.
    await accept({ kind: 'run.replay_unavailable', data: {} })
    await flushPromises()
    await store.dispatch('chatRuns/handleChanged', {
      runId: 'run',
      runType: 'fake',
      chatId: 1,
    })
    expect(api.get).toHaveBeenCalledTimes(2)
  })

  test('a silent stream reconnects, also after the computer slept', async () => {
    type.openStream.mockImplementation(
      (follower, onRecord, signal) =>
        new Promise((resolve, reject) =>
          signal.addEventListener('abort', () => reject(new Error('closed')))
        )
    )
    await follow({ attach: true })
    await flushPromises()
    expect(api.get).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(15000)
    expect(type.openStream).toHaveBeenCalledTimes(2)
    expect(api.get).toHaveBeenCalledOnce()

    vi.setSystemTime(Date.now() + 20000)
    await store.dispatch('chatRuns/resumeFollowers')
    await flushPromises()
    expect(type.openStream).toHaveBeenCalledTimes(3)
  })

  test('the default follower reads the run after its cursor', async () => {
    await follow()
    await accept(record('10', 'text.delta', { segment: 0, text: 'Hi' }))
    const onRecord = vi.fn()
    const { signal } = new AbortController()
    new ChatRunType({ app: testApp.getApp() }).openStream(
      current(),
      onRecord,
      signal
    )
    expect(api.stream).toHaveBeenCalledWith(
      'run',
      'generation:10-0',
      onRecord,
      signal
    )
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
    await vi.advanceTimersByTimeAsync(15000)
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

  test('a stream refused for lack of capacity is retried with the next status check', async () => {
    type.openStream.mockRejectedValue({ response: { status: 503 } })
    await follow({ attach: true })
    await flushPromises()
    expect(type.openStream).toHaveBeenCalledTimes(1)
    expect(api.get).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(5000)
    expect(api.get).toHaveBeenCalledTimes(1)
    expect(type.openStream).toHaveBeenCalledTimes(2)
  })

  test('lifecycle and subscription confirmations do not renew an exhausted reconnect budget', async () => {
    type.openStream.mockRejectedValue(new Error('offline'))
    await store.dispatch('chatRuns/subscribeToChat', {
      runType: 'fake',
      chatId: 1,
    })
    await follow({ attach: true })
    await flushPromises()
    expect(type.openStream).toHaveBeenCalledTimes(3)
    for (let i = 0; i < 3; i++) {
      await store.dispatch('chatRuns/handleChanged', {
        runId: 'run',
        runType: 'fake',
        chatId: 1,
      })
      realtime.socket = {}
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

  test('focus resumes followers whose stream ended without re-reading their chat', async () => {
    type.openStream.mockRejectedValue(new Error('offline'))
    type.refreshChat = vi.fn()
    await follow({ attach: true })
    await follow({ runId: 'live', controller: new AbortController() })
    await flushPromises()
    expect(type.openStream).toHaveBeenCalledTimes(3)
    await store.dispatch('chatRuns/resumeFollowers')
    await flushPromises()
    expect(type.openStream).toHaveBeenCalledTimes(6)
    expect(
      type.openStream.mock.calls.map(([{ runId }]) => runId)
    ).not.toContain('live')
    expect(type.refreshChat).not.toHaveBeenCalled()
  })

  describe('chat subscriptions', () => {
    const subscribe = (chatId, runType = 'fake') =>
      store.dispatch('chatRuns/subscribeToChat', { runType, chatId })
    const confirm = (chatId) =>
      store.dispatch('chatRuns/handlePageAdd', {
        run_type: 'fake',
        chat_id: chatId,
      })

    beforeEach(() => {
      type.refreshChat = vi.fn()
    })

    test('a confirmation re-reads the chat only after a websocket reconnect', async () => {
      await subscribe(1)
      await follow()
      await confirm(1)
      await confirm(2)
      expect(type.refreshChat).not.toHaveBeenCalled()

      realtime.socket = {}
      await confirm(1)
      await confirm(1)
      expect(type.refreshChat).toHaveBeenCalledExactlyOnceWith(1)
      expect(api.get).toHaveBeenCalledExactlyOnceWith('run')
    })

    test('a subscription sent while disconnected re-reads the chat once confirmed', async () => {
      realtime.connected = false
      await subscribe(1)
      realtime.connected = true
      await confirm(1)
      expect(type.refreshChat).toHaveBeenCalledExactlyOnceWith(1)
    })

    test('each run type keeps one subscription until its owner releases it', async () => {
      await subscribe(1)
      await subscribe(2)
      await subscribe(1, 'other')
      await store.dispatch('chatRuns/unsubscribeFromChat', {
        runType: 'fake',
        chatId: 1,
      })
      expect(store.state.chatRuns.subscriptions).toEqual({ fake: 2, other: 1 })

      await store.dispatch('chatRuns/unsubscribeFromChat', {
        runType: 'fake',
        chatId: 2,
      })
      expect(store.state.chatRuns.subscriptions).toEqual({ other: 1 })
      expect(realtime.unsubscribe.mock.calls).toEqual([
        ['chat_runs', { run_type: 'fake', chat_id: 1 }],
        ['chat_runs', { run_type: 'fake', chat_id: 2 }],
      ])
    })
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
