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
  incompleteConfiguration,
  message,
  messages,
  mockConversations,
  mockMessages,
  mockSaves,
  mockSendMessage,
  mockStartConversation,
  openSection,
  page,
  selectConversation,
  send,
  sendMessage,
  stop,
} from './helpers'

vi.mock('@baserow/modules/core/services/chatRuns', () => ({ default: vi.fn() }))

const existingConversation = conversation('conversation-a', 'Conversation A')
const prompt = message('m1', 'Hello', { id: 1 })
const reply = (status, content = 'Hi there', { id = 2, ...extra } = {}) =>
  message(`reply-${id}`, content, { id, role: 'assistant', status, ...extra })
const runningReply = (runId = 'run-1', id = 2) =>
  reply('running', '', { id, runId })
const error = (wrapper) => wrapper.find('.chat-message__bubble--error').text()
const note = (wrapper) => wrapper.find('.chat-message__note').text()
const activity = (wrapper) => wrapper.get('.chat-composer__activity')
const announcement = (wrapper) =>
  wrapper.get('.agent-chat__announcement[role="status"]').text()
const liveReply = (wrapper) => wrapper.get('.chat-message__bubble[aria-live]')
const typing = (wrapper) => wrapper.find('.chat-typing').exists()
const spinning = (wrapper) => wrapper.find('.chat-loading__spinner').exists()
const toolStep = (id, tool, status, extra = {}) => ({
  id,
  tool,
  presentation_type: tool,
  status,
  changes_data: tool === 'create_rows',
  input: {},
  facts: {},
  ...extra,
})

