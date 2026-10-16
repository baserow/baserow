import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import {
  acceptConversation,
  agentData,
  completeConfiguration,
  composer,
  composerExists,
  conversation,
  conversationTitles,
  createAgentPage,
  debounce,
  deferredReply,
  destroyAgentPage,
  editInstructions,
  incompleteConfiguration,
  instructions,
  message,
  messages,
  mockAvailability,
  mockConfiguration,
  mockConversations,
  mockMessages,
  mockReadiness,
  mockSaves,
  mockSendMessage,
  mockStartConversation,
  openSection,
  page,
  refreshAvailabilityTwice,
  selectConversation,
  selected,
  send,
  sendMessage,
  sentBodies,
  useFakeTimers,
  warning,
  withoutSettings,
  workspace,
} from './helpers'

describe('Agent conversations', () => {
  let testApp, agent, allowed, mount

  beforeEach(async () => {
    ;({ testApp, agent, allowed, mount } = await createAgentPage())
  })

  afterEach(() => destroyAgentPage(testApp))

  const twoConversations = () =>
    mockConversations(
      testApp,
      page([
        conversation('thread-a', 'Thread A'),
        conversation('thread-b', 'Thread B'),
      ])
    )

  test('sends the first message only after configuration is confirmed ready', async () => {
    const configuration = deferredReply()
    const readiness = deferredReply()
    mockConfiguration(testApp, configuration.reply)
    mockReadiness(testApp, readiness.reply)
    const wrapper = await mount()
    expect(composerExists(wrapper)).toBe(false)
    readiness.resolve(200, { state: 'ready' })
    configuration.resolve(200, completeConfiguration())
    await flushPromises()

    const content = '  First message\nsecond line  '
    await sendMessage(wrapper, content)
    await flushPromises()

    expect(sentBodies(testApp)[0].content).toBe(content)
    expect(
      wrapper.get('.agent-chat__message-content').element.textContent
    ).toBe(content)
    expect(composer(wrapper).element.value).toBe('')
    expect(selected(wrapper).text()).toContain('First message')
    expect(testApp.store.getters['application/get'](10)).not.toHaveProperty(
      'instructions'
    )
  })

  test('retries a failed first message with the same content and IDs', async () => {
    testApp.dontFailOnErrorResponses()
    mockStartConversation(testApp, [500, {}], acceptConversation)
    const wrapper = await mount()
    await sendMessage(wrapper, 'Keep this draft')

    expect(composer(wrapper).element.value).toBe('Keep this draft')
    expect(composer(wrapper).element.disabled).toBe(true)
    expect(send(wrapper).attributes('aria-label')).toBe('action.retry')
    await send(wrapper).trigger('click')
    await flushPromises()
    await flushPromises()

    const [failed, retried] = sentBodies(testApp)
    expect(retried).toEqual(failed)
    expect(messages(wrapper)).toEqual(['Keep this draft'])
    expect(composer(wrapper).element.disabled).toBe(false)
  })

  test('keeps the composer in place but disabled while settings save', async () => {
    useFakeTimers()
    const patch = deferredReply()
    mockSaves(testApp, patch.reply)
    const wrapper = await mount()
    const composerElement = wrapper.get('.agent-chat__composer').element
    await openSection(wrapper, 'agent.instructions')

    await instructions(wrapper).setValue('Updated instructions')
    expect(composer(wrapper).element.disabled).toBe(true)
    await debounce()
    expect(composer(wrapper).element.disabled).toBe(true)
    patch.resolve(
      200,
      completeConfiguration({ instructions: 'Updated instructions' })
    )
    await flushPromises()

    expect(wrapper.get('.agent-chat__composer').element).toBe(composerElement)
    expect(composer(wrapper).element.disabled).toBe(false)
  })

  test('lets an Editor send without ever loading the settings', async () => {
    allowed.value = withoutSettings
    const wrapper = await mount()

    await sendMessage(wrapper, 'Editor message')

    expect(messages(wrapper)).toEqual(['Editor message'])
    expect(
      testApp.mock.history.get.some(({ url }) => url.includes('configuration'))
    ).toBe(false)
  })

  test('shows a Viewer their history without a composer', async () => {
    allowed.value = (operation) =>
      withoutSettings(operation) && !operation.includes('create')
    mockConversations(testApp, page([conversation('thread-a', 'Thread A')]))
    mockMessages(testApp, 'thread-a', page([message('a1', 'Earlier')]))
    const wrapper = await mount()

    await selectConversation(wrapper, 'Thread A')

    expect(messages(wrapper)).toEqual(['Earlier'])
    expect(composerExists(wrapper)).toBe(false)
    expect(wrapper.find('.agent-conversations__footer').exists()).toBe(false)
    expect(warning(wrapper).exists()).toBe(false)
  })

  test.each([true, false])(
    'blocks writing until the newest availability refresh, older resolved first=%s',
    async (olderFirst) => {
      testApp.dontFailOnErrorResponses()
      const wrapper = await mount()
      await composer(wrapper).setValue('Keep my unsent message')
      const older = deferredReply()
      const newer = deferredReply()
      mockAvailability(testApp, older.reply, newer.reply)
      await refreshAvailabilityTwice(testApp, agent)

      const [first, second] = olderFirst ? [older, newer] : [newer, older]
      first.resolve(first === older ? 500 : 200, [workspace])
      await flushPromises()
      expect(composer(wrapper).element.disabled).toBe(olderFirst)
      second.resolve(second === older ? 500 : 200, [workspace])
      await flushPromises()

      expect(composer(wrapper).element.disabled).toBe(false)
      expect(composer(wrapper).element.value).toBe('Keep my unsent message')
    }
  )

  test('keeps history and the hidden draft until incomplete settings are repaired', async () => {
    mockConversations(testApp, page([conversation('thread-a', 'Thread A')]))
    mockMessages(testApp, 'thread-a', page([message('a1', 'Earlier')]))
    mockSaves(
      testApp,
      incompleteConfiguration('instructions'),
      completeConfiguration()
    )
    const wrapper = await mount()
    await selectConversation(wrapper, 'Thread A')
    await composer(wrapper).setValue('Keep my unsent message')
    await openSection(wrapper, 'agent.instructions')

    await editInstructions(wrapper, '')
    expect(composerExists(wrapper)).toBe(false)
    expect(messages(wrapper)).toEqual(['Earlier'])
    await editInstructions(wrapper, 'Be helpful.')

    expect(composer(wrapper).element.value).toBe('Keep my unsent message')
    expect(composer(wrapper).element.disabled).toBe(false)
  })

  test('lets a member continue a conversation without permission to start one', async () => {
    allowed.value = (operation) =>
      operation !== 'agent_application.create_conversation'
    mockConversations(testApp, page([conversation('thread-a', 'Thread A')]))
    mockMessages(testApp, 'thread-a', page([message('a1', 'Earlier')]))
    const wrapper = await mount()
    expect(composerExists(wrapper)).toBe(false)

    await selectConversation(wrapper, 'Thread A')

    expect(composer(wrapper).element.disabled).toBe(false)
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
    mockMessages(testApp, 'thread-a', page([message('a1', 'Existing A')]))
    mockMessages(testApp, 'thread-b', page([message('b1', 'Existing B')]))
    const write = deferredReply()
    mockSendMessage(testApp, 'thread-a', write.reply)
    const wrapper = await mount()
    await selectConversation(wrapper, 'Thread A')
    await sendMessage(wrapper, 'New A')
    await selectConversation(wrapper, 'Thread B')
    await composer(wrapper).setValue('Draft B')

    write.resolve(200, {
      conversation: conversation('thread-a', 'Thread A'),
      message: message(sentBodies(testApp)[0].uuid, 'New A'),
    })
    await flushPromises()
    expect(messages(wrapper)).toEqual(['Existing B'])
    await selectConversation(wrapper, 'Thread A')
    expect(messages(wrapper)).toEqual(['Existing A', 'New A'])
    expect(composer(wrapper).element.value).toBe('')
    await selectConversation(wrapper, 'Thread B')

    expect(composer(wrapper).element.value).toBe('Draft B')
  })

  test('pages conversations without duplicates and older messages with retry', async () => {
    testApp.dontFailOnErrorResponses()
    mockConversations(
      testApp,
      page([conversation('thread-a', 'Thread A')], 'next'),
      page([
        conversation('thread-a', 'Thread A'),
        conversation('thread-b', 'Thread B'),
      ])
    )
    mockMessages(
      testApp,
      'thread-a',
      page([message('a2', 'Newer A')], 'next'),
      [500, {}],
      page([message('a1', 'Older A')])
    )
    const wrapper = await mount()
    await wrapper.get('.agent-conversations__more').trigger('click')
    await flushPromises()
    expect(conversationTitles(wrapper)).toEqual(['Thread A', 'Thread B'])
    await selectConversation(wrapper, 'Thread A')

    await wrapper.get('.agent-chat__older').trigger('click')
    await flushPromises()
    expect(messages(wrapper)).toEqual(['Newer A'])
    expect(wrapper.text()).toContain('agent.messagesLoadError')
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
        'thread-a',
        page([message('a2', 'Newer A')], 'next'),
        older.reply
      )
      mockMessages(testApp, 'thread-b', page([message('b1', 'Current B')]))
      const wrapper = await mount()
      await selectConversation(wrapper, 'Thread A')
      const history = wrapper.get('.agent-chat__history').element
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
        await selectConversation(wrapper, 'Thread B')
        history.scrollTop = 200
      }
      if (selection === 'back') {
        scrollHeight = 1000
        await selectConversation(wrapper, 'Thread A')
        history.scrollTop = 300
      }

      scrollHeight = selection === 'other' ? 600 : 1500
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
        url.includes('conversations')
          ? page([])
          : completeConfiguration({ name: 'Next agent' }),
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
    mockConversations(testApp, list.reply)
    const wrapper = await mount()
    await sendMessage(wrapper, 'Sent during load')

    list.resolve(200, page([conversation('older-thread', 'Existing')]))
    await flushPromises()

    expect(conversationTitles(wrapper)).toEqual([
      'Existing',
      'Sent during load',
    ])
    expect(selected(wrapper).text()).toContain('Sent during load')
    expect(messages(wrapper)).toEqual(['Sent during load'])
  })

  test('moves a conversation to the top after sending in it', async () => {
    const old = conversation('thread-a', 'Thread A', '2026-10-12T10:00:00Z')
    mockConversations(
      testApp,
      page([conversation('thread-b', 'Thread B', '2026-10-13T10:00:00Z'), old])
    )
    mockMessages(testApp, 'thread-a', page([]))
    mockSendMessage(testApp, 'thread-a', ({ data }) => [
      200,
      {
        conversation: { ...old, updated_on: '2026-10-14T10:00:00Z' },
        message: message(JSON.parse(data).uuid, JSON.parse(data).content),
      },
    ])
    const wrapper = await mount()
    await selectConversation(wrapper, 'Thread A')

    await sendMessage(wrapper, 'Update older conversation')

    expect(conversationTitles(wrapper)).toEqual(['Thread A', 'Thread B'])
  })
})
