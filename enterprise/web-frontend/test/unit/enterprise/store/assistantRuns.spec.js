import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import assistantService from '@baserow_enterprise/services/assistant'
import coreService from '@baserow/modules/core/services/chatRuns'
import {
  createRunsTestApp,
  destroyRunsTestApp,
  cursor,
  runRecord,
  followRun,
  acceptRecord,
  applySnapshot,
} from '../assistantRunHelpers'
import {
  getStoredChatUuid,
  getTabId,
  storeChatUuid,
} from '@baserow_enterprise/utils/assistantTabStorage'
import { SEND_OUTCOME } from '@baserow_enterprise/store/assistant'

vi.mock('@baserow_enterprise/services/assistant', () => ({ default: vi.fn() }))
vi.mock('@baserow/modules/core/services/chatRuns', () => ({ default: vi.fn() }))

const workspace = { id: 1, name: 'Test workspace' }
const uuid = '11111111-1111-4111-8111-111111111111'
const human = { type: 'human', id: 501, content: 'Hi' }
const answer = { type: 'ai/message', id: 502, content: 'Hello' }
const refused = (status, code) =>
  Object.assign(new Error('Refused'), {
    response: { status },
    handler: {
      code,
      detail: 'Refused.',
      isTooManyRequests: () => status === 429,
      hasRequestBodyValidationError: () =>
        code === 'ERROR_REQUEST_BODY_VALIDATION',
    },
  })

