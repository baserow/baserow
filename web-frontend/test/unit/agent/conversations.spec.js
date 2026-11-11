import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import {
  filterConversations,
  acceptConversation,
  chooseFromMenu,
  agentData,
  completeConfiguration,
  composer,
  composerExists,
  conversation,
  conversationTitles,
  createAgentPage,
  deferredReply,
  destroyAgentPage,
  editInstructions,
  incompleteConfiguration,
  message,
  messages,
  mockAvailability,
  mockConfiguration,
  mockConversations,
  mockMessages,
  mockSaves,
  mockSendMessage,
  mockStartConversation,
  openSection,
  page,
  selectConversation,
  selected,
  send,
  sendMessage,
  sentBodies,
  unavailableModel,
  useFakeTimers,
  warning,
  withoutConfiguration,
  workspace,
  conversationsPage,
} from './helpers'

describe('Agent conversations', () => {
  let testApp, allowed, mount

  beforeEach(async () => {
    ;({ testApp, allowed, mount } = await createAgentPage())
  })

  afterEach(() => destroyAgentPage(testApp))

  const twoConversations = () =>
    mockConversations(
      testApp,
      conversationsPage([
        conversation('conversation-a', 'Conversation A'),
        conversation('conversation-b', 'Conversation B'),
      ])
    )

  test.each([
    ['configuration', mockConfiguration, completeConfiguration()],
    ['models', mockAvailability, [workspace]],
  ])(
    'keeps sending blocked until the %s load answers',
    async (_, mockLoad, data) => {
      const load = deferredReply()
      mockLoad(testApp, load.reply)
      const wrapper = await mount()
      await composer(wrapper).setValue('Hello')
      expect(send(wrapper).element.disabled).toBe(true)

      load.resolve(200, data)
      await flushPromises()

      expect(send(wrapper).element.disabled).toBe(false)
    }
  )

  test('sends the first message as typed and lists its conversation', async () => {
    const wrapper = await mount()
    const content = '  First message\nsecond line  '

    await sendMessage(wrapper, content)

    expect(sentBodies(testApp)[0].content).toBe(content)
    expect(wrapper.get('.chat-message__bubble').element.textContent).toBe(
      content
    )
    expect(composer(wrapper).element.value).toBe('')
    expect(selected(wrapper).text()).toContain('First message')
  })

  test('focuses the composer when a new conversation starts', async () => {
    const wrapper = await mount()

    await wrapper.get('.agent-conversations__footer .button').trigger('click')
    await flushPromises()

    expect(document.activeElement).toBe(composer(wrapper).element)
  })

  test('keeps the Recent section and focused composer when typing the first draft', async () => {
    const wrapper = await mount()
    const input = composer(wrapper)
    input.element.focus()
    const header = wrapper.get('.agent-conversations__header')

    await input.setValue('Unfinished first conversation')

    expect(wrapper.get('.agent-conversations__header').element).toBe(
      header.element
    )
    expect(composer(wrapper).element).toBe(input.element)
    expect(document.activeElement).toBe(input.element)
    expect(input.element.value).toBe('Unfinished first conversation')
    expect(wrapper.get('.agent-conversations__draft').exists()).toBe(true)
  })

  test('keeps focus in the composer after clicking Send', async () => {
    const wrapper = await mount()
    await composer(wrapper).setValue('Hello')
    send(wrapper).element.focus()
    send(wrapper).element.click()
    await flushPromises()

    expect(document.activeElement).toBe(composer(wrapper).element)
    expect(composer(wrapper).element.value).toBe('')
  })

  test('sends on Enter but not on Shift+Enter or while composing', async () => {
    const wrapper = await mount()
    await composer(wrapper).setValue('Hello')
    for (const options of [
      { shiftKey: true },
      { isComposing: true },
      { keyCode: 229 },
    ]) {
      await composer(wrapper).trigger('keydown', { key: 'Enter', ...options })
    }
    await flushPromises()
    expect(sentBodies(testApp)).toEqual([])

    await composer(wrapper).trigger('keydown', { key: 'Enter' })
    await flushPromises()

    expect(sentBodies(testApp).map(({ content }) => content)).toEqual(['Hello'])
  })

  test('keeps the unsent draft when the session token is refreshed', async () => {
    const user = { id: 1, username: 'member@example.com' }
    testApp.authenticate(user)
    const wrapper = await mount()
    await composer(wrapper).setValue('Unsent draft')

    testApp.authenticate({ ...user })
    await flushPromises()

    expect(composer(wrapper).element.value).toBe('Unsent draft')
  })

  test.each([
    ['ERROR_REQUEST_BODY_VALIDATION', 400, 'agent.messageSaveError'],
    ['ERROR_AGENT_BUSY', 429, 'agent.agentsBusy'],
  ])(
    'lets a message rejected with %s be edited and sent with new IDs',
    async (error, status, alert) => {
      testApp.dontFailOnErrorResponses()
      mockStartConversation(testApp, [status, { error }], acceptConversation)
      const wrapper = await mount()
      await sendMessage(wrapper, 'Rejected')

      expect(wrapper.get('#agent-chat-send-error').text()).toBe(alert)
      expect(composer(wrapper).element.readOnly).toBe(false)
      await composer(wrapper).setValue('Accepted')
      await send(wrapper).trigger('click')
      await flushPromises()

      const [rejected, accepted] = sentBodies(testApp)
      expect(accepted.content).toBe('Accepted')
      expect(accepted.message_uuid).not.toBe(rejected.message_uuid)
    }
  )

  test('retries a failed first message with the same content and IDs', async () => {
    testApp.dontFailOnErrorResponses()
    mockStartConversation(testApp, [500, {}], acceptConversation)
    const wrapper = await mount()
    useFakeTimers()
    await sendMessage(wrapper, 'Keep this draft')

    const notice = wrapper.get('.chat-composer__activity[role="alert"]')
    expect(notice.text()).toBe('agent.messageSaveError')
    expect(notice.classes()).toContain('chat-composer__activity--error')
    expect(composer(wrapper).attributes('aria-describedby')).toBe(
      notice.attributes('id')
    )
    await vi.advanceTimersByTimeAsync(9999)
    expect(wrapper.find('#agent-chat-send-error').exists()).toBe(true)
    await vi.advanceTimersByTimeAsync(1)
    expect(wrapper.find('#agent-chat-send-error').exists()).toBe(false)
    expect(composer(wrapper).attributes('aria-describedby')).toBeUndefined()
    expect(composer(wrapper).element.value).toBe('Keep this draft')
    expect(composer(wrapper).element.readOnly).toBe(true)
    expect(send(wrapper).attributes('aria-label')).toBe('action.retry')
    await send(wrapper).trigger('click')
    await flushPromises()

    const [failed, retried] = sentBodies(testApp)
    expect(retried).toEqual(failed)
    expect(messages(wrapper)).toEqual(['Keep this draft'])
    expect(composer(wrapper).element.readOnly).toBe(false)
  })

  test('shows a new notice for the same error when a safe retry fails again', async () => {
    testApp.dontFailOnErrorResponses()
    const retry = deferredReply()
    mockStartConversation(testApp, [500, {}], retry.reply, acceptConversation)
    const wrapper = await mount()
    useFakeTimers()
    await sendMessage(wrapper, 'Keep retrying safely')
    await vi.advanceTimersByTimeAsync(9000)

    await send(wrapper).trigger('click')
    await flushPromises()
    expect(wrapper.find('#agent-chat-send-error').exists()).toBe(false)
    await vi.advanceTimersByTimeAsync(1000)
    retry.resolve(500, {})
    await flushPromises()

    expect(wrapper.get('#agent-chat-send-error').text()).toBe(
      'agent.messageSaveError'
    )
    await vi.advanceTimersByTimeAsync(9999)
    expect(wrapper.find('#agent-chat-send-error').exists()).toBe(true)
    await vi.advanceTimersByTimeAsync(1)
    expect(wrapper.find('#agent-chat-send-error').exists()).toBe(false)
    await send(wrapper).trigger('click')
    await flushPromises()

    const [first, second, third] = sentBodies(testApp)
    expect(second).toEqual(first)
    expect(third).toEqual(first)
    expect(messages(wrapper)).toEqual(['Keep retrying safely'])
  })

  test('keeps each notice expiry when switching conversations', async () => {
    testApp.dontFailOnErrorResponses()
    twoConversations()
    for (const uuid of ['conversation-a', 'conversation-b']) {
      mockMessages(testApp, uuid, page([]))
      mockSendMessage(testApp, uuid, [500, {}])
    }
    const wrapper = await mount()
    useFakeTimers()
    await selectConversation(wrapper, 'Conversation A')
    await sendMessage(wrapper, 'Draft A')
    await vi.advanceTimersByTimeAsync(6000)
    await selectConversation(wrapper, 'Conversation B')
    await sendMessage(wrapper, 'Draft B')

    await vi.advanceTimersByTimeAsync(4000)
    expect(wrapper.get('#agent-chat-send-error').text()).toBe(
      'agent.messageSaveError'
    )
    await selectConversation(wrapper, 'Conversation A')
    expect(wrapper.find('#agent-chat-send-error').exists()).toBe(false)
    expect(composer(wrapper).element.value).toBe('Draft A')
    await selectConversation(wrapper, 'Conversation B')
    expect(wrapper.find('#agent-chat-send-error').exists()).toBe(true)
    await vi.advanceTimersByTimeAsync(6000)
    expect(wrapper.find('#agent-chat-send-error').exists()).toBe(false)
    expect(composer(wrapper).element.value).toBe('Draft B')
  })

  test('replaces the composer with the warning when a send finds the configuration invalid', async () => {
    testApp.dontFailOnErrorResponses()
    mockStartConversation(testApp, [400, { error: 'ERROR_AGENT_NOT_READY' }])
    mockConfiguration(
      testApp,
      completeConfiguration(),
      unavailableModel('model-one')
    )
    const wrapper = await mount()

    await sendMessage(wrapper, 'Hello')

    expect(composerExists(wrapper)).toBe(false)
    expect(warning(wrapper).text()).toContain('agent.modelUnavailable')
  })

  test('keeps the composer writable but blocks sending while the configuration saves', async () => {
    const patch = deferredReply()
    mockSaves(testApp, patch.reply)
    const wrapper = await mount()
    const composerElement = wrapper.get('.agent-chat__composer').element
    await openSection(wrapper, 'agent.instructions')
    await editInstructions(wrapper, 'Updated instructions')

    await composer(wrapper).setValue('Typed while saving')
    expect(send(wrapper).element.disabled).toBe(true)
    patch.resolve(
      200,
      completeConfiguration({ instructions: 'Updated instructions' })
    )
    await flushPromises()

    expect(wrapper.get('.agent-chat__composer').element).toBe(composerElement)
    expect(send(wrapper).element.disabled).toBe(false)
  })

  test('lets an Editor send without ever loading the configuration', async () => {
    allowed.value = withoutConfiguration
    const wrapper = await mount()

    await sendMessage(wrapper, 'Editor message')

    expect(messages(wrapper)).toEqual(['Editor message'])
    expect(
      testApp.mock.history.get.some(({ url }) => url.includes('configuration'))
    ).toBe(false)
  })

  test('shows a Viewer their history without a composer', async () => {
    allowed.value = (operation) =>
      withoutConfiguration(operation) && !operation.includes('create')
    mockConversations(
      testApp,
      conversationsPage([conversation('conversation-a', 'Conversation A')])
    )
    mockMessages(testApp, 'conversation-a', page([message('a1', 'Earlier')]))
    const wrapper = await mount()

    await selectConversation(wrapper, 'Conversation A')

    expect(messages(wrapper)).toEqual(['Earlier'])
    expect(composerExists(wrapper)).toBe(false)
    expect(wrapper.find('.agent-conversations__footer').exists()).toBe(false)
    expect(warning(wrapper).exists()).toBe(false)
  })

  test('keeps history and the hidden draft until an incomplete configuration is repaired', async () => {
    mockConversations(
      testApp,
      conversationsPage([conversation('conversation-a', 'Conversation A')])
    )
    mockMessages(testApp, 'conversation-a', page([message('a1', 'Earlier')]))
    mockSaves(
      testApp,
      incompleteConfiguration('instructions'),
      completeConfiguration()
    )
    const wrapper = await mount()
    await selectConversation(wrapper, 'Conversation A')
    await composer(wrapper).setValue('Keep my unsent message')
    await openSection(wrapper, 'agent.instructions')

    await editInstructions(wrapper, '')
    expect(composerExists(wrapper)).toBe(false)
    expect(messages(wrapper)).toEqual(['Earlier'])
    await editInstructions(wrapper, 'Be helpful.')

    expect(composer(wrapper).element.value).toBe('Keep my unsent message')
    expect(send(wrapper).element.disabled).toBe(false)
  })

  test('lets a member continue a conversation without permission to start one', async () => {
    allowed.value = (operation) =>
      operation !== 'agent_application.create_conversation'
    mockConversations(
      testApp,
      conversationsPage([conversation('conversation-a', 'Conversation A')])
    )
    mockMessages(testApp, 'conversation-a', page([message('a1', 'Earlier')]))
    const wrapper = await mount()
    expect(composerExists(wrapper)).toBe(false)

    await selectConversation(wrapper, 'Conversation A')

    expect(composerExists(wrapper)).toBe(true)
  })

  test('does not show a sent message after read access is revoked during the send', async () => {
    const write = deferredReply()
    mockStartConversation(testApp, write.reply)
    const wrapper = await mount()
    await sendMessage(wrapper, 'Private pending message')

    allowed.value = (operation) => !operation.includes('conversation')
    await flushPromises()
    write.resolve(...acceptConversation(testApp.mock.history.post[0]))
    await flushPromises()

    expect(wrapper.find('.agent-conversations').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('Private pending message')
  })

  test('keeps drafts per conversation and a late send in its own conversation', async () => {
    twoConversations()
    mockMessages(testApp, 'conversation-a', page([message('a1', 'Existing A')]))
    mockMessages(testApp, 'conversation-b', page([message('b1', 'Existing B')]))
    const write = deferredReply()
    mockSendMessage(testApp, 'conversation-a', write.reply)
    const wrapper = await mount()
    await selectConversation(wrapper, 'Conversation A')
    await sendMessage(wrapper, 'New A')
    await selectConversation(wrapper, 'Conversation B')
    await composer(wrapper).setValue('Draft B')

    write.resolve(200, {
      conversation: conversation('conversation-a', 'Conversation A'),
      message: message(sentBodies(testApp)[0].uuid, 'New A'),
    })
    await flushPromises()
    expect(messages(wrapper)).toEqual(['Existing B'])
    await selectConversation(wrapper, 'Conversation A')
    expect(messages(wrapper)).toEqual(['Existing A', 'New A'])
    expect(composer(wrapper).element.value).toBe('')
    await selectConversation(wrapper, 'Conversation B')

    expect(composer(wrapper).element.value).toBe('Draft B')
  })

  test('pages conversations without duplicates and messages with retry', async () => {
    testApp.dontFailOnErrorResponses()
    mockConversations(
      testApp,
      conversationsPage(
        [
          conversation('conversation-new', 'Newest', '2026-10-14T11:00:00Z'),
          conversation('conversation-a', 'Conversation A'),
        ],
        'next'
      ),
      conversationsPage([
        conversation('conversation-a', 'Conversation A'),
        conversation('conversation-b', 'Conversation B'),
      ])
    )
    mockMessages(
      testApp,
      'conversation-a',
      [500, {}],
      page([message('a2', 'Newer A')], 'next'),
      [500, {}],
      page([message('a1', 'Older A')])
    )
    const wrapper = await mount()
    await wrapper.get('.agent-conversations__content').trigger('scroll')
    await flushPromises()
    expect(conversationTitles(wrapper)).toEqual([
      'Newest',
      'Conversation A',
      'Conversation B',
    ])
    await selectConversation(wrapper, 'Conversation A')
    await composer(wrapper).setValue('Hello')
    expect(send(wrapper).element.disabled).toBe(true)
    await wrapper.get('.agent-chat__history .alert button').trigger('click')
    await flushPromises()

    await wrapper.get('.agent-chat__older').trigger('click')
    await flushPromises()
    expect(messages(wrapper)).toEqual(['Newer A'])
    expect(wrapper.text()).toContain('agent.messagesLoadError')
    expect(send(wrapper).element.disabled).toBe(false)
    await wrapper.get('.agent-chat__history .alert button').trigger('click')
    await flushPromises()

    expect(messages(wrapper)).toEqual(['Older A', 'Newer A'])
  })

  test.each(['same', 'other', 'back'])(
    'keeps the reading position when older messages load with selection=%s',
    async (selection) => {
      twoConversations()
      const older = deferredReply()
      mockMessages(
        testApp,
        'conversation-a',
        page([message('a2', 'Newer A')], 'next'),
        older.reply
      )
      mockMessages(
        testApp,
        'conversation-b',
        page([message('b1', 'Current B')])
      )
      const wrapper = await mount()
      await selectConversation(wrapper, 'Conversation A')
      const history = wrapper.get('.agent-chat__history').element
      const anchor = wrapper.get('.chat-message').element
      let anchorOffset = 0
      vi.spyOn(anchor, 'offsetTop', 'get').mockImplementation(
        () => anchorOffset
      )
      let scrollHeight = 1000
      let scrollTop = 400
      vi.spyOn(history, 'scrollHeight', 'get').mockImplementation(
        () => scrollHeight
      )
      vi.spyOn(history, 'scrollTop', 'get').mockImplementation(() => scrollTop)
      vi.spyOn(history, 'scrollTop', 'set').mockImplementation((value) => {
        scrollTop = value
      })
      await wrapper.get('.agent-chat__older').trigger('click')
      await flushPromises()
      if (selection !== 'same') {
        scrollHeight = 600
        await selectConversation(wrapper, 'Conversation B')
        history.scrollTop = 200
      }
      if (selection === 'back') {
        scrollHeight = 1000
        await selectConversation(wrapper, 'Conversation A')
        history.scrollTop = 300
      }

      scrollHeight = selection === 'other' ? 600 : 1500
      anchorOffset = 500
      older.resolve(200, page([message('a1', 'Older A')]))
      await flushPromises()

      expect(history.scrollTop).toBe(
        { same: 900, other: 200, back: 300 }[selection]
      )
      expect(messages(wrapper)).toEqual(
        selection === 'other' ? ['Current B'] : ['Older A', 'Newer A']
      )
    }
  )

  test('follows runs only in the selected saved conversation', async () => {
    const { id } = conversation('conversation-a', 'Conversation A')
    twoConversations()
    mockMessages(testApp, 'conversation-a', page([]))
    const subscriptions = () => testApp.store.state.chatRuns.subscriptions
    const wrapper = await mount()

    await selectConversation(wrapper, 'Conversation A')
    expect(subscriptions()).toEqual({ agent: id })
    await wrapper.get('.agent-conversations__footer .button').trigger('click')
    await flushPromises()
    expect(subscriptions()).toEqual({})
    await selectConversation(wrapper, 'Conversation A')
    wrapper.unmount()
    expect(subscriptions()).toEqual({})
  })

  test('ignores a send that finishes after switching to another Agent', async () => {
    const write = deferredReply()
    mockStartConversation(testApp, write.reply)
    const wrapper = await mount()
    await sendMessage(wrapper, 'Old Agent message')
    const next = await testApp.store.dispatch('application/forceCreate', {
      ...agentData,
      id: 20,
      name: 'Next agent',
    })
    testApp.mock
      .onGet(/\/agent\/20\//)
      .reply(({ url }) => [
        200,
        url.includes('conversations') ? page([]) : completeConfiguration(),
      ])

    await wrapper.setProps({ agent: next })
    await flushPromises()
    write.resolve(...acceptConversation(testApp.mock.history.post[0]))
    await flushPromises()

    expect(wrapper.text()).not.toContain('Old Agent message')
    expect(composer(wrapper).element.value).toBe('')
  })

  test('keeps a conversation sent while the list was still loading', async () => {
    const list = deferredReply()
    const existing = conversationsPage([
      conversation('older-conversation', 'Existing', '2026-10-13T10:00:00Z'),
    ])
    // The read started before the send, so it reads again.
    mockConversations(testApp, list.reply, existing)
    const wrapper = await mount()
    await sendMessage(wrapper, 'Sent during load')

    list.resolve(200, existing)
    await flushPromises()

    expect(conversationTitles(wrapper)).toEqual([
      'Sent during load',
      'Existing',
    ])
    expect(selected(wrapper).text()).toContain('Sent during load')
    expect(messages(wrapper)).toEqual(['Sent during load'])
  })

  test('moves a conversation to the top after sending in it', async () => {
    const old = conversation(
      'conversation-a',
      'Conversation A',
      '2026-10-12T10:00:00Z'
    )
    mockConversations(
      testApp,
      conversationsPage([
        conversation(
          'conversation-b',
          'Conversation B',
          '2026-10-13T10:00:00Z'
        ),
        old,
      ])
    )
    mockMessages(testApp, 'conversation-a', page([]))
    mockSendMessage(testApp, 'conversation-a', ({ data }) => [
      200,
      {
        conversation: { ...old, updated_on: '2026-10-14T10:00:00Z' },
        message: message(JSON.parse(data).uuid, JSON.parse(data).content),
      },
    ])
    const wrapper = await mount()
    await selectConversation(wrapper, 'Conversation A')

    await sendMessage(wrapper, 'Update older conversation')

    expect(conversationTitles(wrapper)).toEqual([
      'Conversation A',
      'Conversation B',
    ])
  })

  test('renames inline, then deletes and offers a restore, selecting the next one', async () => {
    const renamed = conversation('conversation-a', 'Renamed')
    twoConversations()
    mockMessages(testApp, 'conversation-a', page([]))
    mockMessages(testApp, 'conversation-b', page([]))
    testApp.mock
      .onPatch('/agent/10/conversations/conversation-a/')
      .reply(200, renamed)
    testApp.mock.onDelete('/agent/10/conversations/conversation-a/').reply(204)
    const wrapper = await mount()
    await selectConversation(wrapper, 'Conversation A')

    await chooseFromMenu(wrapper, 'Conversation A', 'action.rename')
    const input = wrapper.get('.agent-conversations__rename')
    expect(document.activeElement).toBe(input.element)
    await input.setValue('  Renamed ')
    await input.trigger('keydown', { key: 'Enter' })
    await flushPromises()

    expect(JSON.parse(testApp.mock.history.patch.at(-1).data)).toEqual({
      title: 'Renamed',
    })
    expect(conversationTitles(wrapper)).toEqual(['Renamed', 'Conversation B'])

    await chooseFromMenu(wrapper, 'Renamed', 'action.delete')

    expect(conversationTitles(wrapper)).toEqual(['Conversation B'])
    expect(selected(wrapper).text()).toContain('Conversation B')
    expect(testApp.store.state.toast.items).toContainEqual(
      expect.objectContaining({
        type: 'restore',
        data: {
          trash_item_type: 'agent_conversation',
          trash_item_id: renamed.id,
        },
      })
    )
  })

  test('loads the conversations after the last one shown, also after a delete', async () => {
    mockConversations(
      testApp,
      conversationsPage(
        [
          conversation('conversation-a', 'Conversation A'),
          conversation('conversation-b', 'Conversation B'),
        ],
        'after-b'
      ),
      conversationsPage([conversation('conversation-c', 'Conversation C')])
    )
    testApp.mock.onDelete('/agent/10/conversations/conversation-a/').reply(204)
    const wrapper = await mount()

    await chooseFromMenu(wrapper, 'Conversation A', 'action.delete')
    await wrapper.get('.agent-conversations__content').trigger('scroll')
    await flushPromises()

    expect(conversationTitles(wrapper)).toEqual([
      'Conversation B',
      'Conversation C',
    ])
    expect(
      testApp.mock.history.get
        .filter(({ url }) => url === '/agent/10/conversations/')
        .map(({ params }) => params.cursor)
    ).toEqual([null, 'after-b'])
    expect(wrapper.find('.infinite-scroll__loading-wrapper').isVisible()).toBe(
      false
    )
  })

  test('rolls a failed rename back and drops a conversation deleted elsewhere', async () => {
    twoConversations()
    testApp.mock
      .onPatch('/agent/10/conversations/conversation-a/')
      .replyOnce(500)
      .onPatch('/agent/10/conversations/conversation-a/')
      .replyOnce(404, { error: 'ERROR_AGENT_CONVERSATION_DOES_NOT_EXIST' })
    const wrapper = await mount()
    const rename = async (title) => {
      await chooseFromMenu(wrapper, 'Conversation A', 'action.rename')
      const input = wrapper.get('.agent-conversations__rename')
      await input.setValue(title)
      await input.trigger('keydown', { key: 'Enter' })
      await flushPromises()
    }

    await rename('Fails')
    expect(conversationTitles(wrapper)).toEqual([
      'Conversation A',
      'Conversation B',
    ])

    await rename('Gone')
    expect(conversationTitles(wrapper)).toEqual(['Conversation B'])
  })

  test('filters on the server, keeps the open draft, and ignores an older page', async () => {
    const a = conversation('a', 'A')
    const b = { ...conversation('b', 'B'), pinned: true }
    const waiting = {
      ...conversation('waiting', 'Waiting'),
      pending_approval_count: 1,
    }
    const stale = deferredReply()
    mockConversations(
      testApp,
      conversationsPage([a], 'older'),
      stale.reply,
      conversationsPage([waiting]),
      conversationsPage([b])
    )
    mockMessages(testApp, a.uuid, page([message('m', 'Hello')]))
    const wrapper = await mount()
    await selectConversation(wrapper, 'A')
    await composer(wrapper).setValue('Unsent text')
    await wrapper.get('.agent-conversations__content').trigger('scroll')
    await filterConversations(wrapper, 'agent.waitingForApprovalFilter')
    expect(conversationTitles(wrapper)).toEqual([
      'Waitingagent.waitingForApproval',
    ])
    expect(composer(wrapper).element.value).toBe('Unsent text')
    expect(messages(wrapper)).toEqual(['Hello'])
    stale.resolve(
      200,
      conversationsPage([conversation('old', 'Old')], 'stale-cursor')
    )
    await flushPromises()
    expect(conversationTitles(wrapper)).toEqual([
      'Waitingagent.waitingForApproval',
    ])
    await filterConversations(wrapper, 'agent.pinned')
    expect(conversationTitles(wrapper)).toEqual(['B'])
    const reads = testApp.mock.history.get.filter(({ url }) =>
      url.endsWith('/conversations/')
    )
    expect(reads.at(-2).params).toEqual({
      cursor: null,
      limit: 20,
      has_pending_approvals: true,
    })
    expect(reads.at(-1).params).toEqual({
      cursor: null,
      limit: 20,
      pinned: true,
    })
  })

  test('pins through PATCH, restores a failed unpin, and preserves the open conversation', async () => {
    const a = conversation('a', 'A')
    const b = conversation('b', 'B')
    mockConversations(testApp, conversationsPage([a, b]))
    mockMessages(testApp, b.uuid, page([message('m', 'Hello')]))
    testApp.dontFailOnErrorResponses()
    testApp.mock
      .onPatch('/agent/10/conversations/b/')
      .replyOnce(200, { ...b, pinned: true })
      .onPatch('/agent/10/conversations/b/')
      .replyOnce(500)
    const wrapper = await mount()
    await selectConversation(wrapper, 'B')
    await composer(wrapper).setValue('Draft')
    await chooseFromMenu(wrapper, 'B', 'agent.pin')
    expect(conversationTitles(wrapper)).toEqual(['B', 'A'])
    expect(JSON.parse(testApp.mock.history.patch[0].data)).toEqual({
      pinned: true,
    })
    expect(wrapper.get('.agent-conversations__header').text()).toBe(
      'agent.pinned'
    )
    await chooseFromMenu(wrapper, 'B', 'agent.unpin')
    expect(conversationTitles(wrapper)).toEqual(['B', 'A'])
    expect(composer(wrapper).element.value).toBe('Draft')
    expect(selected(wrapper).text()).toBe('B')
  })
})
