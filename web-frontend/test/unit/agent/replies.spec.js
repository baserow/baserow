import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import service from '@baserow/modules/core/services/chatRuns'
import {
  composer,
  conversation,
  createAgentPage,
  deferredReply,
  destroyAgentPage,
  message,
  messages,
  mockConversations,
  mockMessages,
  mockSendMessage,
  mockStartConversation,
  page,
  runningTurn,
  selectConversation,
  send,
  sendMessage,
  sentBodies,
  stop,
} from './helpers'

vi.mock('@baserow/modules/core/services/chatRuns', () => ({ default: vi.fn() }))

const author = { id: 1, name: 'Ada' }

const savedTurn = (status, errorCode = '', id = 1) => ({
  id,
  status,
  error_code: errorCode,
  run_id: null,
})

const chat = (wrapper) =>
  wrapper
    .findAll(
      '.agent-chat__message-author, .agent-chat__message-content, .agent-chat__notice'
    )
    .map((item) => item.text())

const announcement = (wrapper) =>
  wrapper.get('.agent-chat__announcement[role="status"]').text()

const liveReply = (wrapper) => wrapper.get('.agent-chat__message[aria-live]')

const loadErrorAlert = (wrapper) =>
  wrapper
    .findAll('.alert')
    .find((alert) => alert.text().includes('agent.messagesLoadError'))

const messageRequests = (testApp) =>
  testApp.mock.history.get.filter(({ url }) => url.endsWith('/messages/'))