describe('Kuma durable streamed send and resume', () => {
  let testApp, store, service, api, receive, finish, fail
  const send = () =>
    store.dispatch('assistant/sendMessage', { message: 'Hi', workspace })
  const follower = () => store.getters['chatRuns/getFollower']('run-1')
  const emit = (type, values, metadata) =>
    receive(runRecord(type, values, metadata))
  async function open(active = null) {
    store.commit('assistant/SET_CHATS', [{ uuid, chat_id: 7, title: '' }])
    service.fetchChatMessages.mockResolvedValue({
      chat_id: 7,
      messages: active ? [human] : [],
      active_run: active,
    })
    await store.dispatch('assistant/selectChat', store.state.assistant.chats[0])
    await flushPromises()
  }
  function restoreAfterReload(readChat) {
    storeChatUuid(uuid)
    store.commit('assistant/SET_CHATS', [{ uuid, chat_id: 7, title: '' }])
    service.fetchChatMessages.mockImplementation(readChat)
    return store.dispatch('assistant/restoreOpenChat')
  }
  const rereadChat = (refresh) =>
    refresh === 'reopen'
      ? store.dispatch('assistant/selectChat', store.state.assistant.chats[0])
      : store.dispatch('assistant/refreshCurrentChat')
  beforeEach(async () => {
    testApp = createRunsTestApp()
    store = testApp.store
    service = {
      fetchChats: vi.fn().mockResolvedValue({ results: [] }),
      fetchChatMessages: vi
        .fn()
        .mockResolvedValue({ chat_id: 7, messages: [] }),
      sendMessage: vi.fn((...args) => {
        receive = args[3]
        return new Promise((resolve, reject) => {
          finish = resolve
          fail = reject
        })
      }),
      resumeMessage: vi.fn(() => new Promise(() => {})),
    }
    assistantService.mockReturnValue(service)
    api = {
      get: vi.fn().mockResolvedValue({ status: 'running' }),
    }
    coreService.mockReturnValue(api)
    await store.dispatch('workspace/forceCreate', workspace)
    await store.dispatch('undoRedo/updateCurrentScopeSet', { workspace: 1 })
  })
  afterEach(() => destroyRunsTestApp(testApp))

  test('uses the original message POST response and stays followed when the panel is reset', async () => {
    const sending = send()
    await flushPromises()
    await emit('human', human, { cursor: cursor(1), status: 'queued' })
    expect(service.sendMessage).toHaveBeenCalledWith(
      expect.any(String),
      'Hi',
      expect.any(Object),
      expect.any(Function),
      expect.objectContaining({ tabId: getTabId() })
    )
    expect(service.resumeMessage).not.toHaveBeenCalled()
    expect(follower()).toMatchObject({
      chatId: 7,
      streaming: true,
      finished: false,
    })
    expect(store.state.assistant.messages.map((m) => m.id)).toEqual([501])
    await store.dispatch('assistant/reset')
    expect(follower().finished).toBe(false)
    await emit('ai/message', answer, { cursor: cursor(2), status: 'completed' })
    finish()
    expect(await sending).toBe(SEND_OUTCOME.ACCEPTED)
  })

  test('refresh attaches read-only to the same endpoint by run/cursor without sending content', async () => {
    await open({ id: 'run-1', status: 'running' })
    expect(service.sendMessage).not.toHaveBeenCalled()
    expect(service.resumeMessage).toHaveBeenCalledWith(
      uuid,
      'run-1',
      null,
      expect.any(Function),
      expect.objectContaining({ tabId: getTabId() })
    )
    expect(store.getters['assistant/messages'].map((m) => m.id)).toEqual([
      501,
      'run-run-1',
    ])
  })

  test.each(['reopen', 'focus'])(
    '%s keeps current feedback from history instead of the finished follower snapshot',
    async (refresh) => {
      await open()
      await followRun(store)
      await applySnapshot(store, {
        status: 'completed',
        message: { ...answer, human_sentiment: null },
      })
      const ratedAnswer = { ...answer, human_sentiment: 'Good' }
      service.fetchChatMessages.mockResolvedValue({
        chat_id: 7,
        messages: [human, ratedAnswer],
        active_run: null,
        latest_run: {
          id: 'run-1',
          status: 'completed',
          message: ratedAnswer,
        },
      })

      await rereadChat(refresh)

      expect(
        store.getters['assistant/messages'].map((message) => message.id)
      ).toEqual([human.id, answer.id])
      expect(store.getters['assistant/messages'].at(-1).human_sentiment).toBe(
        'Good'
      )
      expect(service.resumeMessage).not.toHaveBeenCalled()
    }
  )

  test('history restores the durable chat title without a live Redis title event', async () => {
    await open()
    service.fetchChatMessages.mockResolvedValue({
      chat_id: 7,
      chat_title: 'A useful title',
      messages: [human, answer],
      active_run: null,
    })

    await store.dispatch('assistant/refreshCurrentChat')

    expect(store.getters['assistant/currentChat'].title).toBe('A useful title')
  })

  test('a late title goes to the chat it was generated for', async () => {
    send()
    await flushPromises()
    const firstChatId = store.getters['assistant/currentChatId']
    await store.dispatch('assistant/clearChat')
    await store.dispatch('assistant/createChat', workspace.id)
    await emit('chat/title', { content: 'First title' }, { cursor: cursor(1) })

    const chats = store.getters['assistant/chats']
    expect(chats.find((c) => c.id === firstChatId).title).toBe('First title')
    expect(store.getters['assistant/currentChat'].title).toBe('')
  })

  test.each([
    ['reopen', false],
    ['focus', false],
    ['reopen', true],
  ])(
    'a final response racing the history read on %s (live output lost: %s) still inserts the saved answer once',
    async (refresh, outputLost) => {
      const active = { id: 'run-1', status: 'running' }
      await open(active)
      if (outputLost) {
        await acceptRecord(
          store,
          runRecord('chat-run-state', {}, { replay_unavailable: true })
        )
      }
      await applySnapshot(store, { status: 'completed', message: answer })

      // This response captured the turn before the worker's final commit.
      service.fetchChatMessages.mockResolvedValue({
        chat_id: 7,
        messages: [human],
        active_run: active,
      })
      await rereadChat(refresh)

      expect(
        store.getters['assistant/messages'].map((message) => message.id)
      ).toEqual([human.id, answer.id])
    }
  )

  test('a terminal resume header waits for the saved answer instead of completing with partial text', async () => {
    await open({ id: 'run-1', status: 'running' })
    await acceptRecord(
      store,
      runRecord('ai/reasoning', { content: 'Partial' }, { cursor: cursor(1) })
    )

    // The worker finished between the status read and the resume request.
    await acceptRecord(
      store,
      runRecord('chat-run-state', {}, { status: 'completed' })
    )
    await flushPromises()
    expect(follower().finished).toBe(false)
    await acceptRecord(
      store,
      runRecord('ai/message', answer, { status: 'completed' })
    )

    expect(store.getters['assistant/messages'].at(-1)).toMatchObject(answer)
  })

  test('an outcome without a saved message is recovered and stays shown while its run is the latest', async () => {
    await open({ id: 'run-1', status: 'running' })
    api.get.mockResolvedValue({
      status: 'failed',
      error_code: 'interrupted',
      message: null,
    })

    await acceptRecord(
      store,
      runRecord('chat-run-state', {}, { status: 'failed' })
    )
    await flushPromises()
    const outcome = {
      content: '',
      run_status: 'failed',
      error_code: 'interrupted',
    }
    expect(store.getters['assistant/messages'].at(-1)).toMatchObject(outcome)

    service.fetchChatMessages.mockResolvedValue({
      chat_id: 7,
      messages: [human],
      latest_run: { id: 'run-1', status: 'failed', message: null },
    })
    await rereadChat('reopen')
    expect(store.getters['assistant/messages'].at(-1)).toMatchObject(outcome)

    const later = { id: 504, type: 'ai/message', content: 'Done' }
    service.fetchChatMessages.mockResolvedValue({
      chat_id: 7,
      messages: [human, { id: 503, type: 'human', content: 'Again' }, later],
      latest_run: { id: 'run-2', status: 'completed', message: later },
    })
    await rereadChat('reopen')
    expect(
      store.getters['assistant/messages'].map((message) => message.id)
    ).toEqual([501, 503, 504])
  })

  test('connection loss after metadata reconnects from the applied cursor and never resends the prompt', async () => {
    const sending = send()
    await flushPromises()
    await emit('human', human, { cursor: cursor(1) })
    await emit('ai/reasoning', { content: 'Part' }, { cursor: cursor(2) })
    fail(new Error('offline'))
    await flushPromises()
    expect(service.sendMessage).toHaveBeenCalledTimes(1)
    expect(service.resumeMessage).toHaveBeenCalledWith(
      expect.any(String),
      'run-1',
      cursor(2),
      expect.any(Function),
      expect.any(Object)
    )
    api.get.mockResolvedValue({ status: 'completed', message: answer })
    await vi.advanceTimersByTimeAsync(5000)
    expect(await sending).toBe(SEND_OUTCOME.ACCEPTED)
    expect(store.getters['assistant/messages'].at(-1).content).toBe('Hello')
  })

  test('logout before run identity closes the original response and rejects its late records after signing in again', async () => {
    const sending = send()
    await flushPromises()
    const { signal } = service.sendMessage.mock.calls[0][4]
    store.commit('auth/LOGOFF')
    expect(signal.aborted).toBe(true)
    testApp.authenticate({ id: 1, first_name: 'Test' })

    await emit('human', human, { cursor: cursor(1) })
    expect(follower()).toBeNull()
    fail(Object.assign(new Error('closed'), { cancelled: true }))

    expect(await sending).toBe(SEND_OUTCOME.FAILED)
    expect(service.fetchChatMessages).not.toHaveBeenCalled()
    expect(service.resumeMessage).not.toHaveBeenCalled()
  })

  test('early loss recovers committed identity from JSON history without a second send', async () => {
    const sending = send()
    await flushPromises()
    service.fetchChatMessages.mockResolvedValue({
      chat_id: 7,
      messages: [human],
      active_run: { id: 'run-1', status: 'running', human_message_id: 501 },
    })
    fail(new Error('offline before metadata'))
    await flushPromises()
    expect(service.sendMessage).toHaveBeenCalledTimes(1)
    expect(service.resumeMessage).toHaveBeenCalledTimes(1)
    api.get.mockResolvedValue({ status: 'completed', message: answer })
    await vi.advanceTimersByTimeAsync(5000)
    expect(await sending).toBe(SEND_OUTCOME.ACCEPTED)
  })

  test.each([
    [409, 'ERROR_CHAT_RUN_IN_PROGRESS', SEND_OUTCOME.BUSY, null],
    [429, 'ERROR_CHAT_STREAM_USER_LIMIT', SEND_OUTCOME.ACCEPTED, 'run-1'],
  ])(
    'a %i %s drops the draft and follows the run the chat already has',
    async (status, code, outcome, runId) => {
      await open()
      service.sendMessage.mockRejectedValue(refused(status, code))
      service.fetchChatMessages.mockResolvedValue({
        chat_id: 7,
        messages: [human],
        active_run: { id: 'run-1', status: 'running' },
      })
      expect(
        await store.dispatch('assistant/startRun', { message: 'Hi', workspace })
      ).toEqual({ outcome, runId })
      await flushPromises()
      expect(store.state.assistant.messages.map((m) => m.id)).toEqual([501])
      expect(service.resumeMessage).toHaveBeenCalledTimes(1)
    }
  )

  test.each([
    [404, 'ERROR_ASSISTANT_CHAT_DOES_NOT_EXIST', null],
    [503, null, uuid],
  ])(
    'a reload whose chat read fails with %i %s keeps %s as the tab chat',
    async (status, code, kept) => {
      await restoreAfterReload(() => Promise.reject(refused(status, code)))
      expect(getStoredChatUuid()).toBe(kept)
    }
  )

  test('a reload read that ends after the user starts a new chat leaves it open', async () => {
    let read
    const restoring = restoreAfterReload(
      () => new Promise((resolve) => (read = resolve))
    )
    const newChat = await store.dispatch('assistant/createChat')
    read({ chat_id: 7, messages: [human] })
    await restoring
    expect(store.state.assistant.currentChatId).toBe(newChat)
    expect(store.state.assistant.messages).toEqual([])
  })

  test.each([
    [429, 'ERROR_CHAT_RUN_LIMIT', 'assistant.runLimitReached'],
    [400, 'ERROR_REQUEST_BODY_VALIDATION', 'assistant.runMessageTooLong'],
    [400, 'ERROR_ASSISTANT_MODEL_DISABLED', 'Refused.'],
  ])('a %i %s refusal reads as %s', async (status, code, content) => {
    await open()
    service.sendMessage.mockRejectedValue(refused(status, code))
    expect(await send()).toBe(SEND_OUTCOME.FAILED)
    expect(store.getters['assistant/messages'].at(-1)).toMatchObject({
      content,
      error: true,
    })
    await flushPromises()
    expect(store.getters['assistant/currentChat'].running).toBe(false)
  })

  test('refreshing the chat keeps a refused prompt and its explanation', async () => {
    await open()
    service.sendMessage.mockRejectedValue(refused(429, 'ERROR_CHAT_RUN_LIMIT'))
    await send()
    await store.dispatch('assistant/refreshCurrentChat')
    expect(store.getters['assistant/messages'].map((m) => m.content)).toEqual([
      'Hi',
      'assistant.runLimitReached',
    ])
  })

  test('a bug while recovering a lost send surfaces instead of a refusal', async () => {
    const sending = send()
    await flushPromises()
    const bug = new Error('bug')
    service.fetchChatMessages.mockRejectedValue(bug)
    fail(new Error('offline'))
    await expect(sending).rejects.toBe(bug)
  })

  test('early loss never associates the send with a later run from another tab', async () => {
    const sending = send()
    await flushPromises()
    service.fetchChatMessages.mockResolvedValue({
      chat_id: 7,
      messages: [
        human,
        answer,
        { id: 503, type: 'human', content: 'Another prompt' },
      ],
      active_run: { id: 'other-run', status: 'running', human_message_id: 503 },
    })
    fail(new Error('lost identity'))
    expect(await sending).toBe(SEND_OUTCOME.FAILED)
    expect(service.sendMessage).toHaveBeenCalledTimes(1)
    expect(service.resumeMessage).not.toHaveBeenCalled()
    expect(store.getters['chatRuns/getFollower']('other-run')).toBeNull()
  })
})
