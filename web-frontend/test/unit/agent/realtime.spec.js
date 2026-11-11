import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import service from '@baserow/modules/core/services/chatRuns'
import { registerRealtimeEvents } from '@baserow/modules/agent/realtime'
import {
  filterConversations,
  agentData,
  composer,
  conversation,
  conversationTitles,
  createAgentPage,
  chooseFromMenu,
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
  conversationsPage,
} from './helpers'

vi.mock('@baserow/modules/core/services/chatRuns', () => ({ default: vi.fn() }))

const storedMessage = (id, content) => ({
  ...message(`message-${id}`, content),
  id,
})
const remoteReply = (id) =>
  message(`reply-${id}`, '', {
    id,
    role: 'assistant',
    status: 'running',
    runId: 'remote-run',
  })
const first = conversation('conversation-a', 'Conversation A')
const second = conversation('conversation-b', 'Conversation B')
const isRecovery = (request) =>
  request.headers['X-Baserow-Realtime-Recovery'] === 'true'

describe('Agent conversation realtime updates', () => {
  let testApp, agent, allowed, mount, receivers

  beforeEach(async () => {
    ;({ testApp, agent, allowed, mount } = await createAgentPage())
    service.mockReturnValue({
      get: vi.fn().mockResolvedValue({ status: 'running' }),
      stream: vi.fn(() => new Promise(() => {})),
    })
    receivers = {}
    registerRealtimeEvents({
      registerEvent: (type, handler) => {
        receivers[type] = handler
      },
    })
  })

  afterEach(() => destroyAgentPage(testApp))

  const update = async (
    uuid,
    {
      runId = null,
      updatedOn = '2026-10-22T10:00:00Z',
      agentId = agentData.id,
      title = '',
    } = {}
  ) => {
    receivers.agent_conversation_activity(
      { store: testApp.store },
      {
        agent_id: agentId,
        conversation_uuid: uuid,
        conversation: {
          ...conversation(uuid, title, updatedOn),
          run_id: runId,
          pending_approval_count: 0,
        },
      }
    )
    await flushPromises()
  }
  const reconnect = async (chatId) => {
    testApp.getRegistry().get('chatRunType', 'agent').refreshChat(chatId)
    await flushPromises()
  }

  test('lists a remote conversation and loads a remote reply, keeping history, draft and focus', async () => {
    mockConversations(
      testApp,
      conversationsPage([first], 'next'),
      conversationsPage([second])
    )
    mockMessages(
      testApp,
      second.uuid,
      page([storedMessage(2, 'Recent')], 'next'),
      page([storedMessage(1, 'Older')])
    )
    const wrapper = await mount()
    await wrapper.get('.agent-conversations__content').trigger('scroll')
    await flushPromises()
    await selectConversation(wrapper, second.title)
    await wrapper.get('.agent-chat__older').trigger('click')
    await flushPromises()
    await composer(wrapper).setValue('Unfinished draft')
    const textarea = composer(wrapper).element
    textarea.focus()
    const listReads = testApp.mock.history.get.filter(({ url }) =>
      url.endsWith('/conversations/')
    ).length
    mockMessages(
      testApp,
      second.uuid,
      page([storedMessage(3, 'Remote message'), remoteReply(4)], 'next'),
      page([storedMessage(2, 'Recent')], 'next')
    )

    await update('conversation-c', { title: 'New remote conversation' })
    await update(second.uuid, { runId: 'remote-run' })

    expect(conversationTitles(wrapper)).toContain('New remote conversation')
    expect(
      testApp.mock.history.get.filter(({ url }) =>
        url.endsWith('/conversations/')
      )
    ).toHaveLength(listReads)
    expect(selected(wrapper).text()).toContain(second.title)
    expect(messages(wrapper)).toEqual(['Older', 'Recent', 'Remote message', ''])
    expect(composer(wrapper).element).toBe(textarea)
    expect(document.activeElement).toBe(textarea)
    expect(textarea.value).toBe('Unfinished draft')
    expect(agent).not.toHaveProperty('messages')
    expect(agent._.realtimeVersion).toBe(0)
  })

  test('keeps a send accepted after a background read started in API order', async () => {
    mockConversations(testApp, conversationsPage([first]))
    mockMessages(testApp, first.uuid, page([storedMessage(1, 'Earlier')]))
    const wrapper = await mount()
    await selectConversation(wrapper, first.title)
    const refresh = deferredReply()
    mockMessages(testApp, first.uuid, refresh.reply)
    await reconnect(first.id)
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

  test('loads a remote reply that starts during the first history load without replacing the draft', async () => {
    mockConversations(testApp, conversationsPage([first]))
    const initial = deferredReply()
    mockMessages(
      testApp,
      first.uuid,
      initial.reply,
      page([
        storedMessage(1, 'Earlier'),
        storedMessage(2, 'Remote message'),
        remoteReply(3),
      ])
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

    await update(first.uuid, { runId: 'remote-run' })
    initial.resolve(200, page([storedMessage(1, 'Earlier')]))
    await flushPromises()

    expect(messages(wrapper)).toEqual(['Earlier', 'Remote message', ''])
    expect(composer(wrapper).element).toBe(textarea)
    expect(textarea.value).toBe('Writing during load')
    expect(document.activeElement).toBe(textarea)
  })

  test('queues a reconnect read during a send without duplicating the accepted message', async () => {
    mockConversations(testApp, conversationsPage([first]))
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

    await reconnect(first.id)

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
    mockConversations(testApp, conversationsPage([first]))
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

    await reconnect(first.id)

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
    mockConversations(testApp, conversationsPage([first]))
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
    await reconnect(first.id)
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
    mockConversations(testApp, conversationsPage([first]))
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
    mockConversations(testApp, conversationsPage([first]))
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

    await reconnect(first.id)

    expect(messages(wrapper)).toEqual(['Earlier', 'Remote message'])
    expect(scrollTop).toBe(150)
  })

  test('refreshes cached inactive conversations only when selected again', async () => {
    mockConversations(testApp, conversationsPage([first, second]))
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

  test('pulses the dot while any session writes a reply, without reading again', async () => {
    mockConversations(
      testApp,
      conversationsPage([first, { ...second, run_id: 'run-b' }])
    )
    const wrapper = await mount()
    const replying = () =>
      wrapper
        .findAll('.agent-conversations__item')
        .filter((item) =>
          item.find('.agent-conversations__status--replying').exists()
        )
        .map((item) => item.text())
    const reads = testApp.mock.history.get.length
    expect(replying()).toEqual(['Conversation B'])

    await update(first.uuid, {
      runId: 'run-a',
      updatedOn: '2026-10-22T10:00:00Z',
    })
    await update(second.uuid, { updatedOn: '2026-10-22T10:00:01Z' })
    expect(conversationTitles(wrapper)).toEqual([second.title, first.title])
    expect(replying()).toEqual(['Conversation A'])

    // A start delivered after its end must not relight the dot.
    await update(first.uuid, { updatedOn: '2026-10-22T10:00:02Z' })
    await update(first.uuid, {
      runId: 'run-a',
      updatedOn: '2026-10-22T10:00:00Z',
    })
    expect(replying()).toEqual([])
    expect(testApp.mock.history.get).toHaveLength(reads)
  })

  test('does not read private data without conversation access or for another Agent', async () => {
    allowed.value = (operation) => !operation.includes('conversation')
    await mount()
    const reads = testApp.mock.history.get.length

    await update(first.uuid)
    await update(first.uuid, { agentId: 999 })

    expect(testApp.mock.history.get).toHaveLength(reads)
    expect(agent._.conversationUpdate.version).toBe(1)
  })

  test('does not bring back a conversation deleted while the list was being read', async () => {
    const stale = deferredReply()
    mockConversations(
      testApp,
      conversationsPage([first]),
      stale.reply,
      conversationsPage([second])
    )
    const wrapper = await mount()
    await reconnect(first.id)

    receivers.agent_conversation_deleted(
      { store: testApp.store },
      { agent_id: agentData.id, conversation_uuid: first.uuid }
    )
    stale.resolve(200, conversationsPage([first, second]))
    await flushPromises()

    expect(conversationTitles(wrapper)).toEqual([second.title])
    const reads = testApp.mock.history.get.filter(
      ({ url }) => url === '/agent/10/conversations/'
    )
    expect(reads).toHaveLength(3)
    expect(reads.at(-1)).toSatisfy(isRecovery)
  })

  test('keeps a conversation deleted while its message was being sent', async () => {
    mockConversations(testApp, conversationsPage([first, second]))
    mockMessages(testApp, first.uuid, page([]))
    mockMessages(testApp, second.uuid, page([]))
    const write = deferredReply()
    mockSendMessage(testApp, first.uuid, write.reply)
    const wrapper = await mount()
    await selectConversation(wrapper, first.title)
    await sendMessage(wrapper, 'My message')

    receivers.agent_conversation_deleted(
      { store: testApp.store },
      { agent_id: agentData.id, conversation_uuid: first.uuid }
    )
    write.resolve(200, {
      conversation: first,
      message: storedMessage(1, 'My message'),
    })
    await flushPromises()

    expect(conversationTitles(wrapper)).toEqual([second.title])
  })

  test('keeps a rename that an older list read missed', async () => {
    const stale = deferredReply()
    const renamed = { ...first, title: 'Renamed' }
    mockConversations(
      testApp,
      conversationsPage([first]),
      stale.reply,
      conversationsPage([renamed])
    )
    const saved = deferredReply()
    testApp.mock
      .onPatch(`/agent/10/conversations/${first.uuid}/`)
      .reply(saved.reply)
    const wrapper = await mount()
    await chooseFromMenu(wrapper, first.title, 'action.rename')
    const input = wrapper.get('.agent-conversations__rename')
    await input.setValue(renamed.title)
    await input.trigger('keydown', { key: 'Enter' })

    // The read starts after the rename shows, but answers before it's saved.
    await reconnect(first.id)
    saved.resolve(200, renamed)
    await flushPromises()
    stale.resolve(200, conversationsPage([first]))
    await flushPromises()

    expect(conversationTitles(wrapper)).toEqual([renamed.title])
  })

  const paged = {
    a: conversation('paged-a', 'A', '2026-10-14T10:04:00Z'),
    b: conversation('paged-b', 'B', '2026-10-14T10:03:00Z'),
    c: conversation('paged-c', 'C', '2026-10-14T10:02:00Z'),
    d: conversation('paged-d', 'D', '2026-10-14T10:01:00Z'),
  }
  const loadMore = async (wrapper) => {
    await wrapper.get('.agent-conversations__content').trigger('scroll')
    await flushPromises()
  }
  const hasMore = (wrapper) =>
    wrapper.find('.infinite-scroll__loading-wrapper').isVisible()

  test('lists a restored conversation only inside the loaded pages', async () => {
    const { a, b, c, d } = paged
    mockConversations(
      testApp,
      conversationsPage([a, b], 'after-b'),
      conversationsPage([c, d])
    )
    const wrapper = await mount()

    await update(c.uuid, { title: c.title, updatedOn: c.updated_on })
    expect(conversationTitles(wrapper)).toEqual(['A', 'B'])

    await loadMore(wrapper)
    receivers.agent_conversation_deleted(
      { store: testApp.store },
      { agent_id: agentData.id, conversation_uuid: c.uuid }
    )
    await flushPromises()
    expect(conversationTitles(wrapper)).toEqual(['A', 'B', 'D'])

    await update(c.uuid, { title: c.title, updatedOn: c.updated_on })
    expect(conversationTitles(wrapper)).toEqual(['A', 'B', 'C', 'D'])
    expect(hasMore(wrapper)).toBe(false)
    expect(
      testApp.mock.history.get.filter(({ url }) =>
        url.endsWith('/conversations/')
      )
    ).toHaveLength(2)
  })

  test('reads the loaded pages again after a reconnect, dropping deleted ones', async () => {
    const { a, b, c, d } = paged
    mockConversations(
      testApp,
      conversationsPage([a, b], 'after-b'),
      conversationsPage([c, d]),
      conversationsPage([a, b], 'after-b'),
      conversationsPage([d])
    )
    const wrapper = await mount()
    await loadMore(wrapper)

    await reconnect(a.id)

    expect(conversationTitles(wrapper)).toEqual(['A', 'B', 'D'])
    expect(hasMore(wrapper)).toBe(false)
    expect(
      testApp.mock.history.get
        .filter(({ url }) => url.endsWith('/conversations/'))
        .map(({ params }) => params.cursor)
    ).toEqual([null, 'after-b', null, 'after-b'])
  })

  test('renames and removes conversations changed in another session', async () => {
    mockConversations(testApp, conversationsPage([first, second]))
    mockMessages(testApp, first.uuid, page([]))
    mockMessages(testApp, second.uuid, page([]))
    const wrapper = await mount()
    await selectConversation(wrapper, first.title)
    const reads = testApp.mock.history.get.length
    const receive = (type, data) =>
      receivers[type](
        { store: testApp.store },
        { agent_id: agentData.id, ...data }
      )

    receive('agent_conversation_updated', {
      conversation_uuid: second.uuid,
      values: { title: 'Renamed elsewhere' },
    })
    receive('agent_conversation_deleted', { conversation_uuid: first.uuid })
    await flushPromises()

    expect(conversationTitles(wrapper)).toEqual(['Renamed elsewhere'])
    expect(selected(wrapper).text()).toContain('Renamed elsewhere')
    // Only the newly selected conversation's history is read.
    expect(testApp.mock.history.get.slice(reads).map(({ url }) => url)).toEqual(
      [`/agent/10/conversations/${second.uuid}/messages/`]
    )
  })

  test('fetches an older conversation pinned elsewhere into the first group', async () => {
    const pinned = { ...second, pinned: true }
    mockConversations(
      testApp,
      conversationsPage([first], 'older'),
      conversationsPage([pinned, first], 'older')
    )
    mockMessages(testApp, first.uuid, page([message('m', 'Hello')]))
    const wrapper = await mount()
    await selectConversation(wrapper, first.title)
    await composer(wrapper).setValue('Unsent')
    receivers.agent_conversation_updated(
      { store: testApp.store },
      {
        agent_id: agentData.id,
        conversation_uuid: second.uuid,
        values: { pinned: true },
      }
    )
    await flushPromises()
    expect(conversationTitles(wrapper)).toEqual([second.title, first.title])
    expect(composer(wrapper).element.value).toBe('Unsent')
    expect(selected(wrapper).text()).toBe(first.title)
  })

  test('removes a decided conversation from the waiting filter without closing it', async () => {
    const waiting = { ...first, pending_approval_count: 1 }
    mockConversations(
      testApp,
      conversationsPage([waiting]),
      conversationsPage([waiting])
    )
    mockMessages(testApp, first.uuid, page([message('m', 'Hello')]))
    const wrapper = await mount()
    await filterConversations(wrapper, 'agent.waitingForApprovalFilter')
    await selectConversation(wrapper, first.title)
    await composer(wrapper).setValue('Draft')
    await update(first.uuid)
    expect(conversationTitles(wrapper)).toEqual([])
    expect(wrapper.get('.agent-conversations__empty').text()).toBe(
      'agent.noMatchingConversations'
    )
    expect(composer(wrapper).element.value).toBe('Draft')
    expect(messages(wrapper)).toEqual(['Hello'])
  })
})
