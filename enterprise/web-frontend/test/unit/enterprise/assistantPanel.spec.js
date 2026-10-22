import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'

import assistantService from '@baserow_enterprise/services/assistant'
import AssistantPanel from '@baserow_enterprise/components/assistant/AssistantPanel'
import { TestApp } from '@baserow/test/helpers/testApp'

vi.mock('@baserow_enterprise/services/assistant', () => ({
  default: vi.fn(),
}))

const workspace = { id: 1, name: 'Test workspace' }
const otherWorkspace = { id: 2, name: 'Other workspace' }

describe('AssistantPanel', () => {
  let testApp = null
  let store = null
  let service = null

  beforeEach(async () => {
    vi.clearAllMocks()
    service = {
      fetchChats: vi.fn().mockResolvedValue({ results: [] }),
      fetchChatMessages: vi.fn().mockResolvedValue({ messages: [] }),
      sendMessage: vi.fn().mockResolvedValue(undefined),
    }
    assistantService.mockReturnValue(service)

    testApp = new TestApp()
    store = testApp.store
    // The welcome message greets the user by name; nothing here needs a session.
    store.state.auth.user = { id: 1, first_name: 'Test' }
    await store.dispatch('workspace/forceCreate', workspace)
    await store.dispatch('undoRedo/updateCurrentScopeSet', {
      workspace: workspace.id,
    })
  })

  afterEach(async () => {
    vi.useRealTimers()
    vi.restoreAllMocks()
    await testApp.afterEach()
    vi.unstubAllGlobals()
  })

  async function mountWithRunningChat() {
    const wrapper = await testApp.mount(AssistantPanel, {
      props: { workspace },
    })
    await store.dispatch('assistant/createChat', workspace.id)
    store.commit('assistant/SET_ASSISTANT_RUNNING', {
      chat: store.getters['assistant/currentChat'],
      value: true,
    })
    return { wrapper }
  }

  test('sends a pending prompt in a fresh conversation and focuses the input', async () => {
    await testApp.mount(AssistantPanel, { props: { workspace } })
    await store.dispatch('assistant/createChat', workspace.id)
    const shownChatId = store.getters['assistant/currentChatId']

    await store.dispatch('assistant/setPendingPrompt', 'Build a tracker')
    await flushPromises()

    expect(service.sendMessage).toHaveBeenCalledOnce()
    expect(service.sendMessage.mock.calls[0][0]).not.toBe(shownChatId)
    expect(service.sendMessage.mock.calls[0][1]).toBe('Build a tracker')
    expect(store.getters['assistant/pendingPrompt']).toBe(null)
    expect(document.activeElement.className).toBe('assistant__input-textarea')
  })

  test('drops a pending prompt when the workspace changes before it starts', async () => {
    const { wrapper } = await mountWithRunningChat()
    const dispatch = store.dispatch.bind(store)
    let releasePrompt
    vi.spyOn(store, 'dispatch').mockImplementation(
      (action, payload, ...rest) => {
        const result = dispatch(action, payload, ...rest)
        if (action === 'assistant/setPendingPrompt' && payload === null) {
          return new Promise((resolve) => {
            releasePrompt = () => resolve(result)
          })
        }
        return result
      }
    )

    await store.dispatch('assistant/setPendingPrompt', 'Build a tracker')
    await wrapper.setProps({ workspace: otherWorkspace })
    releasePrompt()
    await flushPromises()

    expect(service.sendMessage).not.toHaveBeenCalled()
  })

  test('does not fetch chats when the selected workspace goes away', async () => {
    const wrapper = await testApp.mount(AssistantPanel, {
      props: { workspace },
    })

    // The selected workspace getter returns an empty object when none is selected.
    await wrapper.setProps({ workspace: {} })
    await flushPromises()

    expect(service.fetchChats).toHaveBeenCalledOnce()
    expect(service.fetchChats).toHaveBeenCalledWith(workspace.id)
  })

  test('keeps response actions hidden until the chat finishes after its first chunk', async () => {
    const { wrapper } = await mountWithRunningChat()
    store.commit('assistant/SET_MESSAGES', [
      {
        id: 7,
        role: 'ai',
        content: 'Partial response',
        loading: false,
        can_submit_feedback: true,
      },
    ])
    await flushPromises()
    expect(wrapper.get('.chat-message__bubble').attributes('aria-busy')).toBe(
      'true'
    )
    expect(wrapper.find('.chat-message__actions').exists()).toBe(false)

    store.commit('assistant/SET_ASSISTANT_RUNNING', {
      chat: store.getters['assistant/currentChat'],
      value: false,
    })
    await flushPromises()
    expect(wrapper.get('.chat-message__bubble').attributes('aria-busy')).toBe(
      'false'
    )
    expect(wrapper.find('.chat-message__actions').exists()).toBe(true)
  })

  test('updates every message time from the panel clock without requesting messages', async () => {
    vi.useFakeTimers({ toFake: ['Date', 'setInterval', 'clearInterval'] })
    vi.setSystemTime(new Date('2026-11-03T10:03:00Z'))
    const { wrapper } = await mountWithRunningChat()
    store.commit('assistant/SET_ASSISTANT_RUNNING', {
      chat: store.getters['assistant/currentChat'],
      value: false,
    })
    store.commit('assistant/SET_MESSAGES', [
      {
        id: 1,
        role: 'human',
        content: 'Question',
        timestamp: '2026-11-03T10:00:00Z',
      },
      {
        id: 2,
        role: 'ai',
        content: 'Answer',
        timestamp: '2026-11-03T10:00:00Z',
      },
    ])
    await flushPromises()

    expect(wrapper.findAll('time').map((time) => time.text())).toEqual([
      'datetime.minutesAgo - 3',
      'datetime.minutesAgo - 3',
    ])
    await vi.advanceTimersByTimeAsync(60000)
    expect(wrapper.findAll('time').map((time) => time.text())).toEqual([
      'datetime.minutesAgo - 4',
      'datetime.minutesAgo - 4',
    ])
    expect(service.fetchChatMessages).not.toHaveBeenCalled()
  })

  test('ignores invisible thinking growth and follows answer text until the user scrolls up', async () => {
    let xhr
    class FakeXHR {
      constructor() {
        xhr = this
        this.responseText = ''
        this.status = 200
      }
      open() {}
      setRequestHeader() {}
      send() {}
      receive(record) {
        this.responseText += JSON.stringify(record) + '\n\n'
        this.onprogress()
      }
    }
    vi.stubGlobal('XMLHttpRequest', FakeXHR)
    const actualService = await vi.importActual(
      '@baserow_enterprise/services/assistant'
    )
    assistantService.mockImplementation(actualService.default)
    testApp.mock
      .onGet('/assistant/chat/?workspace_id=1')
      .reply(200, { results: [] })
    const wrapper = await testApp.mount(AssistantPanel, {
      props: { workspace },
    })
    const sending = store.dispatch('assistant/sendMessage', {
      message: 'A detailed answer, please',
      workspace,
    })
    await flushPromises()

    const container = wrapper.get('.assistant__content').element
    let height = 1000
    let top = 600
    const writes = []
    vi.spyOn(container, 'scrollHeight', 'get').mockImplementation(() => height)
    vi.spyOn(container, 'clientHeight', 'get').mockReturnValue(400)
    vi.spyOn(container, 'scrollTop', 'get').mockImplementation(() => top)
    vi.spyOn(container, 'scrollTop', 'set').mockImplementation((value) => {
      writes.push(value)
      top = Math.min(value, height - 400)
    })
    const receive = async (record) => {
      xhr.receive(record)
      await flushPromises()
      await new Promise((resolve) => setTimeout(resolve, 0))
    }
    const content = Array.from(
      { length: 40 },
      (_, index) => `Paragraph ${index}: Detailed text.`
    ).join('\n\n')
    await receive({ type: 'ai/reasoning', content })
    expect(wrapper.find('.assistant__reasoning--collapsed').exists()).toBe(true)
    expect(wrapper.find('.chat-message__bubble--thinking').exists()).toBe(true)
    writes.length = 0

    // The preview has reached its cap; more thinking does not change its height.
    await receive({
      type: 'ai/reasoning',
      content: content + '\n\nMore thinking',
    })
    expect(writes).toEqual([])
    height = 1400
    await receive({ type: 'ai/message', content, sources: [] })
    expect(store.getters['assistant/currentChat'].running).toBe(true)
    expect(wrapper.find('.assistant__reasoning--collapsed').exists()).toBe(
      false
    )
    expect(wrapper.find('.assistant__reasoning-toggle').exists()).toBe(false)
    expect(wrapper.findAll('.chat-markdown p')).toHaveLength(40)
    expect(wrapper.find('.chat-message__bubble--thinking').exists()).toBe(false)
    expect(writes).toEqual([1400])

    // A later tool call can reveal that the streamed text was only its preface.
    height = 1000
    await receive({ type: 'ai/reasoning', content })
    expect(wrapper.find('.chat-message__bubble--thinking').exists()).toBe(true)
    expect(wrapper.find('.assistant__reasoning--collapsed').exists()).toBe(true)
    expect(wrapper.find('.assistant__reasoning-toggle').exists()).toBe(true)
    await receive({ type: 'ai/reasoning', content: '' })
    expect(wrapper.find('.chat-message__bubble--thinking').exists()).toBe(true)
    expect(wrapper.find('.chat-typing').exists()).toBe(true)
    expect(wrapper.find('.assistant__reasoning-toggle').exists()).toBe(false)
    height = 1400
    await receive({ type: 'ai/message', content, sources: [] })
    expect(wrapper.find('.chat-message__bubble--thinking').exists()).toBe(false)
    expect(wrapper.find('.assistant__reasoning--collapsed').exists()).toBe(
      false
    )

    container.scrollTop = 200
    await wrapper.get('.assistant__content').trigger('scroll')
    writes.length = 0
    height = 1600
    const final = content + '\n\nThe final paragraph.'
    await receive({ type: 'ai/message', content: final, sources: [] })
    await receive({
      type: 'ai/message',
      id: 7,
      content: final,
      sources: [],
      can_submit_feedback: true,
    })
    xhr.onload()
    await sending
    await flushPromises()

    expect(writes).toEqual([])
    expect(top).toBe(200)
    expect(wrapper.findAll('.chat-markdown p')).toHaveLength(41)
    expect(wrapper.find('.chat-message__bubble--thinking').exists()).toBe(false)
    expect(wrapper.find('.assistant__reasoning-toggle').exists()).toBe(false)
    expect(wrapper.find('button[aria-label="action.copy"]').exists()).toBe(true)
    expect(store.getters['assistant/currentChat'].running).toBe(false)
  })

  describe('when Kuma creates a table the store never hears about', () => {
    const database = {
      id: 10,
      type: 'database',
      name: 'CRM',
      order: 1,
      workspace,
      tables: [],
    }
    const newTable = { id: 20, name: 'Leads', order: 1, database_id: 10 }
    let push = null

    beforeEach(async () => {
      vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'Date'] })
      await store.dispatch('application/forceCreate', database)
      await testApp.mount(AssistantPanel, { props: { workspace } })
      push = vi.spyOn(testApp.nuxtApp.$router, 'push').mockResolvedValue()
    })

    async function kumaNavigatesToTheNewTable(location = {}) {
      store.commit('assistant/SET_UI_LOCATION', {
        type: 'database-table',
        database_id: database.id,
        table_id: newTable.id,
        ...location,
      })
      await vi.advanceTimersByTimeAsync(11000)
      await flushPromises()
    }

    test.each(['has', 'lacks'])(
      'fetches and opens the table when the store %s its database',
      async (storeDatabase) => {
        if (storeDatabase === 'lacks') {
          store.commit('application/DELETE_ITEM', database.id)
        }
        testApp.mock
          .onGet(`/applications/${database.id}/`)
          .reply(200, { ...database, tables: [newTable] })

        await kumaNavigatesToTheNewTable()

        expect(push).toHaveBeenCalledExactlyOnceWith({
          name: 'database-table',
          params: expect.objectContaining({
            databaseId: database.id,
            tableId: newTable.id,
          }),
        })
      }
    )

    test('stays put without an unhandled rejection when the table is missing', async () => {
      const unhandled = vi.fn()
      testApp.mock.onGet(`/applications/${database.id}/`).reply(200, database)
      process.on('unhandledRejection', unhandled)

      try {
        await kumaNavigatesToTheNewTable()
      } finally {
        process.off('unhandledRejection', unhandled)
      }

      expect(push).not.toHaveBeenCalled()
      expect(unhandled).not.toHaveBeenCalled()
    })

    test('fetches a new view of a table whose views are loaded and opens it', async () => {
      const view = { id: 30, table_id: newTable.id, type: 'grid', order: 1 }
      await store.dispatch('table/forceUpsert', {
        database: store.getters['application/get'](database.id),
        data: newTable,
      })
      store.commit('view/SET_TABLE_ID', newTable.id)
      testApp.mock.onGet(`/database/views/${view.id}/`).reply(200, view)

      await kumaNavigatesToTheNewTable({
        type: 'database-view',
        view_id: view.id,
        view_type: view.type,
      })

      expect(push).toHaveBeenCalledWith({
        name: 'database-table',
        params: expect.objectContaining({ viewId: view.id }),
      })
      expect(store.getters['view/get'](view.id)).toBeDefined()
    })
  })
})
