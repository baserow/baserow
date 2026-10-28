import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'

import assistantService from '@baserow_enterprise/services/assistant'
import AssistantPanel from '@baserow_enterprise/components/assistant/AssistantPanel'
import { TestApp } from '@baserow/test/helpers/testApp'

vi.mock('@baserow_enterprise/services/assistant', () => ({
  default: vi.fn(),
}))

const workspace = { id: 1, name: 'Test workspace' }

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
  })

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

  describe('when Kuma creates a table or view the store never hears about', () => {
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
