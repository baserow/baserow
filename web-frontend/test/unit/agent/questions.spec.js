import { afterEach, beforeEach, describe, expect, test } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { pendingApprovals } from '@baserow/modules/agent/utils/replies'
import {
  conversation,
  createAgentPage,
  destroyAgentPage,
  incompleteConfiguration,
  message,
  mockApprovals,
  mockConfiguration,
  mockConversations,
  mockMessages,
  conversationsPage,
  page,
  selectConversation,
  sentBodies,
} from './helpers'

const chat = conversation('conversation-a', 'Conversation A')
const prompt = message('m1', 'Reply to the new message', { id: 1 })
const QUESTION = 'Which customer is the message from?'

const questionStep = (id, status = 'waiting') => ({
  id: `step-${id}`,
  tool: 'ask_person',
  status,
  changes_data: false,
  input: { question: QUESTION },
  facts: {},
})
const createStep = (id) => ({
  id: `step-${id}`,
  tool: 'create_rows',
  status: 'waiting',
  changes_data: true,
  input: { requested_count: 1, values: { table_id: 1, rows: [] } },
  facts: {},
})
const approval = (
  id,
  { status = 'pending', tool = 'ask_person', answer = '' } = {}
) => ({
  id,
  step_id: `step-${id}`,
  pause: 1,
  tool,
  status,
  reason: '',
  answer,
})
const reply = (approvals, steps, status = 'waiting') => ({
  ...message('reply-2', '', { id: 2, role: 'assistant', status, steps }),
  approvals,
})
const askedReply = (questionApproval = approval(1)) =>
  reply([questionApproval], [questionStep(1)])

const texts = (elements) => elements.map((element) => element.text())
const card = (wrapper) => wrapper.get('.agent-question')
const answerInput = (wrapper) => card(wrapper).find('textarea')
const buttons = (wrapper) =>
  card(wrapper).findAll('.agent-question__actions button')
const sendButton = (wrapper) => buttons(wrapper)[1]
const dismissButton = (wrapper) => buttons(wrapper)[0]

