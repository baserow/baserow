import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import service from '@baserow/modules/core/services/chatRuns'
import {
  composer,
  composerExists,
  conversation,
  createAgentPage,
  deferredReply,
  destroyAgentPage,
  message,
  messages,
  mockApprovals,
  mockConversations,
  mockMessages,
  mockSendMessage,
  mockStartConversation,
  page,
  selectConversation,
  sendMessage,
  sentBodies,
  stop,
} from './helpers'

vi.mock('@baserow/modules/core/services/chatRuns', () => ({ default: vi.fn() }))

const chat = conversation('conversation-a', 'Conversation A')
const prompt = message('m1', 'Add the companies', { id: 1 })
const read = {
  id: 'read',
  tool: 'list_tables',
  status: 'done',
  changes_data: false,
  input: {},
  facts: {},
}
const heldStep = (id, status) => ({
  id: `step-${id}`,
  tool: 'create_rows',
  status,
  changes_data: true,
  input: {
    requested_count: 3,
    target: 'Companies',
    values: { table_id: 1, rows: [{ Name: `Company ${id}` }] },
  },
  facts: {},
})
const approval = (id, status = 'pending', { reason = '', pause = 1 } = {}) => ({
  id,
  step_id: `step-${id}`,
  tool: 'create_rows',
  status,
  reason,
  pause,
})
const reply = (
  status,
  approvals,
  { runId = null, stepStatus, steps } = {}
) => ({
  ...message('reply-2', 'Adding them.', {
    id: 2,
    role: 'assistant',
    status,
    runId,
    steps: steps || [
      read,
      ...approvals.map(({ id, status: decision }) =>
        heldStep(
          id,
          stepStatus || (decision === 'rejected' ? 'rejected' : 'waiting')
        )
      ),
    ],
  }),
  approvals,
})

const card = (wrapper) => wrapper.get('.agent-approval')
const cards = (wrapper) => wrapper.findAll('.agent-approval')
const texts = (elements) => elements.map((element) => element.text())
const title = (wrapper) => card(wrapper).get('.agent-approval__title').text()
const headerButtons = (wrapper) =>
  card(wrapper).findAll('.agent-approval__actions button')
const items = (wrapper) => card(wrapper).findAll('.agent-approval__item')
const itemButtons = (item) =>
  item.findAll('.agent-approval__item-actions button')
const decisions = (wrapper) =>
  texts(card(wrapper).findAll('.agent-approval__decision'))
const announcement = (wrapper) =>
  card(wrapper).get('.agent-approval__announcement[role="status"]').text()
const activity = (wrapper) => wrapper.get('.chat-composer__activity')
const inModal = (selector) => document.body.querySelector(selector)
const modalButton = (text) =>
  [
    ...document.body.querySelectorAll('.agent-reject-modal__actions button'),
  ].find((button) => button.textContent.trim() === text)

