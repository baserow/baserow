import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import * as vueI18n from 'vue-i18n'
import service from '@baserow/modules/core/services/chatRuns'
import { registerRealtimeEvents } from '@baserow/modules/agent/realtime'
import { pendingApprovals } from '@baserow/modules/agent/utils/replies'
import {
  agentData,
  composer,
  composerExists,
  conversation,
  conversationsPage,
  createAgentPage,
  deferredReply,
  destroyAgentPage,
  message,
  messages,
  mockAgent,
  mockApprovals,
  mockConversations,
  mockMessages,
  mockSendMessage,
  mockStartConversation,
  page,
  selectConversation,
  selected,
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
    values: { table_id: 1, rows: [{ Name: `Company ${id}` }] },
  },
  facts: {},
})
const approval = (
  id,
  status = 'pending',
  { reason = '', pause = 1, tool = 'create_rows' } = {}
) => ({
  id,
  step_id: `step-${id}`,
  tool,
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
const alwaysAllow = (wrapper) =>
  card(wrapper).find('.agent-approval__always-allow')
const activity = (wrapper) => wrapper.get('.chat-composer__activity')
const waitingDot = (wrapper) =>
  wrapper.find('.agent-conversations__status--waiting').exists()
const inModal = (selector) => document.body.querySelector(selector)
const modalButton = (text) =>
  [
    ...document.body.querySelectorAll('.agent-reject-modal__actions button'),
  ].find((button) => button.textContent.trim() === text)

describe('Agent tool approvals', () => {
  let testApp, agent, mount, allowed, api, streams, cursor

  beforeEach(async () => {
    ;({ testApp, agent, mount, allowed } = await createAgentPage())
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
  const configurationReads = () =>
    testApp.mock.history.get.filter(
      ({ url }) => url === '/agent/10/configuration/'
    ).length

  function showAlwaysAllowTools() {
    const useI18n = vueI18n.useI18n
    vi.spyOn(vueI18n, 'useI18n').mockImplementation((...args) => {
      const composer = useI18n(...args)
      return {
        ...composer,
        t: (key, values, ...rest) =>
          key === 'agent.alwaysAllowTools'
            ? `Always allow ${values.tools}`
            : composer.t(key, values, ...rest),
      }
    })
  }

  async function openReply(saved, ...later) {
    mockConversations(
      testApp,
      conversationsPage([
        { ...chat, pending_approval_count: pendingApprovals(saved).length },
      ])
    )
    mockMessages(testApp, chat.uuid, page([prompt, saved]), ...later)
    const wrapper = await mount()
    await selectConversation(wrapper, chat.title)
    return wrapper
  }
  const openWaitingReply = (approvals, ...later) =>
    openReply(reply('waiting', approvals), ...later)

  test.each(['approved', 'rejected'])(
    'keeps a saved %s decision when an older message snapshot arrives',
    async (status) => {
      const reading = deferredReply()
      const initial = [approval(1), approval(2), approval(3)]
      mockApprovals(
        testApp,
        chat.uuid,
        reply('waiting', [approval(1, status), approval(2), approval(3)]),
        reply(
          'running',
          [
            approval(1, status),
            approval(2, 'approved'),
            approval(3, 'approved'),
          ],
          { runId: 'run-2' }
        )
      )
      const wrapper = await openWaitingReply(initial, reading.reply)
      testApp.getRegistry().get('chatRunType', 'agent').refreshChat(chat.id)
      await flushPromises()

      if (status === 'approved') {
        await itemButtons(items(wrapper)[0])[1].trigger('click')
      } else {
        await itemButtons(items(wrapper)[0])[0].trigger('click')
        await flushPromises()
        modalButton('agent.reject').click()
      }
      await flushPromises()
      expect(decisions(wrapper)).toEqual([`agent.${status}`])

      reading.resolve(200, page([prompt, reply('waiting', initial)]))
      await flushPromises()

      expect(decisions(wrapper)).toEqual([`agent.${status}`])
      await headerButtons(wrapper)[1].trigger('click')
      await flushPromises()
      expect(sentBodies(testApp)).toEqual([
        { decisions: [{ id: 1, approved: status === 'approved' }] },
        {
          decisions: [
            { id: 2, approved: true },
            { id: 3, approved: true },
          ],
        },
      ])
      expect(messageReads()).toHaveLength(2)
    }
  )

  test.each(['earlier pause', 'omitted approvals'])(
    'keeps a later pause when a snapshot has %s',
    async (older) => {
      const reading = deferredReply()
      mockApprovals(
        testApp,
        chat.uuid,
        reply('running', [approval(1, 'approved')], { runId: 'run-2' }),
        reply('running', [approval(1, 'approved'), approval(2, 'approved')], {
          runId: 'run-3',
        })
      )
      const wrapper = await openWaitingReply([approval(1)], reading.reply)
      testApp.getRegistry().get('chatRunType', 'agent').refreshChat(chat.id)
      await flushPromises()
      await headerButtons(wrapper)[1].trigger('click')
      await flushPromises()
      await finish(
        'run-2',
        reply(
          'waiting',
          [approval(1, 'approved'), approval(2, 'pending', { pause: 2 })],
          {
            steps: [read, heldStep(1, 'done'), heldStep(2, 'waiting')],
          }
        )
      )
      const snapshot = reply('running', [approval(1, 'approved')], {
        runId: 'run-2',
      })
      if (older === 'omitted approvals') delete snapshot.approvals
      reading.resolve(200, page([prompt, snapshot]))
      await flushPromises()

      expect(cards(wrapper)).toHaveLength(2)
      expect(decisions(wrapper)).toEqual(['agent.approved'])
      expect(activity(wrapper).text()).toBe('agent.waitingForApproval')
      expect(composer(wrapper).element.disabled).toBe(true)
      await wrapper
        .findAll('.agent-approval__actions button')[1]
        .trigger('click')
      await flushPromises()
      expect(sentBodies(testApp).at(-1)).toEqual({
        decisions: [{ id: 2, approved: true }],
      })
      expect(messageReads()).toHaveLength(2)
    }
  )

  test('a delayed run snapshot cannot undo decisions made after a reconnect', async () => {
    const reading = deferredReply()
    mockApprovals(
      testApp,
      chat.uuid,
      reply('running', [approval(1, 'approved')], { runId: 'run-2' }),
      reply('running', [approval(1, 'approved'), approval(2, 'approved')], {
        runId: 'run-3',
      })
    )
    const wrapper = await openWaitingReply([approval(1)], reading.reply)
    await headerButtons(wrapper)[1].trigger('click')
    await flushPromises()
    testApp.getRegistry().get('chatRunType', 'agent').refreshChat(chat.id)
    await flushPromises()
    const paused = reply(
      'waiting',
      [approval(1, 'approved'), approval(2, 'pending', { pause: 2 })],
      { steps: [read, heldStep(1, 'done'), heldStep(2, 'waiting')] }
    )
    reading.resolve(200, page([prompt, paused]))
    await flushPromises()
    await wrapper.findAll('.agent-approval__actions button')[1].trigger('click')
    await flushPromises()
    expect(decisions(wrapper)).toEqual(['agent.approved', 'agent.approved'])

    await finish('run-2', paused)

    expect(decisions(wrapper)).toEqual(['agent.approved', 'agent.approved'])
    expect(wrapper.findAll('.agent-approval__actions button')).toHaveLength(0)
    expect(stop(wrapper).exists()).toBe(true)
  })

  test('accepts a newer snapshot with another pause and pending approval', async () => {
    const reading = deferredReply()
    mockApprovals(
      testApp,
      chat.uuid,
      reply('running', [approval(1, 'approved')], { runId: 'run-2' })
    )
    const wrapper = await openWaitingReply([approval(1)], reading.reply)
    await headerButtons(wrapper)[1].trigger('click')
    await flushPromises()
    testApp.getRegistry().get('chatRunType', 'agent').refreshChat(chat.id)
    await flushPromises()
    reading.resolve(
      200,
      page([
        prompt,
        reply(
          'waiting',
          [approval(1, 'approved'), approval(2, 'pending', { pause: 2 })],
          {
            steps: [read, heldStep(1, 'done'), heldStep(2, 'waiting')],
          }
        ),
      ])
    )
    await flushPromises()

    expect(cards(wrapper)).toHaveLength(2)
    expect(decisions(wrapper)).toEqual(['agent.approved'])
    expect(texts(wrapper.findAll('.agent-approval__actions button'))).toEqual([
      'agent.reject',
      'agent.approve',
    ])
  })

  test('a reply that pauses asks for approval of its step', async () => {
    const useI18n = vueI18n.useI18n
    vi.spyOn(vueI18n, 'useI18n').mockImplementation((...args) => {
      const composer = useI18n(...args)
      return {
        ...composer,
        t: (key, ...values) =>
          key === 'agent.waitingForApproval'
            ? 'Waiting for your approval'
            : composer.t(key, ...values),
      }
    })
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
      'agent.toolCreateRowsRequestedCount - 3'
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
      'Waiting for your approval'
    )
    expect(activity(wrapper).classes()).toEqual(
      expect.arrayContaining([
        'chat-composer__activity--visible',
        'chat-composer__activity--waiting',
      ])
    )
    expect(activity(wrapper).text()).toBe('Waiting for your approval')
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

  test.each([
    ['stopped', 'statusStopped', 'iconoir-minus-circle'],
    ['failed', 'statusFailed', 'iconoir-warning-triangle'],
  ])(
    'an approved step that ended %s says so next to the decision',
    async (stepStatus, label, icon) => {
      const wrapper = await openReply(
        reply('failed', [approval(1, 'approved')], { stepStatus })
      )

      const item = items(wrapper)[0]
      const status = item.get('.agent-approval__step-status')
      expect(status.text()).toBe(`toolPresentation.${label}`)
      expect(status.find(`.${icon}`).exists()).toBe(true)
      expect(item.get('.agent-approval__item-title').text()).toBe(
        'agent.toolCreateRowsRequestedCount - 3'
      )
      expect(decisions(wrapper)).toEqual(['agent.approved'])
    }
  )

  test('an approved step that partly failed lists the items it missed', async () => {
    const partlyDone = {
      ...heldStep(1, 'done'),
      item_errors: [{ item: 'Company 1', code: 'conflict', message: 'Taken.' }],
    }
    const wrapper = await openReply(
      reply('completed', [approval(1, 'approved')], {
        steps: [read, partlyDone],
      })
    )

    const item = items(wrapper)[0]
    const status = item.get('.agent-approval__step-status')
    expect(status.text()).toBe('toolPresentation.statusPartial')
    expect(status.find('.iconoir-warning-circle').exists()).toBe(true)
    expect(item.get('.agent-approval__item-note').text()).toBe(
      'Company 1: Taken.'
    )
  })

  test('approving all steps follows the resumed reply', async () => {
    const decision = deferredReply()
    mockApprovals(testApp, chat.uuid, decision.reply)
    const wrapper = await openWaitingReply([approval(1), approval(2)])
    await testApp.store.dispatch('application/forceUpdate', {
      application: agent,
      data: { pending_count: 2 },
    })
    expect(waitingDot(wrapper)).toBe(true)
    const reads = configurationReads()

    await headerButtons(wrapper)[1].trigger('click')
    await flushPromises()
    expect(
      card(wrapper)
        .findAll('button:not(.agent-approval__details-toggle)')
        .map((button) => button.element.disabled)
    ).toEqual(Array(7).fill(true))
    const approved = [approval(1, 'approved'), approval(2, 'approved')]
    decision.resolve(200, reply('running', approved, { runId: 'run-2' }))
    await flushPromises()
    expect(title(wrapper)).toBe('agent.approvalReviewed')
    expect(messages(wrapper)).toEqual(['Add the companies', 'Adding them.'])
    expect(waitingDot(wrapper)).toBe(false)
    // Success waits for the ordinary count event, with no speculative arithmetic
    // or extra application read.
    expect(agent.pending_count).toBe(2)
    expect(
      testApp.mock.history.get.filter(({ url }) => url === '/applications/10/')
    ).toHaveLength(0)

    expect(sentBodies(testApp)).toEqual([
      {
        decisions: [
          { id: 1, approved: true },
          { id: 2, approved: true },
        ],
      },
    ])
    expect(configurationReads()).toBe(reads)
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

  test('always allow approves every pending step and re-reads the configuration', async () => {
    mockApprovals(
      testApp,
      chat.uuid,
      reply('running', [approval(1, 'approved'), approval(2, 'approved')], {
        runId: 'run-2',
      })
    )
    showAlwaysAllowTools()
    const wrapper = await openWaitingReply([approval(1), approval(2)])
    const reads = configurationReads()
    expect(alwaysAllow(wrapper).text()).toBe(
      'Always allow agent.toolCreateRows'
    )

    await alwaysAllow(wrapper).trigger('click')
    await flushPromises()

    expect(sentBodies(testApp)).toEqual([
      {
        decisions: [
          { id: 1, approved: true },
          { id: 2, approved: true },
        ],
        always_allow: true,
      },
    ])
    expect(configurationReads()).toBe(reads + 1)
    expect(alwaysAllow(wrapper).exists()).toBe(false)
  })

  test('always allow names each distinct tool it stops asking for', async () => {
    showAlwaysAllowTools()
    const wrapper = await openWaitingReply([
      approval(1),
      approval(2, 'pending', { tool: 'delete_rows' }),
      approval(3),
    ])

    expect(alwaysAllow(wrapper).text()).toBe(
      'Always allow agent.toolCreateRows and agent.toolDeleteRows'
    )
  })

  test('always allow is offered only to members who can edit the configuration', async () => {
    allowed.value = (operation) => operation !== 'application.update'
    const wrapper = await openWaitingReply([approval(1)])

    expect(alwaysAllow(wrapper).exists()).toBe(false)
    expect(headerButtons(wrapper)).toHaveLength(2)
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

  test.each(['cancel', 'Escape'])(
    'keeps rejection keyboard focus in the dialog and restores it on %s',
    async (dismiss) => {
      const wrapper = await openWaitingReply([approval(1)])
      const opener = headerButtons(wrapper)[0]
      // Pointer opening must return to its actual trigger, even when it wasn't
      // focused. Escape exercises opening from a keyboard-focused trigger.
      headerButtons(wrapper)[dismiss === 'cancel' ? 1 : 0].element.focus()
      await opener.trigger('click')
      await flushPromises()

      const dialog = inModal('.agent-reject-modal')
      const reason = dialog.querySelector('textarea')
      const reject = modalButton('agent.reject')
      expect(dialog.getAttribute('role')).toBe('dialog')
      expect(dialog.getAttribute('aria-modal')).toBe('true')
      expect(
        document.getElementById(dialog.getAttribute('aria-labelledby'))
      ).toBe(dialog.querySelector('.box__title'))
      expect(document.activeElement).toBe(reason)

      const backwards = new KeyboardEvent('keydown', {
        key: 'Tab',
        shiftKey: true,
        bubbles: true,
        cancelable: true,
      })
      reason.dispatchEvent(backwards)
      expect(backwards.defaultPrevented).toBe(true)
      expect(document.activeElement).toBe(reject)

      const forwards = new KeyboardEvent('keydown', {
        key: 'Tab',
        bubbles: true,
        cancelable: true,
      })
      reject.dispatchEvent(forwards)
      expect(forwards.defaultPrevented).toBe(true)
      expect(document.activeElement).toBe(reason)
      expect(sentBodies(testApp)).toEqual([])

      if (dismiss === 'cancel') modalButton('action.cancel').click()
      else window.dispatchEvent(new KeyboardEvent('keyup', { key: 'Escape' }))
      await flushPromises()
      expect(document.activeElement).toBe(opener.element)
      expect(sentBodies(testApp)).toEqual([])
    }
  )

  test('re-reads the reply and count when a step was already decided elsewhere', async () => {
    testApp.dontFailOnErrorResponses()
    mockAgent(testApp, { ...agentData, pending_count: 1 })
    mockApprovals(testApp, chat.uuid, [
      409,
      { error: 'ERROR_AGENT_TOOL_APPROVAL_NOT_PENDING', detail: 'Decided.' },
    ])
    const wrapper = await openWaitingReply(
      [approval(1), approval(2)],
      page([prompt, reply('waiting', [approval(1, 'rejected'), approval(2)])])
    )

    await testApp.store.dispatch('application/forceUpdate', {
      application: agent,
      // Another tab's count event already includes the decision.
      data: { pending_count: 1 },
    })
    await headerButtons(wrapper)[1].trigger('click')
    await flushPromises()

    expect(
      testApp.store.getters['application/get'](agentData.id).pending_count
    ).toBe(1)
    expect(messageReads()).toHaveLength(2)
    expect(decisions(wrapper)).toEqual(['agent.rejected'])
    expect(testApp.store.state.toast.items).toHaveLength(1)
    expect(headerButtons(wrapper)[1].element.disabled).toBe(false)
  })

  async function updatedElsewhere(listed, count, runId = null) {
    const receivers = {}
    registerRealtimeEvents({
      registerEvent: (type, handler) => (receivers[type] = handler),
    })
    receivers.agent_conversation_activity(
      { store: testApp.store },
      {
        agent_id: agentData.id,
        conversation_uuid: listed.uuid,
        conversation: {
          ...listed,
          run_id: runId,
          pending_approval_count: count,
        },
      }
    )
    await flushPromises()
  }

  test('re-reads the open reply only when another tab changed its pending count', async () => {
    const wrapper = await openWaitingReply(
      [approval(1), approval(2)],
      page([prompt, reply('waiting', [approval(1, 'approved'), approval(2)])])
    )

    await updatedElsewhere(chat, 2)
    expect(messageReads()).toHaveLength(1)

    await updatedElsewhere(chat, 1)
    expect(messageReads()).toHaveLength(2)
    expect(decisions(wrapper)).toEqual(['agent.approved'])
  })

  test('an older successful partial response cannot restore the waiting dot', async () => {
    const decision = deferredReply()
    mockApprovals(testApp, chat.uuid, decision.reply)
    const latest = reply('completed', [
      approval(1, 'approved'),
      approval(2, 'approved'),
    ])
    const wrapper = await openWaitingReply(
      [approval(1), approval(2)],
      page([prompt, latest])
    )
    await itemButtons(items(wrapper)[0])[1].trigger('click')
    await flushPromises()
    await updatedElsewhere(chat, 0)
    expect(waitingDot(wrapper)).toBe(false)

    decision.resolve(
      200,
      reply('waiting', [approval(1, 'approved'), approval(2)])
    )
    await flushPromises()

    expect(decisions(wrapper)).toEqual(['agent.approved', 'agent.approved'])
    expect(waitingDot(wrapper)).toBe(false)
  })

  test('a pause arriving while following the run does not re-read the reply', async () => {
    let started
    mockStartConversation(testApp, ({ data }) => {
      const body = JSON.parse(data)
      started = conversation(body.uuid, body.content, undefined, 5)
      return [
        200,
        {
          conversation: started,
          message: message(body.message_uuid, body.content, { id: 1 }),
          reply: reply('running', [], { runId: 'run-1' }),
        },
      ]
    })
    const wrapper = await mount()
    await sendMessage(wrapper, 'Add the companies')

    await updatedElsewhere(started, 1)

    expect(messageReads()).toHaveLength(0)
    await finish('run-1', reply('waiting', [approval(1)]))
    expect(title(wrapper)).toBe('agent.approvalRequest')
  })

  test('an update from another tab moves the waiting dot of a closed conversation', async () => {
    const other = conversation('conversation-b', 'Conversation B')
    mockConversations(testApp, conversationsPage([chat, other]))
    mockMessages(testApp, chat.uuid, page([prompt]))
    const wrapper = await mount()
    await selectConversation(wrapper, chat.title)
    expect(waitingDot(wrapper)).toBe(false)

    await updatedElsewhere(other, 1)

    expect(waitingDot(wrapper)).toBe(true)
  })

  test('the header pill cycles only loaded waiting conversations without fetching a list', async () => {
    const row = (uuid, updatedOn, count) => ({
      ...conversation(uuid, uuid, updatedOn),
      pending_approval_count: count,
    })
    const loaded = [
      row('newest', '2026-10-14T10:00:03Z', 1),
      row('idle', '2026-10-14T10:00:02Z', 0),
      row('middle', '2026-10-14T10:00:01Z', 2),
    ]
    mockConversations(testApp, conversationsPage(loaded, 'next'))
    for (const { uuid } of loaded) mockMessages(testApp, uuid, page([]))
    await testApp.store.dispatch('application/forceUpdate', {
      application: agent,
      // Most waiting conversations are outside the loaded page.
      data: { pending_count: 106 },
    })
    const wrapper = await mount()
    const pill = () => wrapper.find('.agent-application__approvals')
    expect(pill().text()).toBe('agent.approvalsWaiting - 106')

    const opened = []
    for (let click = 0; click < 6; click++) {
      await pill().trigger('click')
      await flushPromises()
      opened.push(
        selected(wrapper).get('.agent-conversations__item-name').text()
      )
    }

    expect(opened).toEqual([
      'newest',
      'middle',
      'newest',
      'middle',
      'newest',
      'middle',
    ])
    expect(
      testApp.mock.history.get.filter(
        ({ url }) => url === '/agent/10/conversations/'
      )
    ).toHaveLength(1)
    await testApp.store.dispatch('application/forceUpdate', {
      application: agent,
      data: { pending_count: 0 },
    })
    await flushPromises()
    expect(pill().exists()).toBe(false)
  })

  test('the pill preserves the selection when no loaded conversation is waiting', async () => {
    const idle = { ...conversation('idle', 'Idle'), pending_approval_count: 0 }
    mockConversations(testApp, conversationsPage([idle], 'next'))
    mockMessages(testApp, idle.uuid, page([]))
    await testApp.store.dispatch('application/forceUpdate', {
      application: agent,
      data: { pending_count: 106 },
    })
    const wrapper = await mount()
    await selectConversation(wrapper, 'Idle')
    for (let click = 0; click < 6; click++) {
      await wrapper.get('.agent-application__approvals').trigger('click')
      await flushPromises()
    }
    expect(
      selected(wrapper).get('.agent-conversations__item-name').text()
    ).toBe('Idle')
    expect(
      testApp.mock.history.get.filter(
        ({ url }) => url === '/agent/10/conversations/'
      )
    ).toHaveLength(1)
  })

  test('a list read started before a decision keeps the decided count', async () => {
    const stale = deferredReply()
    mockConversations(
      testApp,
      conversationsPage([{ ...chat, pending_approval_count: 1 }]),
      stale.reply,
      conversationsPage([{ ...chat, pending_approval_count: 0 }])
    )
    mockMessages(
      testApp,
      chat.uuid,
      page([prompt, reply('waiting', [approval(1)])])
    )
    mockApprovals(
      testApp,
      chat.uuid,
      reply('running', [approval(1, 'approved')], { runId: 'run-2' })
    )
    const wrapper = await mount()
    await selectConversation(wrapper, chat.title)
    testApp.getRegistry().get('chatRunType', 'agent').refreshChat(chat.id)
    await flushPromises()

    await headerButtons(wrapper)[1].trigger('click')
    await flushPromises()
    stale.resolve(
      200,
      conversationsPage([{ ...chat, pending_approval_count: 1 }])
    )
    await flushPromises()

    expect(waitingDot(wrapper)).toBe(false)
  })

  test.each([false, true])(
    'reconciles an uncertain decision with committed=%s',
    async (committed) => {
      testApp.dontFailOnErrorResponses()
      const decision = deferredReply()
      mockApprovals(testApp, chat.uuid, decision.reply)
      mockAgent(testApp, {
        ...agentData,
        pending_count: committed ? 2 : 3,
      })
      const wrapper = await openWaitingReply(
        [approval(1), approval(2)],
        page([
          prompt,
          reply('waiting', [
            approval(1, committed ? 'approved' : 'pending'),
            approval(2),
          ]),
        ])
      )
      await testApp.store.dispatch('application/forceUpdate', {
        application: agent,
        data: { pending_count: 3 },
      })
      const pendingCount = () =>
        testApp.store.getters['application/get'](agentData.id).pending_count

      await itemButtons(items(wrapper)[0])[1].trigger('click')
      expect(pendingCount()).toBe(3)
      await flushPromises()
      if (committed) {
        // The exact server count can arrive before the HTTP response is lost.
        await testApp.store.dispatch('application/forceUpdate', {
          application: agent,
          data: { pending_count: 2 },
        })
      }
      decision.resolve(504, { error: 'ERROR_UNKNOWN' })
      await flushPromises()

      expect(pendingCount()).toBe(committed ? 2 : 3)
      const countReads = testApp.mock.history.get.filter(
        ({ url }) => url === '/applications/10/'
      )
      expect(countReads).toHaveLength(1)
      expect(countReads[0].headers['X-Baserow-Realtime-Recovery']).toBe('true')
      expect(messageReads()).toHaveLength(2)
      expect(messageReads().at(-1).headers['X-Baserow-Realtime-Recovery']).toBe(
        'true'
      )
      expect(decisions(wrapper)).toEqual(committed ? ['agent.approved'] : [])
    }
  )

  test('keeps the last count if an uncertain decision cannot refresh the application', async () => {
    testApp.dontFailOnErrorResponses()
    mockApprovals(testApp, chat.uuid, [504, { error: 'ERROR_UNKNOWN' }])
    mockAgent(testApp, [503, { error: 'ERROR_UNKNOWN' }])
    const wrapper = await openWaitingReply([approval(1)])
    await testApp.store.dispatch('application/forceUpdate', {
      application: agent,
      data: { pending_count: 2 },
    })

    await headerButtons(wrapper)[1].trigger('click')
    await flushPromises()

    expect(agent.pending_count).toBe(2)
    expect(headerButtons(wrapper)[1].element.disabled).toBe(false)
    expect(
      testApp.mock.history.get.filter(({ url }) => url === '/applications/10/')
    ).toHaveLength(1)
  })

  test('a failed always-allow response reconciles configuration as well as approvals', async () => {
    testApp.dontFailOnErrorResponses()
    mockApprovals(testApp, chat.uuid, [504, { error: 'ERROR_UNKNOWN' }])
    const wrapper = await openWaitingReply(
      [approval(1)],
      page([prompt, reply('completed', [approval(1, 'approved')])])
    )
    const reads = configurationReads()
    await alwaysAllow(wrapper).trigger('click')
    await flushPromises()

    expect(configurationReads()).toBe(reads + 1)
    const refresh = testApp.mock.history.get
      .filter(({ url }) => url === '/agent/10/configuration/')
      .at(-1)
    expect(refresh.headers['X-Baserow-Realtime-Recovery']).toBe('true')
    expect(decisions(wrapper)).toEqual(['agent.approved'])
    expect(waitingDot(wrapper)).toBe(false)
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
    mockConversations(testApp, conversationsPage([chat]))
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
