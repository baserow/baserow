import { beforeEach, describe, expect, test, vi } from 'vitest'

import assistantService from '@baserow_enterprise/services/assistant'
import { TestApp } from '@baserow/test/helpers/testApp'

vi.mock('@baserow_enterprise/services/assistant', () => ({
  default: vi.fn(),
}))

const workspace = { id: 1, name: 'Test workspace' }

const serverChat = (uuid, title = 'Persisted') => ({
  uuid,
  title,
  created_on: '2026-09-15T10:00:00Z',
  updated_on: '2026-09-15T10:00:00Z',
  status: 'completed',
})

describe('Assistant store', () => {
  let testApp = null
  let store = null
  let service = null

  beforeEach(async () => {
    vi.clearAllMocks()
    service = {
      fetchChats: vi.fn().mockResolvedValue({ results: [] }),
      fetchChatMessages: vi.fn().mockResolvedValue({ messages: [] }),
      sendMessage: vi.fn().mockResolvedValue(undefined),
      cancelMessage: vi.fn().mockResolvedValue(undefined),
      submitFeedback: vi.fn().mockResolvedValue(undefined),
    }
    assistantService.mockReturnValue(service)

    testApp = new TestApp()
    store = testApp.store
    // `uiContext` builds the assistant payload from the current undo/redo scope.
    await store.dispatch('workspace/forceCreate', workspace)
    await store.dispatch('undoRedo/updateCurrentScopeSet', {
      workspace: workspace.id,
    })
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('sending a message recovers when the current chat is gone', async () => {
    store.commit('assistant/SET_CURRENT_CHAT_ID', 'dropped')

    await store.dispatch('assistant/sendMessage', {
      message: 'hello',
      workspace,
    })

    expect(service.sendMessage).toHaveBeenCalledOnce()
    const currentChatId = store.getters['assistant/currentChatId']
    expect(currentChatId).not.toBe('dropped')
    expect(store.getters['assistant/currentChat']).toBeDefined()
    expect(service.sendMessage.mock.calls[0][0]).toBe(currentChatId)
  })

  test('removing a chat removes it by id', async () => {
    store.commit('assistant/SET_CHATS', [
      serverChat('first'),
      serverChat('second'),
    ])

    store.commit('assistant/REMOVE_CHAT', 'first')

    expect(store.getters['assistant/chats'].map((c) => c.id)).toStrictEqual([
      'second',
    ])
  })

  test('sending a message leaves the assistant idle once it finishes', async () => {
    await store.dispatch('assistant/createChat', workspace.id)
    service.sendMessage.mockImplementation(
      async (chatUuid, message, uiContext, onUpdate) => {
        await onUpdate({ type: 'ai/message', content: 'hi' })
      }
    )

    await store.dispatch('assistant/sendMessage', {
      message: 'hello',
      workspace,
    })

    expect(store.getters['assistant/currentChat'].running).toBe(false)
  })

  test('a late title goes to the chat it was generated for', async () => {
    await store.dispatch('assistant/createChat', workspace.id)
    const firstChatId = store.getters['assistant/currentChatId']
    service.sendMessage.mockImplementation(
      async (chatUuid, message, uiContext, onUpdate) => {
        // The user started another chat before this one got its title.
        await store.dispatch('assistant/clearChat')
        await store.dispatch('assistant/createChat', workspace.id)
        await onUpdate({ type: 'chat/title', content: 'First title' })
        await onUpdate({ type: 'ai/message', content: 'hi' })
      }
    )

    await store.dispatch('assistant/sendMessage', {
      message: 'hello',
      workspace,
    })

    const chats = store.getters['assistant/chats']
    expect(chats.find((c) => c.id === firstChatId).title).toBe('First title')
    expect(store.getters['assistant/currentChat'].title).toBe('')
  })

  test('fetching chats keeps a current chat that is not persisted yet', async () => {
    await store.dispatch('assistant/createChat', workspace.id)
    const unsavedChatId = store.getters['assistant/currentChatId']
    service.fetchChats.mockResolvedValue({ results: [serverChat('persisted')] })

    await store.dispatch('assistant/fetchChats', workspace.id)

    expect(store.getters['assistant/chats'].map((c) => c.id)).toStrictEqual([
      unsavedChatId,
      'persisted',
    ])
    expect(store.getters['assistant/currentChat']).toBeDefined()
  })

  test('fetching chats replaces a current chat the server also returns', async () => {
    store.commit('assistant/SET_CHATS', [serverChat('persisted', 'Old title')])
    store.commit('assistant/SET_CURRENT_CHAT_ID', 'persisted')
    service.fetchChats.mockResolvedValue({
      results: [serverChat('persisted', 'New title')],
    })

    await store.dispatch('assistant/fetchChats', workspace.id)

    expect(store.getters['assistant/chats']).toHaveLength(1)
    expect(store.getters['assistant/currentChat'].title).toBe('New title')
  })

  test('resetting clears the chats instead of keeping the current one', async () => {
    await store.dispatch('assistant/createChat', workspace.id)

    await store.dispatch('assistant/reset')

    expect(store.getters['assistant/chats']).toStrictEqual([])
    expect(store.getters['assistant/currentChatId']).toBe(null)
  })
})