describe('Agent tool approvals', () => {
  let testApp, mount, allowed, api, streams, cursor

  beforeEach(async () => {
    ;({ testApp, mount, allowed } = await createAgentPage())
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
  const finish = (runId, saved) =>
    receive(runId, 'run.finished', { status: 'completed', message: saved })
  const messageReads = () =>
    testApp.mock.history.get.filter(({ url }) => url.includes('/messages/'))

  async function openReply(saved, ...later) {
    mockConversations(testApp, page([chat]))
    mockMessages(testApp, chat.uuid, page([prompt, saved]), ...later)
    const wrapper = await mount()
    await selectConversation(wrapper, chat.title)
    return wrapper
  }
  const openWaitingReply = (approvals, ...later) =>
    openReply(reply('waiting', approvals), ...later)

  test('a reply that pauses asks for approval of its step', async () => {
    mockStartConversation(testApp, ({ data }) => {
      const body = JSON.parse(data)
      return [
        200,
        {
          conversation: conversation(body.uuid, body.content, undefined, 5),
          message: message(body.message_uuid, body.content, { id: 1 }),
          reply: reply('running', [], { runId: 'run-1' }),
        },
      ]
    })
    const wrapper = await mount()
    await sendMessage(wrapper, 'Add the companies')

    await finish('run-1', reply('waiting', [approval(1)]))

    expect(wrapper.findAll('.chat-step-group')).toHaveLength(1)
    expect(title(wrapper)).toBe('agent.approvalRequest')
    expect(texts(headerButtons(wrapper))).toEqual([
      'agent.reject',
      'agent.approve',
    ])
    const [item] = items(wrapper)
    expect(item.get('.agent-approval__item-title').text()).toBe(
      'agent.toolCreateRowsHeldCountTarget - 3'
    )
    expect(itemButtons(item)).toHaveLength(0)
    expect(item.get('.agent-approval__tool').text()).toBe('create_rows')
    expect(item.find('pre').exists()).toBe(false)
    await item.get('.agent-approval__details-toggle').trigger('click')
    expect(item.get('pre').text()).toContain('Company 1')
    expect(item.get('.agent-approval__details-toggle').text()).toBe(
      'agent.hideDetails'
    )
    expect(wrapper.find('.chat-message__bubble--error').exists()).toBe(false)
    expect(wrapper.get('.agent-chat__announcement[role="status"]').text()).toBe(
      'agent.waitingForApproval'
    )
    expect(activity(wrapper).classes()).toEqual(
      expect.arrayContaining([
        'chat-composer__activity--visible',
        'chat-composer__activity--waiting',
      ])
    )
    expect(activity(wrapper).text()).toBe('agent.waitingForApproval')
    expect(composer(wrapper).element.disabled).toBe(true)
    expect(composer(wrapper).attributes('placeholder')).toBe(
      'agent.approvalPlaceholder'
    )
  })

  test('a reloaded reply asks for approval of each of several steps', async () => {
    const wrapper = await openWaitingReply([approval(1), approval(2)])

    expect(texts(headerButtons(wrapper))).toEqual([
      'agent.rejectAll',
      'agent.approveAll',
    ])
    expect(items(wrapper).map((item) => texts(itemButtons(item)))).toEqual([
      ['agent.reject', 'agent.approve'],
      ['agent.reject', 'agent.approve'],
    ])
    expect(activity(wrapper).text()).toBe('agent.waitingForApprovalSteps - 2')
    expect(composer(wrapper).element.disabled).toBe(true)
  })

  test('a later pause gets its own card after the reviewed one', async () => {
    const wrapper = await openReply(
      reply(
        'waiting',
        [approval(1, 'approved'), approval(2, 'pending', { pause: 2 })],
        {
          steps: [read, heldStep(1, 'done'), heldStep(2, 'waiting')],
        }
      )
    )

    expect(
      cards(wrapper).map((item) => item.get('.agent-approval__title').text())
    ).toEqual(['agent.approvalReviewed', 'agent.approvalRequest'])
    expect(
      texts(cards(wrapper)[1].findAll('.agent-approval__actions button'))
    ).toEqual(['agent.reject', 'agent.approve'])
  })

  test('a read between the held writes of a pause follows their card', async () => {
    const wrapper = await openReply(
      reply('waiting', [approval(1), approval(2)], {
        steps: [heldStep(1, 'waiting'), read, heldStep(2, 'waiting')],
      })
    )

    expect(
      wrapper
        .findAll('.agent-approval, .chat-step-group')
        .map((element) => element.classes()[0])
    ).toEqual(['agent-approval', 'chat-step-group'])
    expect(items(wrapper)).toHaveLength(2)
    expect(texts(headerButtons(wrapper))).toEqual([
      'agent.rejectAll',
      'agent.approveAll',
    ])
  })

  test('an approved step that was stopped says it may have run', async () => {
    const wrapper = await openReply(
      reply('failed', [approval(1, 'approved')], { stepStatus: 'stopped' })
    )

    const status = items(wrapper)[0].get('.agent-approval__step-status')
    expect(status.text()).toBe('toolPresentation.statusStopped')
    expect(status.find('.iconoir-minus-circle').exists()).toBe(true)
    expect(decisions(wrapper)).toEqual(['agent.approved'])
  })

  test('approving all steps follows the resumed reply', async () => {
    const decision = deferredReply()
    mockApprovals(testApp, chat.uuid, decision.reply)
    const wrapper = await openWaitingReply([approval(1), approval(2)])

    await headerButtons(wrapper)[1].trigger('click')
    await flushPromises()
    expect(
      card(wrapper)
        .findAll('button:not(.agent-approval__details-toggle)')
        .map((button) => button.element.disabled)
    ).toEqual(Array(6).fill(true))
    const approved = [approval(1, 'approved'), approval(2, 'approved')]
    decision.resolve(200, reply('running', approved, { runId: 'run-2' }))
    await flushPromises()
    expect(title(wrapper)).toBe('agent.approvalReviewed')
    expect(messages(wrapper)).toEqual(['Add the companies', 'Adding them.'])

    expect(sentBodies(testApp)).toEqual([
      {
        decisions: [
          { id: 1, approved: true },
          { id: 2, approved: true },
        ],
      },
    ])
    expect(api.stream.mock.calls.map(([runId]) => runId)).toEqual(['run-2'])
    expect(stop(wrapper).exists()).toBe(true)
    expect(activity(wrapper).text()).toBe('agent.thinking')
    expect(composer(wrapper).element.disabled).toBe(false)

    for (const step of [read, heldStep(1, 'done'), heldStep(2, 'running')]) {
      await receive('run-2', 'step', step)
    }
    expect(title(wrapper)).toBe('agent.approvalReviewed')
    await finish('run-2', reply('completed', approved, { stepStatus: 'done' }))

    expect(title(wrapper)).toBe('agent.approvalReviewed')
    expect(card(wrapper).get('.agent-approval__summary').text()).toBe(
      'agent.approvalApprovedCount - 2'
    )
    expect(decisions(wrapper)).toEqual(['agent.approved', 'agent.approved'])
    expect(headerButtons(wrapper)).toHaveLength(0)
  })

  test('rejecting one step sends the reason given in the modal', async () => {
    mockApprovals(
      testApp,
      chat.uuid,
      reply('waiting', [
        approval(1, 'rejected', { reason: 'Wrong table' }),
        approval(2),
      ])
    )
    const wrapper = await openWaitingReply([approval(1), approval(2)])

    await headerButtons(wrapper)[0].trigger('click')
    expect(inModal('.box__title').textContent).toBe('agent.rejectStepsTitle')
    modalButton('action.cancel').click()
    await flushPromises()
    await itemButtons(items(wrapper)[0])[0].trigger('click')
    expect(inModal('.box__title').textContent).toBe('agent.rejectStepTitle')
    const reason = inModal('.agent-reject-modal textarea')
    expect(reason.maxLength).toBe(1000)
    reason.value = '  Wrong table '
    reason.dispatchEvent(new Event('input'))
    modalButton('agent.reject').click()
    await flushPromises()

    expect(sentBodies(testApp)).toEqual([
      { decisions: [{ id: 1, approved: false, reason: 'Wrong table' }] },
    ])
    expect(decisions(wrapper)).toEqual(['agent.rejected'])
    expect(texts(headerButtons(wrapper))).toEqual([
      'agent.reject',
      'agent.approve',
    ])
    expect(activity(wrapper).text()).toBe('agent.waitingForApproval')
  })

  test('re-reads the reply when a step was already decided elsewhere', async () => {
    testApp.dontFailOnErrorResponses()
    mockApprovals(testApp, chat.uuid, [
      409,
      { error: 'ERROR_AGENT_TOOL_APPROVAL_NOT_PENDING', detail: 'Decided.' },
    ])
    const wrapper = await openWaitingReply(
      [approval(1), approval(2)],
      page([prompt, reply('waiting', [approval(1, 'rejected'), approval(2)])])
    )

    await headerButtons(wrapper)[1].trigger('click')
    await flushPromises()

    expect(messageReads()).toHaveLength(2)
    expect(decisions(wrapper)).toEqual(['agent.rejected'])
    expect(testApp.store.state.toast.items).toHaveLength(1)
    expect(headerButtons(wrapper)[1].element.disabled).toBe(false)
  })

  test('a busy workspace keeps the step pending with the agent copy', async () => {
    testApp.dontFailOnErrorResponses()
    mockApprovals(testApp, chat.uuid, [
      429,
      { error: 'ERROR_AGENT_BUSY', detail: 'Busy.' },
    ])
    const wrapper = await openWaitingReply([approval(1)])

    await headerButtons(wrapper)[1].trigger('click')
    await flushPromises()

    expect(
      testApp.store.state.toast.items.map(({ title, message }) => [
        title,
        message,
      ])
    ).toEqual([['clientHandler.notCompletedTitle', 'agent.agentsBusy']])
    expect(title(wrapper)).toBe('agent.approvalRequest')
  })

  test('a decision moves focus on and announces its outcome', async () => {
    mockApprovals(
      testApp,
      chat.uuid,
      reply('waiting', [approval(1, 'approved'), approval(2)]),
      reply('running', [approval(1, 'approved'), approval(2, 'approved')], {
        runId: 'run-2',
      })
    )
    const wrapper = await openWaitingReply([approval(1), approval(2)])
    const approveFirst = itemButtons(items(wrapper)[0])[1]

    approveFirst.element.focus()
    await approveFirst.trigger('click')
    await flushPromises()
    expect(document.activeElement).toBe(headerButtons(wrapper)[1].element)
    expect(announcement(wrapper)).toBe('agent.approved')

    await headerButtons(wrapper)[1].trigger('click')
    await flushPromises()
    expect(document.activeElement).toBe(card(wrapper).element)
    expect(announcement(wrapper)).toBe('agent.approved')
  })

  test('a message sent while another tab paused the reply shows the approval', async () => {
    testApp.dontFailOnErrorResponses()
    mockSendMessage(testApp, chat.uuid, [
      409,
      { error: 'ERROR_AGENT_CONVERSATION_WAITING_FOR_APPROVAL' },
    ])
    mockConversations(testApp, page([chat]))
    mockMessages(
      testApp,
      chat.uuid,
      page([prompt]),
      page([prompt, reply('waiting', [approval(1)])])
    )
    const wrapper = await mount()
    await selectConversation(wrapper, chat.title)

    await sendMessage(wrapper, 'Next')

    expect(wrapper.get('#agent-chat-send-error').text()).toBe(
      'agent.conversationWaitingForApproval'
    )
    expect(title(wrapper)).toBe('agent.approvalRequest')
    expect(composer(wrapper).element.disabled).toBe(true)
    expect(composer(wrapper).element.readOnly).toBe(false)
  })

  test('only a member who can send decides', async () => {
    allowed.value = (operation) =>
      operation !== 'agent_application.create_message'
    const wrapper = await openWaitingReply([approval(1)])

    expect(composerExists(wrapper)).toBe(false)
    expect(
      headerButtons(wrapper).map((button) => button.element.disabled)
    ).toEqual([true, true])
  })
})