describe('Agent replies', () => {
  let testApp, mount, api, streams, cursor

  beforeEach(async () => {
    ;({ testApp, mount } = await createAgentPage())
    testApp.authenticate({ id: 1 })
    streams = {}
    cursor = 0
    api = {
      get: vi.fn().mockResolvedValue({ status: 'running' }),
      cancel: vi.fn().mockResolvedValue({ status: 'running' }),
      stream: vi.fn((runId, from, onRecord) => {
        streams[runId] = onRecord
        return new Promise(() => {})
      }),
    }
    service.mockReturnValue(api)
  })

  afterEach(() => destroyAgentPage(testApp))

  async function receive(runId, kind, data) {
    await streams[runId]({ kind, data, cursor: `a:${++cursor}-0` })
    await flushPromises()
  }
  const streamText = (runId, text) =>
    receive(runId, 'text.delta', { segment: 0, text })
  const finish = (runId, status = 'completed', saved = null) =>
    receive(runId, 'run.finished', { status, message: saved })
  const messageReads = () =>
    testApp.mock.history.get.filter(({ url }) => url.includes('/messages/'))
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
  async function startReply() {
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
    const wrapper = await mount()
    await sendMessage(wrapper, 'Hello')
    return wrapper
  }

  test('sends, streams and shows the saved reply its run ends with', async () => {
    const wrapper = await startReply()

    expect(testApp.store.state.chatRuns.subscriptions).toEqual({ agent: 5 })
    expect(api.stream.mock.calls.map(([runId]) => runId)).toEqual(['run-1'])
    expect(messages(wrapper)).toEqual(['Hello', ''])
    expect(typing(wrapper)).toBe(true)
    expect(activity(wrapper).text()).toBe('agent.thinking')
    expect(announcement(wrapper)).toBe('agent.replying')
    expect(stop(wrapper).attributes('aria-label')).toBe('agent.stop')

    await streamText('run-1', 'Hel')

    expect(messages(wrapper)).toEqual(['Hello', 'Hel'])
    expect([typing(wrapper), spinning(wrapper)]).toEqual([false, true])
    expect(liveReply(wrapper).attributes('aria-busy')).toBe('true')
    expect(activity(wrapper).text()).toBe('agent.writing')

    await finish('run-1', 'completed', reply('completed', '**Hello** there'))
    await composer(wrapper).setValue('Next')

    expect(messages(wrapper)).toEqual(['Hello', 'Hello there'])
    expect(wrapper.get('.chat-markdown strong').text()).toBe('Hello')
    expect(spinning(wrapper)).toBe(false)
    expect(liveReply(wrapper).attributes('aria-busy')).toBe('false')
    expect(activity(wrapper).classes()).not.toContain(
      'chat-composer__activity--visible'
    )
    expect(send(wrapper).element.disabled).toBe(false)
    expect(announcement(wrapper)).toBe('')
    expect(messageReads()).toEqual([])
  })

  test('shows live tool activity and replaces it with the saved outcome', async () => {
    const wrapper = await startReply()
    const running = toolStep('call-1', 'create_rows', 'running', {
      input: { requested_count: 3 },
    })

    await receive('run-1', 'step', running)

    expect(wrapper.get('.chat-step-group').attributes('aria-busy')).toBe('true')
    expect(wrapper.get('.chat-step-group__title').text()).toContain('3')
    expect(typing(wrapper)).toBe(false)
    expect(activity(wrapper).text()).toContain(
      'agent.toolCreateRowsRunningCount'
    )
    expect(activity(wrapper).text()).toContain('3')

    const done = {
      ...running,
      status: 'done',
      facts: { count: 2, table: 'Tasks' },
    }
    await finish(
      'run-1',
      'completed',
      reply('completed', 'Added rows', { steps: [done] })
    )

    expect(wrapper.findAll('.chat-step-group')).toHaveLength(1)
    expect(wrapper.get('.chat-step-group').attributes('aria-busy')).toBe(
      'false'
    )
    expect(wrapper.get('.chat-step-group__title').text()).toContain('2')
    expect(
      wrapper.find('.chat-step-group .iconoir-check-circle').exists()
    ).toBe(true)
    expect(activity(wrapper).classes()).not.toContain(
      'chat-composer__activity--visible'
    )
  })

  test('reloads grouped reads and failed calls from saved message steps', async () => {
    withConversation([
      prompt,
      reply('completed', 'Finished', {
        steps: [
          toolStep('a', 'list_tables', 'done'),
          toolStep('b', 'get_table_schema', 'done', {
            facts: { table: 'Tasks' },
          }),
          toolStep('c', 'create_rows', 'failed'),
        ],
      }),
    ])
    const wrapper = await mount()
    await selectConversation(wrapper, existingConversation.title)

    expect(wrapper.findAll('.chat-step-group')).toHaveLength(2)
    expect(
      wrapper.find('.chat-step-group .iconoir-warning-triangle').exists()
    ).toBe(true)
    const reads = wrapper.findAll('.chat-step-group')[0]
    expect(reads.get('button').classes()).not.toContain('button')
    expect(reads.get('.chat-step-group__title').text()).toBe(
      'Workspace activity'
    )
    expect(reads.findAll('li')).toHaveLength(2)
    await reads.get('button').trigger('click')
    expect(reads.findAll('li')).toHaveLength(0)
    expect(api.stream).not.toHaveBeenCalled()
  })

  test('keeps Stop while the configuration stops being ready', async () => {
    mockSaves(testApp, incompleteConfiguration('instructions'))
    const wrapper = await startReply()

    await openSection(wrapper, 'agent.instructions')
    await editInstructions(wrapper, '')
    await stop(wrapper).trigger('click')
    await flushPromises()

    expect(api.cancel).toHaveBeenCalledExactlyOnceWith('run-1')
  })

  test('a streamed chunk updates only the reply being written', async () => {
    withConversation([
      prompt,
      reply('completed'),
      message('m3', 'More', { id: 3 }),
      runningReply('run-4', 4),
    ])
    const updated = []
    const wrapper = await mount({
      mixins: [
        {
          updated() {
            if (this.$options.__name === 'AgentMessage') {
              updated.push(this.message.uuid)
            }
          },
        },
      ],
    })
    await selectConversation(wrapper, existingConversation.title)
    updated.length = 0

    await streamText('run-4', 'Hel')
    await streamText('run-4', 'lo')

    expect(updated).toEqual(['reply-4', 'reply-4'])
  })

  test('stops a reply and shows its persisted cancellation', async () => {
    const wrapper = await startReply()
    await streamText('run-1', 'Hel')

    await stop(wrapper).trigger('click')
    await flushPromises()
    expect(api.cancel).toHaveBeenCalledExactlyOnceWith('run-1')
    expect(document.activeElement).toBe(composer(wrapper).element)
    await finish('run-1', 'cancelled', reply('cancelled', 'Hel!'))

    expect(messages(wrapper)).toEqual(['Hello', 'Hel!'])
    expect(note(wrapper)).toBe('agent.replyStopped')
    expect(announcement(wrapper)).toBe('agent.replyStopped')
  })

  // Logging out suspends followers; reopening the chat must resume them or Stop stays.
  test('follows an active reply on reload and recovers its saved outcome after logout', async () => {
    withConversation([prompt, runningReply('run-2')])
    let wrapper = await mount()
    await selectConversation(wrapper, existingConversation.title)
    await streamText('run-2', 'Partial')
    expect(messages(wrapper)).toEqual(['Hello', 'Partial'])

    await testApp.store.dispatch('chatRuns/disconnect')
    wrapper.unmount()
    wrapper = await mount()
    await selectConversation(wrapper, existingConversation.title)
    await finish('run-2', 'completed', reply('completed'))

    expect(messages(wrapper)).toEqual(['Hello', 'Hi there'])
    expect(send(wrapper).attributes('aria-label')).toBe('agent.send')
  })

  test('queues a failed outcome behind the refresh started by another tab', async () => {
    const startedRefresh = deferredReply()
    const otherPrompt = message('m3', 'From another tab', { id: 3 })
    withConversation([prompt, reply('completed')], startedRefresh.reply, [
      prompt,
      reply('completed'),
      otherPrompt,
      reply('failed', 'Partial', { id: 4, errorCode: 'failed' }),
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
      page([prompt, reply('completed'), otherPrompt, runningReply('run-4', 4)])
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
    mockConversations(
      testApp,
      page([
        existingConversation,
        conversation('conversation-b', 'Conversation B'),
      ])
    )
    mockMessages(
      testApp,
      existingConversation.uuid,
      page([prompt]),
      page([prompt, otherPrompt, runningReply('run-3', 4)]),
      page([prompt, otherPrompt, reply('completed', 'Hi there', { id: 4 })])
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
