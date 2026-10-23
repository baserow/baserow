import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { registerRealtimeEvents } from '@baserow/modules/agent/realtime'
import {
  agentData,
  composer,
  conversation,
  conversationTitles,
  createAgentPage,
  deferredReply,
  destroyAgentPage,
  message,
  messages,
  mockConversations,
  mockMessages,
  mockSendMessage,
  page,
  selectConversation,
  selected,
  send,
  sendMessage,
} from './helpers'

const storedMessage = (id, content) => ({
  ...message(`message-${id}`, content),
  id,
})
const first = conversation('conversation-a', 'Conversation A')
const second = conversation('conversation-b', 'Conversation B')

describe('Agent conversation realtime updates', () => {
  let testApp, agent, allowed, mount, receive

  beforeEach(async () => {
    ;({ testApp, agent, allowed, mount } = await createAgentPage())
    registerRealtimeEvents({
      registerEvent: (type, handler) => {
        if (type === 'agent_conversation_updated') receive = handler
      },
    })
  })

  afterEach(() => destroyAgentPage(testApp))

  const update = async (uuid, agentId = agentData.id) => {
    receive(
      { store: testApp.store },
      { agent_id: agentId, conversation_uuid: uuid }
    )
    await flushPromises()
  }

  test('keeps selected older conversations, history, drafts and focus during a remote refresh', async () => {
    mockConversations(testApp, page([first], 'next'), page([second]))
    mockMessages(
      testApp,
      second.uuid,
      page([storedMessage(2, 'Recent')], 'next'),
      page([storedMessage(1, 'Older')])
    )
    const wrapper = await mount()
    await wrapper.get('.agent-conversations__more').trigger('click')
    await flushPromises()
    await selectConversation(wrapper, second.title)
    await wrapper.get('.agent-chat__older').trigger('click')
    await flushPromises()
    await composer(wrapper).setValue('Unfinished draft')
    const textarea = composer(wrapper).element
    textarea.focus()
    mockConversations(
      testApp,
      page(
        [
          conversation(
            'conversation-c',
            'New remote conversation',
            '2026-10-22T10:00:00Z'
          ),
        ],
        'next'
      )
    )
    mockMessages(
      testApp,
      second.uuid,
      page([storedMessage(3, 'Remote message')], 'next'),
      page([storedMessage(2, 'Recent')], 'next')
    )

    await update(second.uuid)

    expect(conversationTitles(wrapper)).toContain('New remote conversation')
    expect(selected(wrapper).text()).toContain(second.title)
    expect(messages(wrapper)).toEqual(['Older', 'Recent', 'Remote message'])
    expect(composer(wrapper).element).toBe(textarea)
    expect(document.activeElement).toBe(textarea)
    expect(textarea.value).toBe('Unfinished draft')
    expect(agent).not.toHaveProperty('messages')
    expect(agent._.realtimeVersion).toBe(0)
  })

  test('keeps a send accepted after a background read started in API order', async () => {
    mockConversations(testApp, page([first]))
    mockMessages(testApp, first.uuid, page([storedMessage(1, 'Earlier')]))
    const wrapper = await mount()
    await selectConversation(wrapper, first.title)
    const refresh = deferredReply()
    mockMessages(testApp, first.uuid, refresh.reply)
    await update(first.uuid)
    mockSendMessage(testApp, first.uuid, ({ data }) => [
      200,
      {
        conversation: first,
        message: {
          ...storedMessage(3, 'My accepted message'),
          uuid: JSON.parse(data).uuid,
        },
      },
    ])
    await sendMessage(wrapper, 'My accepted message')

    refresh.resolve(
      200,
      page([storedMessage(1, 'Earlier'), storedMessage(2, 'Remote message')])
    )
    await flushPromises()

    expect(messages(wrapper)).toEqual([
      'Earlier',
      'Remote message',
      'My accepted message',
    ])
    expect(composer(wrapper).element.value).toBe('')
  })

  test('refreshes an event received during the first history load without replacing the draft', async () => {
    mockConversations(testApp, page([first]))
    const initial = deferredReply()
    mockMessages(
      testApp,
      first.uuid,
      initial.reply,
      page([storedMessage(1, 'Earlier'), storedMessage(2, 'Remote message')])
    )
    const wrapper = await mount()
    await selectConversation(wrapper, first.title)
    expect(wrapper.get('.agent-chat__loading').attributes('aria-label')).toBe(
      'agent.loadingMessages'
    )
    expect(
      wrapper.findAll('.agent-chat__loading .skeleton-block')
    ).toHaveLength(3)
    await composer(wrapper).setValue('Writing during load')
    const textarea = composer(wrapper).element
    textarea.focus()

    await update(first.uuid)
    initial.resolve(200, page([storedMessage(1, 'Earlier')]))
    await flushPromises()

    expect(messages(wrapper)).toEqual(['Earlier', 'Remote message'])
    expect(composer(wrapper).element).toBe(textarea)
    expect(textarea.value).toBe('Writing during load')
    expect(document.activeElement).toBe(textarea)
  })

  test('queues a remote update during a send and refreshes without duplicating the accepted message', async () => {
    mockConversations(testApp, page([first]))
    mockMessages(testApp, first.uuid, page([storedMessage(1, 'Earlier')]))
    const write = deferredReply()
    mockSendMessage(testApp, first.uuid, write.reply)
    const wrapper = await mount()
    await selectConversation(wrapper, first.title)
    await sendMessage(wrapper, 'My message')
    mockMessages(
      testApp,
      first.uuid,
      page([
        storedMessage(1, 'Earlier'),
        storedMessage(2, 'Remote message'),
        storedMessage(3, 'My message'),
      ])
    )
    const reads = testApp.mock.history.get.filter(({ url }) =>
      url.includes('/messages/')
    ).length

    await update(first.uuid)

    expect(
      testApp.mock.history.get.filter(({ url }) => url.includes('/messages/'))
    ).toHaveLength(reads)
    const sent = JSON.parse(testApp.mock.history.post.at(-1).data)
    const accepted = { ...storedMessage(3, 'My message'), uuid: sent.uuid }
    mockMessages(
      testApp,
      first.uuid,
      page([
        storedMessage(1, 'Earlier'),
        storedMessage(2, 'Remote message'),
        accepted,
      ])
    )
    write.resolve(200, { conversation: first, message: accepted })
    await flushPromises()

    expect(messages(wrapper)).toEqual([
      'Earlier',
      'Remote message',
      'My message',
    ])
    expect(composer(wrapper).element.value).toBe('')
  })

  test('keeps the focused draft after a failed background history refresh and retries the newest page', async () => {
    testApp.dontFailOnErrorResponses()
    mockConversations(testApp, page([first]))
    mockMessages(
      testApp,
      first.uuid,
      page([storedMessage(1, 'Earlier')], 'next')
    )
    const wrapper = await mount()
    await selectConversation(wrapper, first.title)
    await composer(wrapper).setValue('Keep typing')
    const textarea = composer(wrapper).element
    textarea.focus()
    const container = wrapper.get('.agent-chat__history').element
    let scrollTop = 150
    let scrollHeight = 1000
    vi.spyOn(container, 'scrollHeight', 'get').mockImplementation(
      () => scrollHeight
    )
    vi.spyOn(container, 'clientHeight', 'get').mockReturnValue(300)
    vi.spyOn(container, 'scrollTop', 'get').mockImplementation(() => scrollTop)
    vi.spyOn(container, 'scrollTop', 'set').mockImplementation((value) => {
      scrollTop = value
    })
    mockMessages(
      testApp,
      first.uuid,
      [500, {}],
      page([storedMessage(1, 'Earlier'), storedMessage(2, 'Remote message')])
    )

    await update(first.uuid)

    expect(messages(wrapper)).toEqual(['Earlier'])
    expect(composer(wrapper).element).toBe(textarea)
    expect(document.activeElement).toBe(textarea)
    expect(textarea.value).toBe('Keep typing')
    expect(send(wrapper).element.disabled).toBe(false)
    scrollHeight = 1200
    await wrapper.get('.agent-chat__history .alert button').trigger('click')
    await flushPromises()
    expect(messages(wrapper)).toEqual(['Earlier', 'Remote message'])
    expect(scrollTop).toBe(150)
    expect(testApp.mock.history.get.at(-1).params.page).toBe(1)
  })

  test('anchors older messages without including an appended remote message in the scroll adjustment', async () => {
    mockConversations(testApp, page([first]))
    const older = deferredReply()
    mockMessages(
      testApp,
      first.uuid,
      page([storedMessage(3, 'Recent')], 'next'),
      older.reply,
      () => {
        scrollHeight = 1700
        return [
          200,
          page([storedMessage(3, 'Recent'), storedMessage(4, 'Remote')]),
        ]
      }
    )
    const wrapper = await mount()
    await selectConversation(wrapper, first.title)
    const container = wrapper.get('.agent-chat__history').element
    const anchor = wrapper.get('.chat-message').element
    let scrollTop = 400
    let scrollHeight = 1000
    let anchorOffset = 0
    vi.spyOn(container, 'scrollHeight', 'get').mockImplementation(
      () => scrollHeight
    )
    vi.spyOn(container, 'scrollTop', 'get').mockImplementation(() => scrollTop)
    vi.spyOn(container, 'scrollTop', 'set').mockImplementation((value) => {
      scrollTop = value
    })
    vi.spyOn(anchor, 'offsetTop', 'get').mockImplementation(() => anchorOffset)
    await wrapper.get('.agent-chat__older').trigger('click')
    await flushPromises()
    await update(first.uuid)
    scrollHeight = 1500
    anchorOffset = 500
    older.resolve(
      200,
      page([storedMessage(1, 'Older'), storedMessage(2, 'Middle')])
    )
    await flushPromises()

    expect(messages(wrapper)).toEqual(['Older', 'Middle', 'Recent', 'Remote'])
    expect(scrollTop).toBe(900)
  })

  test('follows an accepted own message even when reading older history', async () => {
    mockConversations(testApp, page([first]))
    mockMessages(testApp, first.uuid, page([storedMessage(1, 'Earlier')]))
    mockSendMessage(testApp, first.uuid, ({ data }) => [
      200,
      {
        conversation: first,
        message: {
          ...storedMessage(2, 'My new message'),
          uuid: JSON.parse(data).uuid,
        },
      },
    ])
    const wrapper = await mount()
    await selectConversation(wrapper, first.title)
    const container = wrapper.get('.agent-chat__history').element
    let scrollTop = 150
    vi.spyOn(container, 'scrollHeight', 'get').mockReturnValue(1000)
    vi.spyOn(container, 'clientHeight', 'get').mockReturnValue(300)
    vi.spyOn(container, 'scrollTop', 'get').mockImplementation(() => scrollTop)
    vi.spyOn(container, 'scrollTop', 'set').mockImplementation((value) => {
      scrollTop = value
    })

    await sendMessage(wrapper, 'My new message')

    expect(messages(wrapper)).toEqual(['Earlier', 'My new message'])
    expect(scrollTop).toBe(1000)
  })

  test('does not jump to the latest remote message while reading older history', async () => {
    mockConversations(testApp, page([first]))
    mockMessages(testApp, first.uuid, page([storedMessage(1, 'Earlier')]))
    const wrapper = await mount()
    await selectConversation(wrapper, first.title)
    const container = wrapper.get('.agent-chat__history').element
    let scrollTop = 150
    vi.spyOn(container, 'scrollHeight', 'get').mockReturnValue(1000)
    vi.spyOn(container, 'clientHeight', 'get').mockReturnValue(300)
    vi.spyOn(container, 'scrollTop', 'get').mockImplementation(() => scrollTop)
    vi.spyOn(container, 'scrollTop', 'set').mockImplementation((value) => {
      scrollTop = value
    })
    mockMessages(
      testApp,
      first.uuid,
      page([storedMessage(1, 'Earlier'), storedMessage(2, 'Remote message')])
    )

    await update(first.uuid)

    expect(messages(wrapper)).toEqual(['Earlier', 'Remote message'])
    expect(scrollTop).toBe(150)
  })

  test('refreshes cached inactive conversations only when selected again', async () => {
    mockConversations(testApp, page([first, second]))
    mockMessages(testApp, first.uuid, page([storedMessage(1, 'Earlier A')]))
    mockMessages(testApp, second.uuid, page([storedMessage(2, 'Earlier B')]))
    const wrapper = await mount()
    await selectConversation(wrapper, first.title)
    await selectConversation(wrapper, second.title)
    mockMessages(
      testApp,
      first.uuid,
      page([storedMessage(1, 'Earlier A'), storedMessage(3, 'Remote A')])
    )
    const reads = testApp.mock.history.get.filter(({ url }) =>
      url.includes('/messages/')
    ).length

    await update(first.uuid)

    expect(messages(wrapper)).toEqual(['Earlier B'])
    expect(
      testApp.mock.history.get.filter(({ url }) => url.includes('/messages/'))
    ).toHaveLength(reads)
    await selectConversation(wrapper, first.title)
    expect(messages(wrapper)).toEqual(['Earlier A', 'Remote A'])
  })

  test('does not read private data without conversation access or for another Agent', async () => {
    allowed.value = (operation) => !operation.includes('conversation')
    await mount()
    const reads = testApp.mock.history.get.length

    await update(first.uuid)
    await update(first.uuid, 999)

    expect(testApp.mock.history.get).toHaveLength(reads)
    expect(agent._.conversationUpdate.version).toBe(1)
  })
})
