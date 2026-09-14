import { expect } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import MockAdapter from 'axios-mock-adapter'

function chat(id, values = {}) {
  return {
    id,
    uuid: `uuid-${id}`,
    title: `Chat ${id}`,
    status: 'idle',
    updated_on: '2026-08-27T10:00:00Z',
    ...values,
  }
}

describe('agentHistory store', () => {
  let store = null
  let mock = null

  beforeEach(() => {
    const { $store, $client } = useNuxtApp()
    store = $store
    mock = new MockAdapter($client, { onNoMatch: 'throwException' })
  })

  afterEach(() => {
    mock.restore()
  })

  test('fetch stores the paginated results and fetchMore appends the next page', async () => {
    mock.onGet('agent_application/42/chats/').replyOnce(200, {
      count: 3,
      next: 'http://localhost/api/agent_application/42/chats/?offset=2',
      previous: null,
      results: [
        chat(2, { updated_on: '2026-08-27T10:00:00Z' }),
        chat(1, { updated_on: '2026-08-25T10:00:00Z' }),
      ],
    })
    await store.dispatch('agentHistory/fetch', { applicationId: 42 })

    expect(
      store.getters['agentHistory/getChats'].map((c) => c.id)
    ).toStrictEqual([2, 1])
    expect(store.getters['agentHistory/hasMore']).toBe(true)

    mock.onGet('agent_application/42/chats/').replyOnce(200, {
      count: 3,
      next: null,
      previous: 'http://localhost/api/agent_application/42/chats/?offset=0',
      results: [chat(3, { updated_on: '2026-08-24T10:00:00Z' })],
    })
    await store.dispatch('agentHistory/fetchMore', { applicationId: 42 })

    expect(
      store.getters['agentHistory/getChats'].map((c) => c.id)
    ).toStrictEqual([2, 1, 3])
    expect(store.getters['agentHistory/hasMore']).toBe(false)
  })

  test('forceUpdateChat inserts new chats sorted by updated_on descending', async () => {
    mock.onGet('agent_application/42/chats/').replyOnce(200, {
      count: 2,
      next: null,
      previous: null,
      results: [
        chat(1, { title: 'Oldest', updated_on: '2026-08-25T10:00:00Z' }),
        chat(2, { title: 'Newest', updated_on: '2026-08-27T10:00:00Z' }),
      ],
    })
    await store.dispatch('agentHistory/fetch', { applicationId: 42 })

    // An upsert of a chat that is not in the (partial) list inserts it.
    await store.dispatch('agentHistory/forceUpdateChat', {
      chat: chat(3, {
        title: 'Middle',
        status: 'in_progress',
        updated_on: '2026-08-26T10:00:00Z',
      }),
    })

    expect(
      store.getters['agentHistory/getChats'].map((c) => c.id)
    ).toStrictEqual([2, 3, 1])
    expect(
      store.getters['agentHistory/getRunningChats'].map((c) => c.id)
    ).toStrictEqual([3])
  })

  test('forceUpdateChat updates an existing chat and resorts the list', async () => {
    await store.dispatch('agentHistory/forceUpdateChat', {
      chat: chat(1, {
        title: 'Middle',
        status: 'in_progress',
        updated_on: '2026-08-26T10:00:00Z',
      }),
    })

    await store.dispatch('agentHistory/forceUpdateChat', {
      chat: chat(1, {
        title: 'Middle updated',
        status: 'idle',
        updated_on: '2026-08-28T10:00:00Z',
      }),
    })

    const chats = store.getters['agentHistory/getChats']
    const updated = chats.find((c) => c.id === 1)
    expect(updated.title).toBe('Middle updated')
    expect(updated.status).toBe('idle')
    expect(chats.map((c) => c.id)[0]).toBe(1)
    expect(chats.filter((c) => c.id === 1).length).toBe(1)
  })

  test('forceDeleteChat removes the chat from the list', async () => {
    await store.dispatch('agentHistory/forceUpdateChat', {
      chat: chat(9),
    })
    expect(store.getters['agentHistory/getChats'].some((c) => c.id === 9)).toBe(
      true
    )

    await store.dispatch('agentHistory/forceDeleteChat', { chatId: 9 })

    expect(store.getters['agentHistory/getChats'].some((c) => c.id === 9)).toBe(
      false
    )
  })
})

describe('agentHistory store pinning and deleting', () => {
  let store = null
  let mock = null

  beforeEach(() => {
    const { $store, $client } = useNuxtApp()
    store = $store
    mock = new MockAdapter($client, { onNoMatch: 'throwException' })
  })

  afterEach(() => {
    mock.restore()
  })

  test('updateChat pins optimistically and orders pinned chats first', async () => {
    store.commit('agentHistory/SET_CHATS', [
      chat(1, { updated_on: '2026-08-27T10:00:00Z' }),
      chat(2, { updated_on: '2026-08-25T10:00:00Z' }),
    ])
    let resolve = null
    mock.onPatch('agent_application/chats/uuid-2/').replyOnce(
      () =>
        new Promise((r) => {
          resolve = r
        })
    )
    const promise = store.dispatch('agentHistory/updateChat', {
      chatUuid: 'uuid-2',
      values: { pinned: true },
    })
    expect(store.getters['agentHistory/getChats'].map((c) => c.id)).toEqual([
      2, 1,
    ])
    expect(
      store.getters['agentHistory/getPinnedChats'].map((c) => c.id)
    ).toEqual([2])
    await flushPromises()
    resolve([200, chat(2, { pinned: true, title: 'Server' })])
    await promise
    expect(store.getters['agentHistory/getChats'][0].title).toBe('Server')
  })

  test('updateChat reverts when the request fails', async () => {
    store.commit('agentHistory/SET_CHATS', [chat(1, { title: 'Old' })])
    mock.onPatch('agent_application/chats/uuid-1/').replyOnce(400, {})
    await expect(
      store.dispatch('agentHistory/updateChat', {
        chatUuid: 'uuid-1',
        values: { title: 'New' },
      })
    ).rejects.toBeTruthy()
    expect(store.getters['agentHistory/getChats'][0].title).toBe('Old')
  })

  test('deleteChat removes the chat and resets the open conversation', async () => {
    store.commit('agentHistory/SET_CHATS', [chat(1), chat(2)])
    store.commit('agentChat/SET_CHAT_ID', 1)
    mock.onDelete('agent_application/chats/uuid-1/').replyOnce(204)
    await store.dispatch('agentHistory/deleteChat', { chat: chat(1) })
    expect(store.getters['agentHistory/getChats'].map((c) => c.id)).toEqual([2])
    expect(store.getters['agentChat/getChatId']).toBe(null)
  })
})
