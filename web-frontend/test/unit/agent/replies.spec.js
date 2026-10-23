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

const savedTurn = (status, errorCode = '', id = 1) => ({
  id,
  status,
  error_code: errorCode,
  run_id: null,
})
const existingConversation = conversation(
  'conversation-a',
  'Conversation A',
  undefined,
  7
)
const prompt = (turn) => message('m1', 'Hello', { id: 1, turn })
const reply = (turn, content = 'Hi there') =>
  message('r1', content, { id: turn.id * 2, role: 'assistant', turn })
const notice = (wrapper) => wrapper.find('.agent-chat__notice').text()
const announcement = (wrapper) =>
  wrapper.get('.agent-chat__announcement[role="status"]').text()
const liveReply = (wrapper) => wrapper.get('.agent-chat__message[aria-live]')
const loadErrorAlert = (wrapper) =>
  wrapper
    .findAll('.alert')
    .find((alert) => alert.text().includes('agent.messagesLoadError'))

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

  async function receive(runId, kind, data, cursor = 'a:1-0') {
    await streams[runId]({ kind, data, cursor })
    await flushPromises()
  }
  const streamText = (runId, text) =>
    receive(runId, 'text.delta', { segment: 0, text })
  const finish = (runId, status = 'completed') =>
    receive(runId, 'run.finished', { status }, 'a:9-0')
  const withConversation = (...responses) => {
    mockConversations(testApp, page([existingConversation]))
    mockMessages(
      testApp,
      existingConversation.uuid,
      ...responses.map((items) =>
        typeof items === 'function' ? items : page(items)
      )
    )
  }
  const savedReply = (status = 'completed', content = 'Hi there') => [
    200,
    page([
      message(sentBodies(testApp)[0].message_uuid, 'Hello', {
        turn: savedTurn(status),
      }),
      reply(savedTurn(status), content),
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

  test('sends, streams and retains the reply until its persisted outcome loads', async () => {
    const pending = deferredReply()
    const wrapper = await startReply(pending.reply)

    expect(testApp.store.state.chatRuns.subscription).toEqual({
      runType: 'agent',
      chatId: 5,
    })
    expect(api.stream.mock.calls.map(([runId]) => runId)).toEqual(['run-1'])
    expect(messages(wrapper)).toEqual(['Hello', 'Hel'])
    expect(
      wrapper.findAll('.agent-chat__message-author').map((item) => item.text())
    ).toEqual(['Ada', 'Support agent'])
    expect(liveReply(wrapper).attributes('aria-busy')).toBe('true')
    expect(announcement(wrapper)).toBe('agent.replying')
    expect(stop(wrapper).attributes('aria-label')).toBe('agent.stop')

    await finish('run-1')

    expect(messages(wrapper)).toEqual(['Hello', 'Hel'])
    expect(liveReply(wrapper).attributes('aria-busy')).toBe('false')
    expect(send(wrapper).attributes('disabled')).toBeDefined()
    expect(testApp.mock.history.get.at(-1).headers).toMatchObject({
      'X-Baserow-Realtime-Recovery': 'true',
    })
    pending.resolve(...savedReply())
    await flushPromises()

    expect(messages(wrapper)).toEqual(['Hello', 'Hi there'])
    expect(announcement(wrapper)).toBe('')
    expect(send(wrapper).attributes('aria-label')).toBe('agent.send')
  })

  test('retains streamed text after a history failure and retries the saved outcome', async () => {
    testApp.dontFailOnErrorResponses()
    let available = false
    const wrapper = await startReply(() =>
      available ? savedReply() : [500, {}]
    )

    await finish('run-1')

    expect(messages(wrapper)).toEqual(['Hello', 'Hel'])
    available = true
    await loadErrorAlert(wrapper).get('button').trigger('click')
    await flushPromises()
    expect(messages(wrapper)).toEqual(['Hello', 'Hi there'])
    expect(loadErrorAlert(wrapper)).toBeUndefined()
  })

  test('stops a reply and shows its persisted cancellation', async () => {
    const wrapper = await startReply(() => savedReply('cancelled', 'Hel'))

    await stop(wrapper).trigger('click')
    await flushPromises()
    expect(api.cancel).toHaveBeenCalledExactlyOnceWith('run-1')
    expect(document.activeElement).toBe(composer(wrapper).element)
    await finish('run-1', 'cancelled')

    expect(messages(wrapper)).toEqual(['Hello', 'Hel'])
    expect(notice(wrapper)).toBe('agent.replyStopped')
    expect(announcement(wrapper)).toBe('agent.replyStopped')
  })

  test('follows an active reply on reload and recovers its saved outcome after logout', async () => {
    withConversation(
      [prompt(runningTurn('run-2'))],
      [prompt(savedTurn('completed')), reply(savedTurn('completed'))]
    )
    let wrapper = await mount()
    await selectConversation(wrapper, existingConversation.title)
    await streamText('run-2', 'Partial')
    expect(messages(wrapper)).toEqual(['Hello', 'Partial'])

    await testApp.store.dispatch('chatRuns/disconnect')
    wrapper.unmount()
    api.get.mockResolvedValue({ status: 'completed', error_code: '' })
    wrapper = await mount()
    await selectConversation(wrapper, existingConversation.title)

    expect(messages(wrapper)).toEqual(['Hello', 'Hi there'])
    expect(send(wrapper).attributes('aria-label')).toBe('agent.send')
  })

  test('queues a completed outcome behind the refresh started by another tab', async () => {
    const startedRefresh = deferredReply()
    const otherPrompt = (turn) =>
      message('m2', 'From another tab', { id: 3, turn })
    const completed = savedTurn('failed', 'failed', 2)
    withConversation([prompt(savedTurn('completed'))], startedRefresh.reply, [
      prompt(savedTurn('completed')),
      otherPrompt(completed),
      reply(completed, 'Partial'),
    ])
    const wrapper = await mount()
    await selectConversation(wrapper, existingConversation.title)
    await testApp.store.dispatch('chatRuns/handleChanged', {
      runId: 'run-4',
      runType: 'agent',
      chatId: existingConversation.id,
    })
    await flushPromises()
    await receive('run-4', 'run.started', {})
    await finish('run-4', 'failed')
    startedRefresh.resolve(
      200,
      page([
        prompt(savedTurn('completed')),
        otherPrompt({ ...runningTurn('run-4'), id: 2 }),
      ])
    )
    await flushPromises()

    expect(messages(wrapper)).toEqual(['Hello', 'From another tab', 'Partial'])
    expect(notice(wrapper)).toBe('agent.replyFailed')
  })

  test('orders the previous reply before a message sent as that reply ends', async () => {
    const completed = savedTurn('completed')
    const next = savedTurn('completed', '', 2)
    withConversation([prompt(savedTurn('running'))], () => [
      200,
      page([
        prompt(completed),
        reply(completed),
        message(sentBodies(testApp)[0].uuid, 'Next', { id: 3, turn: next }),
        message('r2', 'Bye', { id: 4, role: 'assistant', turn: next }),
      ]),
    ])
    mockSendMessage(testApp, existingConversation.uuid, ({ data }) => [
      200,
      {
        conversation: existingConversation,
        message: message(JSON.parse(data).uuid, 'Next', {
          id: 3,
          turn: { ...runningTurn('run-2'), id: 2 },
        }),
      },
    ])
    const wrapper = await mount()
    await selectConversation(wrapper, existingConversation.title)
    await sendMessage(wrapper, 'Next')
    await finish('run-2')

    expect(messages(wrapper)).toEqual(['Hello', 'Hi there', 'Next', 'Bye'])
  })

  test('follows a conflicting reply while preserving the draft and clears its refusal in another chat', async () => {
    testApp.dontFailOnErrorResponses()
    const earlier = prompt(savedTurn('completed'))
    const otherPrompt = (turn) =>
      message('m2', 'Other tab', { id: 3, turn: { ...turn, id: 2 } })
    withConversation(
      [earlier],
      [earlier, otherPrompt(runningTurn('run-3'))],
      [
        earlier,
        otherPrompt(savedTurn('completed', '', 2)),
        reply(savedTurn('completed', '', 2)),
      ]
    )
    mockConversations(
      testApp,
      page([
        existingConversation,
        conversation('conversation-b', 'Conversation B', undefined, 8),
      ])
    )
    mockMessages(testApp, 'conversation-b', page([]))
    mockSendMessage(testApp, existingConversation.uuid, [
      409,
      { error: 'ERROR_CHAT_RUN_IN_PROGRESS' },
    ])
    const wrapper = await mount()
    await selectConversation(wrapper, existingConversation.title)
    await sendMessage(wrapper, 'Again')

    expect(wrapper.get('#agent-chat-send-error').text()).toBe(
      'agent.replyInProgress'
    )
    expect(composer(wrapper).element.readOnly).toBe(false)
    expect(stop(wrapper).exists()).toBe(true)
    expect(api.stream.mock.calls.map(([runId]) => runId)).toEqual(['run-3'])
    await selectConversation(wrapper, 'Conversation B')
    expect(wrapper.find('#agent-chat-send-error').exists()).toBe(false)
    await finish('run-3')
    await selectConversation(wrapper, existingConversation.title)

    expect(messages(wrapper)).toEqual(['Hello', 'Other tab', 'Hi there'])
    expect(composer(wrapper).element.value).toBe('Again')
    expect(wrapper.find('#agent-chat-send-error').exists()).toBe(false)
    expect(send(wrapper).attributes('aria-label')).toBe('agent.send')
  })

  test('keeps a busy refusal editable and allows retry with a new message ID', async () => {
    testApp.dontFailOnErrorResponses()
    withConversation([prompt(savedTurn('completed'))])
    mockSendMessage(testApp, existingConversation.uuid, [
      429,
      { error: 'ERROR_AGENT_BUSY' },
    ])
    const wrapper = await mount()
    await selectConversation(wrapper, existingConversation.title)
    await sendMessage(wrapper, 'Again')

    expect(wrapper.get('#agent-chat-send-error').text()).toBe(
      'agent.agentsBusy'
    )
    expect(composer(wrapper).element.readOnly).toBe(false)
    await sendMessage(wrapper, 'Changed')
    const [first, second] = sentBodies(testApp)
    expect(second.uuid).not.toBe(first.uuid)
    expect(second.content).toBe('Changed')
  })

  test('clears a refusal if the other reply already ended before the refresh', async () => {
    testApp.dontFailOnErrorResponses()
    withConversation([prompt(savedTurn('completed'))])
    mockSendMessage(testApp, existingConversation.uuid, [
      409,
      { error: 'ERROR_CHAT_RUN_IN_PROGRESS' },
    ])
    const wrapper = await mount()
    await selectConversation(wrapper, existingConversation.title)
    await sendMessage(wrapper, 'Again')

    expect(wrapper.find('#agent-chat-send-error').exists()).toBe(false)
    expect(send(wrapper).attributes('aria-label')).toBe('agent.send')
  })

  test.each([
    ['failed', 'timeout', 'agent.replyTimedOut'],
    ['running', '', 'agent.replyInterrupted'],
  ])(
    'shows one notice after the last message of an unsuccessful %s turn',
    async (status, errorCode, expected) => {
      const turn = savedTurn(status, errorCode)
      withConversation([prompt(turn), reply(turn, 'Partial')])
      const wrapper = await mount()
      await selectConversation(wrapper, existingConversation.title)

      expect(messages(wrapper)).toEqual(['Hello', 'Partial'])
      expect(wrapper.findAll('.agent-chat__notice')).toHaveLength(1)
      expect(notice(wrapper)).toBe(expected)
    }
  )
})