describe('Agent replies', () => {
  let testApp, mount, api, streams

  beforeEach(async () => {
    ;({ testApp, mount } = await createAgentPage())
    testApp.authenticate({ id: 1, first_name: 'Ada' })
    streams = {}
    api = {
      get: vi.fn().mockResolvedValue({ status: 'running' }),
      cancel: vi.fn().mockResolvedValue({ status: 'running' }),
      stream: vi.fn((runId, cursor, onRecord) => {
        streams[runId] = onRecord
        return new Promise(() => {})
      }),
    }
    service.mockReturnValue(api)
  })

  afterEach(async () => {
    await testApp.store.dispatch('chatRuns/disconnect')
    await destroyAgentPage(testApp)
  })

  async function receive(runId, kind, data, cursor) {
    await streams[runId]({ kind, data, cursor })
    await flushPromises()
  }

  const streamText = (runId, text, cursor = 'a:1-0') =>
    receive(runId, 'text.delta', { segment: 0, text }, cursor)

  const finish = (runId, status) =>
    receive(runId, 'run.finished', { status }, 'a:9-0')

  const withConversation = (...pages) => {
    mockConversations(
      testApp,
      page([conversation('conversation-a', 'Conversation A', undefined, 7)])
    )
    mockMessages(
      testApp,
      'conversation-a',
      ...pages.map((item) => (typeof item === 'function' ? item : page(item)))
    )
  }

  const savedReply =
    (status, errorCode = '', reply = 'Hi there') =>
    () => [
      200,
      page([
        message(sentBodies(testApp)[0].message_uuid, 'Hello', {
          author,
          turn: savedTurn(status, errorCode),
        }),
        message('reply-1', reply, {
          role: 'assistant',
          turn: savedTurn(status, errorCode),
        }),
      ]),
    ]

  async function startReply(refresh) {
    mockStartConversation(testApp, ({ data }) => {
      const body = JSON.parse(data)
      return [
        200,
        {
          conversation: conversation(body.uuid, body.content, undefined, 5),
          message: message(body.message_uuid, body.content, {
            author,
            turn: runningTurn(),
          }),
        },
      ]
    })
    testApp.mock
      .onGet(/\/agent\/10\/conversations\/.+\/messages\//)
      .reply(refresh)
    const wrapper = await mount()
    await sendMessage(wrapper, 'Hello')
    await streamText('run-1', 'Hel')
    return wrapper
  }

  test('streams the reply to a sent message and shows the saved reply once it finishes', async () => {
    const wrapper = await startReply(savedReply('completed'))

    expect(testApp.store.state.chatRuns.subscription).toEqual({
      runType: 'agent',
      chatId: 5,
    })
    expect(api.stream.mock.calls.map(([runId]) => runId)).toEqual(['run-1'])
    expect(document.activeElement).toBe(composer(wrapper).element)
    expect(chat(wrapper)).toEqual(['Ada', 'Hello', 'Support agent', 'Hel'])
    expect(liveReply(wrapper).attributes('aria-busy')).toBe('true')
    expect(announcement(wrapper)).toBe('agent.replying')
    expect(stop(wrapper).attributes('aria-label')).toBe('agent.stop')
    await finish('run-1', 'completed')

    expect(chat(wrapper)).toEqual(['Ada', 'Hello', 'Support agent', 'Hi there'])
    expect(announcement(wrapper)).toBe('')
    expect(send(wrapper).attributes('aria-label')).toBe('agent.send')
  })

  test('keeps the streamed reply until the saved one has loaded', async () => {
    const pending = deferredReply()
    const wrapper = await startReply(pending.reply)

    await finish('run-1', 'completed')

    expect(chat(wrapper)).toEqual(['Ada', 'Hello', 'Support agent', 'Hel'])
    expect(liveReply(wrapper).attributes('aria-busy')).toBe('false')
    expect(send(wrapper).attributes('disabled')).toBeDefined()
    expect(messageRequests(testApp).at(-1).headers).toMatchObject({
      'X-Baserow-Realtime-Recovery': 'true',
    })
    pending.resolve(...savedReply('completed')())
    await flushPromises()
    expect(chat(wrapper)).toEqual(['Ada', 'Hello', 'Support agent', 'Hi there'])
  })

  test('keeps the streamed reply and offers a retry when the saved one fails to load', async () => {
    testApp.dontFailOnErrorResponses()
    let available = false
    const wrapper = await startReply(() =>
      available ? savedReply('completed')() : [500, {}]
    )

    await finish('run-1', 'completed')

    expect(chat(wrapper)).toEqual(['Ada', 'Hello', 'Support agent', 'Hel'])
    available = true
    await loadErrorAlert(wrapper).get('button').trigger('click')
    await flushPromises()
    expect(chat(wrapper)).toEqual(['Ada', 'Hello', 'Support agent', 'Hi there'])
    expect(loadErrorAlert(wrapper)).toBeUndefined()
  })

  test('stops the reply and shows that it was stopped', async () => {
    const wrapper = await startReply(savedReply('cancelled', '', 'Hel'))

    await stop(wrapper).trigger('click')
    await flushPromises()
    expect(api.cancel).toHaveBeenCalledExactlyOnceWith('run-1')
    expect(document.activeElement).toBe(composer(wrapper).element)
    await finish('run-1', 'cancelled')

    expect(chat(wrapper)).toEqual([
      'Ada',
      'Hello',
      'Support agent',
      'Hel',
      'agent.replyStopped',
    ])
    expect(announcement(wrapper)).toBe('agent.replyStopped')
  })

  test('ignores a Stop that lands after the reply ended', async () => {
    const wrapper = await startReply(savedReply('completed'))
    const staleStop = stop(wrapper)
    await finish('run-1', 'completed')

    await staleStop.trigger('click')
    await flushPromises()

    expect(api.cancel).not.toHaveBeenCalled()
  })

  test.each([
    ['at the bottom', 400, 500],
    ['scrolled up', 100, 100],
  ])(
    'follows the streamed text only when the history is %s',
    async (position, scrollTop, expectedScrollTop) => {
      const wrapper = await startReply(savedReply('completed'))
      const history = wrapper.get('.agent-chat__history').element
      let top = scrollTop
      Object.defineProperties(history, {
        clientHeight: { value: 100, configurable: true },
        scrollHeight: { value: 500, configurable: true },
        scrollTop: {
          get: () => top,
          set: (value) => {
            top = value
          },
        },
      })

      await streamText('run-1', 'lo', 'a:2-0')

      expect(top).toBe(expectedScrollTop)
    }
  )

  test('follows the running reply of a conversation opened after a reload', async () => {
    withConversation([
      message('m1', 'Hello', { author, turn: runningTurn('run-2') }),
    ])
    const wrapper = await mount()

    await selectConversation(wrapper, 'Conversation A')
    await streamText('run-2', 'Partial')

    expect(chat(wrapper)).toEqual(['Ada', 'Hello', 'Support agent', 'Partial'])
  })

  test('shows a message sent from another tab before its reply streams', async () => {
    withConversation(
      [message('m1', 'Hello', { author, turn: savedTurn('completed') })],
      [
        message('m1', 'Hello', { author, turn: savedTurn('completed') }),
        message('m2', 'From another tab', {
          author,
          turn: { ...runningTurn('run-4'), id: 2 },
        }),
      ]
    )
    const wrapper = await mount()
    await selectConversation(wrapper, 'Conversation A')
    await testApp.store.dispatch('chatRuns/handleChanged', {
      runId: 'run-4',
      runType: 'agent',
      chatId: 7,
    })
    await flushPromises()

    await receive('run-4', 'run.started', {}, 'a:1-0')

    expect(messages(wrapper)).toEqual(['Hello', 'From another tab'])
  })

  test('ignores a refresh that lands after a newer one', async () => {
    const earlier = message('m1', 'Hello', {
      author,
      turn: savedTurn('completed'),
    })
    const prompt = (turn) =>
      message('m2', 'From another tab', { author, turn: { ...turn, id: 2 } })
    const failed = savedTurn('failed', 'failed', 2)
    const startedRefresh = deferredReply()
    withConversation([earlier], startedRefresh.reply, [
      earlier,
      prompt(failed),
      message('r2', 'Hel', { role: 'assistant', turn: failed }),
    ])
    const wrapper = await mount()
    await selectConversation(wrapper, 'Conversation A')
    await testApp.store.dispatch('chatRuns/handleChanged', {
      runId: 'run-4',
      runType: 'agent',
      chatId: 7,
    })
    await flushPromises()
    await receive('run-4', 'run.started', {}, 'a:1-0')
    await finish('run-4', 'failed')

    startedRefresh.resolve(200, page([earlier, prompt(runningTurn('run-4'))]))
    await flushPromises()

    expect(chat(wrapper)).toEqual([
      'Ada',
      'Hello',
      'Ada',
      'From another tab',
      'Support agent',
      'Hel',
      'agent.replyFailed',
    ])
  })

  test.each(['before', 'after'])(
    'applies an older refresh that lands %s a newer failed one',
    async (order) => {
      testApp.dontFailOnErrorResponses()
      const finishedRefresh = deferredReply()
      const pageAddRefresh = deferredReply()
      const refreshes = [finishedRefresh, pageAddRefresh]
      const wrapper = await startReply(() => refreshes.shift().reply())
      await finish('run-1', 'completed')
      await testApp.store.dispatch('chatRuns/handlePageAdd', {
        run_type: 'agent',
        chat_id: 5,
      })
      await flushPromises()
      const landings = [
        () => finishedRefresh.resolve(...savedReply('completed')()),
        () => pageAddRefresh.resolve(500, {}),
      ]
      if (order === 'after') landings.reverse()

      for (const land of landings) {
        land()
        await flushPromises()
      }

      expect(chat(wrapper)).toEqual([
        'Ada',
        'Hello',
        'Support agent',
        'Hi there',
      ])
      expect(loadErrorAlert(wrapper).get('button').text()).toBe('action.retry')
    }
  )

  test('resumes a reply that a logout suspended once the conversation loads again', async () => {
    withConversation(
      [message('m1', 'Hello', { author, turn: runningTurn('run-2') })],
      [
        message('m1', 'Hello', { author, turn: savedTurn('completed') }),
        message('r1', 'Done', {
          role: 'assistant',
          turn: savedTurn('completed'),
        }),
      ]
    )
    let wrapper = await mount()
    await selectConversation(wrapper, 'Conversation A')
    await testApp.store.dispatch('chatRuns/disconnect')
    wrapper.unmount()
    api.get.mockResolvedValue({ status: 'completed', error_code: '' })

    wrapper = await mount()
    await selectConversation(wrapper, 'Conversation A')

    expect(chat(wrapper)).toEqual(['Ada', 'Hello', 'Support agent', 'Done'])
    expect(send(wrapper).attributes('aria-label')).toBe('agent.send')
  })

  test('keeps a message sent as a reply ends after that reply', async () => {
    withConversation(
      // Running without a run: the reply ended after this page was read.
      [message('m1', 'Hello', { author, turn: savedTurn('running') })],
      () => [
        200,
        page([
          message('m1', 'Hello', { author, turn: savedTurn('completed') }),
          message('r1', 'Hello there', {
            role: 'assistant',
            turn: savedTurn('completed'),
          }),
          message(sentBodies(testApp)[0].uuid, 'Next', {
            author,
            turn: savedTurn('completed', '', 2),
          }),
          message('r2', 'Bye', {
            role: 'assistant',
            turn: savedTurn('completed', '', 2),
          }),
        ]),
      ]
    )
    mockSendMessage(testApp, 'conversation-a', ({ data }) => [
      200,
      {
        conversation: conversation(
          'conversation-a',
          'Conversation A',
          undefined,
          7
        ),
        message: message(JSON.parse(data).uuid, 'Next', {
          author,
          turn: { ...runningTurn('run-2'), id: 2 },
        }),
      },
    ])
    const wrapper = await mount()
    await selectConversation(wrapper, 'Conversation A')
    await sendMessage(wrapper, 'Next')

    await finish('run-2', 'completed')

    expect(messages(wrapper)).toEqual(['Hello', 'Hello there', 'Next', 'Bye'])
  })

  test('follows the reply that refused a message and clears the refusal once it ends', async () => {
    testApp.dontFailOnErrorResponses()
    const earlier = message('m1', 'Earlier', {
      author,
      turn: savedTurn('completed'),
    })
    withConversation(
      [earlier],
      [
        earlier,
        message('m2', 'Other tab', {
          author,
          turn: { ...runningTurn('run-3'), id: 2 },
        }),
      ],
      [
        earlier,
        message('m2', 'Other tab', {
          author,
          turn: savedTurn('completed', '', 2),
        }),
        message('r2', 'Done', {
          role: 'assistant',
          turn: savedTurn('completed', '', 2),
        }),
      ]
    )
    mockSendMessage(testApp, 'conversation-a', [
      409,
      { error: 'ERROR_CHAT_RUN_IN_PROGRESS' },
    ])
    const wrapper = await mount()
    await selectConversation(wrapper, 'Conversation A')

    await sendMessage(wrapper, 'Again')

    expect(wrapper.get('#agent-chat-send-error').text()).toBe(
      'agent.replyInProgress'
    )
    expect(stop(wrapper).exists()).toBe(true)
    expect(api.stream.mock.calls.map(([runId]) => runId)).toEqual(['run-3'])
    await finish('run-3', 'completed')
    expect(messages(wrapper)).toEqual(['Earlier', 'Other tab', 'Done'])
    expect(wrapper.find('#agent-chat-send-error').exists()).toBe(false)
    expect(send(wrapper).attributes('aria-label')).toBe('agent.send')
  })

  test.each([
    [409, 'ERROR_CHAT_RUN_IN_PROGRESS', 'agent.replyInProgress'],
    [429, 'ERROR_AGENT_BUSY', 'agent.agentsBusy'],
  ])(
    'keeps the message editable when a send is refused with %s',
    async (status, error, copy) => {
      testApp.dontFailOnErrorResponses()
      const earlier = message('m1', 'Earlier', { author })
      withConversation(
        [earlier],
        [earlier, message('m2', 'Other tab', { author, turn: runningTurn() })]
      )
      mockSendMessage(testApp, 'conversation-a', [status, { error }])
      const wrapper = await mount()
      await selectConversation(wrapper, 'Conversation A')

      await sendMessage(wrapper, 'Again')

      expect(wrapper.get('#agent-chat-send-error').text()).toBe(copy)
      expect(composer(wrapper).element.readOnly).toBe(false)
    }
  )

  test('drops a refusal whose reply ended before the refresh', async () => {
    testApp.dontFailOnErrorResponses()
    withConversation([message('m1', 'Earlier', { author })])
    mockSendMessage(testApp, 'conversation-a', [
      409,
      { error: 'ERROR_CHAT_RUN_IN_PROGRESS' },
    ])
    const wrapper = await mount()
    await selectConversation(wrapper, 'Conversation A')

    await sendMessage(wrapper, 'Again')

    expect(wrapper.find('#agent-chat-send-error').exists()).toBe(false)
    expect(send(wrapper).attributes('aria-label')).toBe('agent.send')
  })

  test('drops a refusal whose reply ended while another conversation was open', async () => {
    testApp.dontFailOnErrorResponses()
    const earlier = message('m1', 'Earlier', { author })
    const prompt = (turn) =>
      message('m2', 'Other tab', { author, turn: { ...turn, id: 2 } })
    mockConversations(
      testApp,
      page([
        conversation('conversation-a', 'Conversation A', undefined, 7),
        conversation('conversation-b', 'Conversation B', undefined, 8),
      ])
    )
    mockMessages(
      testApp,
      'conversation-a',
      page([earlier]),
      page([earlier, prompt(runningTurn('run-3'))]),
      page([earlier, prompt(savedTurn('completed', '', 2))])
    )
    mockMessages(testApp, 'conversation-b', page([]))
    mockSendMessage(testApp, 'conversation-a', [
      409,
      { error: 'ERROR_CHAT_RUN_IN_PROGRESS' },
    ])
    const wrapper = await mount()
    await selectConversation(wrapper, 'Conversation A')
    await sendMessage(wrapper, 'Again')
    expect(wrapper.find('#agent-chat-send-error').exists()).toBe(true)

    await selectConversation(wrapper, 'Conversation B')
    expect(wrapper.find('#agent-chat-send-error').exists()).toBe(false)
    await finish('run-3', 'completed')
    await selectConversation(wrapper, 'Conversation A')

    expect(wrapper.find('#agent-chat-send-error').exists()).toBe(false)
    expect(send(wrapper).attributes('aria-label')).toBe('agent.send')
  })

  test.each([
    ['cancelled', '', 'agent.replyStopped'],
    ['failed', 'timeout', 'agent.replyTimedOut'],
    ['failed', 'interrupted', 'agent.replyInterrupted'],
    ['failed', 'not_started', 'agent.replyNotStarted'],
    ['failed', 'not_ready', 'agent.replyNotReady'],
    ['failed', 'not_allowed', 'agent.replyNotAllowed'],
    ['failed', 'failed', 'agent.replyFailed'],
    ['running', '', 'agent.replyInterrupted'],
  ])(
    'shows the notice of a %s turn with code "%s" after its last message',
    async (status, errorCode, notice) => {
      const turn = savedTurn(status, errorCode)
      withConversation([
        message('m1', 'Hello', { author, turn }),
        message('r1', 'Partial', { role: 'assistant', turn }),
      ])
      const wrapper = await mount()

      await selectConversation(wrapper, 'Conversation A')

      expect(chat(wrapper)).toEqual([
        'Ada',
        'Hello',
        'Support agent',
        'Partial',
        notice,
      ])
    }
  )
})
