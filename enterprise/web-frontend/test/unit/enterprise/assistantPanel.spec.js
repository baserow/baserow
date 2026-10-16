import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'

import assistantService from '@baserow_enterprise/services/assistant'
import AssistantPanel from '@baserow_enterprise/components/assistant/AssistantPanel'
import { TestApp } from '@baserow/test/helpers/testApp'

vi.mock('@baserow_enterprise/services/assistant', () => ({
  default: vi.fn(),
}))
vi.mock('@baserow_enterprise/utils/assistant', async (importOriginal) => ({
  ...(await importOriginal()),
  usesBackgroundRuns: () => false,
}))

const workspace = { id: 1, name: 'Test workspace' }
const otherWorkspace = { id: 2, name: 'Other workspace' }

describe('AssistantPanel', () => {
  let testApp = null
  let store = null
  let service = null
  let resolveCancel = null

  beforeEach(async () => {
    vi.clearAllMocks()
    service = {
      fetchChats: vi.fn().mockResolvedValue({ results: [] }),
      fetchChatMessages: vi.fn().mockResolvedValue({ messages: [] }),
      sendMessage: vi.fn().mockResolvedValue(undefined),
      // Resolved by the test, so a prompt can arrive while cancelling.
      cancelMessage: vi.fn(
        () =>
          new Promise((resolve) => {
            resolveCancel = resolve
          })
      ),
    }
    assistantService.mockReturnValue(service)

    testApp = new TestApp()
    store = testApp.store
    // The welcome message greets the user by name; nothing here needs a session.
    store.state.auth.user = { id: 1, first_name: 'Test' }
    await store.dispatch('workspace/forceCreate', workspace)
    await store.dispatch('workspace/forceCreate', otherWorkspace)
    await store.dispatch('undoRedo/updateCurrentScopeSet', {
      workspace: workspace.id,
    })
  })

  afterEach(async () => {
    vi.useRealTimers()
    vi.restoreAllMocks()
    await testApp.afterEach()
  })

  async function mountWithRunningChat() {
    const wrapper = await testApp.mount(AssistantPanel, {
      props: { workspace },
    })
    await store.dispatch('assistant/createChat', workspace.id)
    const runningChatId = store.getters['assistant/currentChatId']
    store.commit('assistant/SET_ASSISTANT_RUNNING', {
      chat: store.getters['assistant/currentChat'],
      value: true,
    })
    return { wrapper, runningChatId }
  }

  test('sends a pending prompt in a fresh conversation and focuses the input', async () => {
    const { runningChatId } = await mountWithRunningChat()

    await store.dispatch('assistant/setPendingPrompt', 'Build a tracker')
    await flushPromises()
    resolveCancel()
    await flushPromises()

    expect(service.cancelMessage).toHaveBeenCalledWith(runningChatId)
    expect(service.sendMessage).toHaveBeenCalledOnce()
    expect(service.sendMessage.mock.calls[0][0]).not.toBe(runningChatId)
    expect(service.sendMessage.mock.calls[0][1]).toBe('Build a tracker')
    expect(store.getters['assistant/pendingPrompt']).toBe(null)
    expect(document.activeElement.className).toBe('assistant__input-textarea')
  })

  test('drops a pending prompt when the workspace changes while cancelling', async () => {
    const { wrapper } = await mountWithRunningChat()

    await store.dispatch('assistant/setPendingPrompt', 'Build a tracker')
    await flushPromises()
    await wrapper.setProps({ workspace: otherWorkspace })
    resolveCancel()
    await flushPromises()

    expect(service.sendMessage).not.toHaveBeenCalled()
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

    async function kumaNavigatesToTheNewTable() {
      store.commit('assistant/SET_UI_LOCATION', {
        type: 'database-table',
        database_id: database.id,
        table_id: newTable.id,
      })
      await vi.advanceTimersByTimeAsync(11000)
      await flushPromises()
    }

    test('fetches the database and opens the table', async () => {
      testApp.mock
        .onGet(`/applications/${database.id}/`)
        .reply(200, { ...database, tables: [newTable] })

      await kumaNavigatesToTheNewTable()

      expect(push).toHaveBeenCalledWith({
        name: 'database-table',
        params: expect.objectContaining({
          databaseId: database.id,
          tableId: newTable.id,
        }),
      })
    })

    test('adds a database the store lacks and opens the table', async () => {
      store.commit('application/DELETE_ITEM', database.id)
      testApp.mock
        .onGet(`/applications/${database.id}/`)
        .reply(200, { ...database, tables: [newTable] })

      await kumaNavigatesToTheNewTable()

      expect(push).toHaveBeenCalledOnce()
    })

    test('opens the table once when its broadcast lands during the fetch', async () => {
      testApp.mock.onGet(`/applications/${database.id}/`).reply(() => {
        store.dispatch('table/forceUpsert', {
          database: store.getters['application/get'](database.id),
          data: newTable,
        })
        return [200, { ...database, tables: [newTable] }]
      })

      await kumaNavigatesToTheNewTable()

      expect(push).toHaveBeenCalledOnce()
    })

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
  })
})