describe('Agent questions', () => {
  let testApp, agent, mount, allowed

  beforeEach(async () => {
    ;({ testApp, agent, mount, allowed } = await createAgentPage())
    testApp.authenticate({ id: 1 })
  })

  afterEach(() => destroyAgentPage(testApp))

  async function openReply(saved) {
    mockConversations(
      testApp,
      conversationsPage([
        { ...chat, pending_approval_count: pendingApprovals(saved).length },
      ])
    )
    mockMessages(testApp, chat.uuid, page([prompt, saved]))
    const wrapper = await mount()
    await selectConversation(wrapper, chat.title)
    return wrapper
  }

  test('a reply waiting on a question shows it in its own card', async () => {
    const wrapper = await openReply(askedReply())

    expect(card(wrapper).get('.agent-question__title').text()).toBe(
      'agent.questionTitle'
    )
    expect(card(wrapper).get('.agent-question__question').text()).toBe(QUESTION)
    expect(card(wrapper).attributes('role')).toBe('group')
    expect(wrapper.find('.agent-approval').exists()).toBe(false)
    expect(wrapper.find('.chat-step-group').exists()).toBe(false)
  })

  test('sending an answer decides the question with it', async () => {
    mockApprovals(
      testApp,
      chat.uuid,
      reply(
        [approval(1, { status: 'approved', answer: 'Acme' })],
        [questionStep(1, 'done')],
        'running'
      )
    )
    const wrapper = await openReply(askedReply())
    expect(texts(buttons(wrapper))).toEqual([
      'agent.questionDismiss',
      'agent.questionSend',
    ])
    expect(answerInput(wrapper).attributes('maxlength')).toBe('10000')
    expect(sendButton(wrapper).element.disabled).toBe(true)
    await answerInput(wrapper).setValue('   ')
    expect(sendButton(wrapper).element.disabled).toBe(true)

    await answerInput(wrapper).setValue('Acme')
    await sendButton(wrapper).trigger('click')
    await flushPromises()

    expect(sentBodies(testApp)).toEqual([
      { decisions: [{ id: 1, approved: true, answer: 'Acme' }] },
    ])
    expect(card(wrapper).get('.agent-question__answer').text()).toBe('Acme')
    expect(document.activeElement).toBe(card(wrapper).element)
  })

  test('dismissing decides the question without an answer', async () => {
    mockApprovals(
      testApp,
      chat.uuid,
      reply(
        [approval(1, { status: 'rejected' })],
        [questionStep(1, 'rejected')]
      )
    )
    const wrapper = await openReply(askedReply())
    await answerInput(wrapper).setValue('Typed but not sent')

    await dismissButton(wrapper).trigger('click')
    await flushPromises()

    expect(sentBodies(testApp)).toEqual([
      { decisions: [{ id: 1, approved: false }] },
    ])
  })

  test('a viewer who cannot decide reads the question only', async () => {
    allowed.value = (operation) =>
      operation !== 'agent_application.approve_tool_calls'
    const wrapper = await openReply(askedReply())

    expect(answerInput(wrapper).exists()).toBe(false)
    expect(card(wrapper).findAll('button')).toHaveLength(0)
    expect(card(wrapper).text()).toContain('agent.questionReadOnly')
    expect(card(wrapper).get('.agent-question__question').text()).toBe(QUESTION)
  })

  test('an approver keeps the form, disabled, while the agent is not ready', async () => {
    mockConfiguration(testApp, incompleteConfiguration('instructions'))
    const wrapper = await openReply(askedReply())

    expect(answerInput(wrapper).element.disabled).toBe(true)
    expect(buttons(wrapper).map((button) => button.element.disabled)).toEqual([
      true,
      true,
    ])
    expect(card(wrapper).text()).not.toContain('agent.questionReadOnly')
  })

  test('a refused answer stays typed and can be sent again', async () => {
    testApp.dontFailOnErrorResponses()
    mockApprovals(testApp, chat.uuid, [
      400,
      { error: 'ERROR_AGENT_TOOL_DECISION_INVALID', detail: 'Invalid.' },
    ])
    const wrapper = await openReply(askedReply())
    await answerInput(wrapper).setValue('Acme')

    await sendButton(wrapper).trigger('click')
    await flushPromises()

    expect(sentBodies(testApp)).toHaveLength(1)
    expect(answerInput(wrapper).element.value).toBe('Acme')
    expect(buttons(wrapper).map((button) => button.element.disabled)).toEqual([
      false,
      false,
    ])
  })

  test.each([
    ['approved', 'Acme', 'agent.questionAnswered'],
    ['rejected', '', 'agent.questionDismissed'],
  ])(
    'a question that was %s shows its outcome',
    async (status, answer, outcome) => {
      const wrapper = await openReply(
        askedReply(approval(1, { status, answer }))
      )

      expect(card(wrapper).get('.agent-question__decision').text()).toBe(
        outcome
      )
      expect(card(wrapper).find('.agent-question__answer').exists()).toBe(
        Boolean(answer)
      )
      if (answer) {
        expect(card(wrapper).get('.agent-question__answer').text()).toBe(answer)
      }
      expect(answerInput(wrapper).exists()).toBe(false)
      expect(card(wrapper).findAll('button')).toHaveLength(0)
    }
  )

  test('a pause holding a question and a change keeps the question out of the approval card', async () => {
    mockApprovals(testApp, chat.uuid, askedReply())
    const wrapper = await openReply(
      reply(
        [approval(1), approval(2, { tool: 'create_rows' })],
        [questionStep(1), createStep(2)]
      )
    )

    expect(wrapper.findAll('.agent-question')).toHaveLength(1)
    const approvals = wrapper.findAll('.agent-approval')
    expect(approvals).toHaveLength(1)
    expect(
      approvals[0].findAll('.agent-approval__tool').map((tool) => tool.text())
    ).toEqual(['create_rows'])
    await approvals[0]
      .findAll('.agent-approval__actions button')
      .at(-1)
      .trigger('click')
    await flushPromises()

    expect(sentBodies(testApp)).toEqual([
      { decisions: [{ id: 2, approved: true }] },
    ])
  })

  test('the pending approvals menu sends a question to its conversation without actions', async () => {
    const asking = conversation('asking', 'Asking')
    mockConversations(testApp, conversationsPage([asking]))
    mockMessages(testApp, asking.uuid, page([prompt, askedReply()]))
    testApp.mock
      .onGet('/agent/10/pending-approvals/')
      .reply(200, page([{ ...askedReply(), conversation: asking }]))
    await testApp.store.dispatch('application/forceUpdate', {
      application: agent,
      data: { pending_count: 1 },
    })
    const wrapper = await mount({ stubs: { Teleport: false } })
    await wrapper.get('.agent-application__approvals').trigger('click')
    await flushPromises()

    const menu = testApp.body.get('.agent-pending-approvals')
    expect(menu.find('.agent-approval').exists()).toBe(false)
    const row = menu.get('.agent-pending-approvals__question')
    expect(row.text()).toContain('agent.questionNeedsAnswer')
    expect(row.findAll('button')).toHaveLength(1)
    await row.get('button').trigger('click')
    await flushPromises()

    expect(card(wrapper).get('.agent-question__question').text()).toBe(QUESTION)
  })

  test('the pending approvals menu links a question and still decides the change held with it', async () => {
    const held = reply(
      [approval(1), approval(2, { tool: 'create_rows' })],
      [questionStep(1), createStep(2)]
    )
    mockApprovals(testApp, chat.uuid, held)
    testApp.mock
      .onGet('/agent/10/pending-approvals/')
      .reply(200, page([{ ...held, conversation: chat }]))
    await testApp.store.dispatch('application/forceUpdate', {
      application: agent,
      data: { pending_count: 2 },
    })
    const wrapper = await mount({ stubs: { Teleport: false } })
    await wrapper.get('.agent-application__approvals').trigger('click')
    await flushPromises()

    const menu = testApp.body.get('.agent-pending-approvals')
    expect(menu.get('.agent-pending-approvals__question').text()).toContain(
      'agent.questionNeedsAnswer'
    )
    expect(texts(menu.findAll('.agent-approval__tool'))).toEqual([
      'create_rows',
    ])
    await menu
      .get('.agent-approval__actions button:last-child')
      .trigger('click')
    await flushPromises()

    expect(sentBodies(testApp)).toEqual([
      { decisions: [{ id: 2, approved: true }] },
    ])
  })

  test('the pending approvals menu can approve an action after a question was answered', async () => {
    const action = approval(2, { tool: 'create_rows' })
    const response = reply(
      [
        approval(1, { status: 'approved', answer: 'Acme' }),
        approval(3, { tool: 'create_rows', status: 'approved' }),
        action,
      ],
      [questionStep(1, 'done'), createStep(3), createStep(2)]
    )
    mockApprovals(testApp, chat.uuid, response)
    testApp.mock.onGet('/agent/10/pending-approvals/').reply(
      200,
      page([
        {
          ...response,
          conversation: chat,
          approvals: [approval(3, { tool: 'create_rows' }), action],
          steps: [createStep(3), createStep(2)],
        },
      ])
    )
    await testApp.store.dispatch('application/forceUpdate', {
      application: agent,
      data: { pending_count: 1 },
    })
    const wrapper = await mount({ stubs: { Teleport: false } })
    await wrapper.get('.agent-application__approvals').trigger('click')
    await flushPromises()

    const menu = testApp.body.get('.agent-pending-approvals')
    await menu
      .get('.agent-approval__item-actions button:last-child')
      .trigger('click')
    await flushPromises()

    expect(sentBodies(testApp)).toEqual([
      { decisions: [{ id: 3, approved: true }] },
    ])
    expect(menu.find('.agent-pending-approvals__question').exists()).toBe(false)
    expect(menu.findAll('.agent-approval__tool')).toHaveLength(1)
  })
})
